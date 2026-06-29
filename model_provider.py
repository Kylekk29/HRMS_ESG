import asyncio
import json
import logging
import re
import time
from typing import Any, Dict, Optional

import config

logger = logging.getLogger(__name__)


class AIModelProvider:
    MAX_INPUT_CHARS = 180_000
    MAX_OUTPUT_TOKENS = 16_384

    def __init__(self):
        logger.info("Initializing AI Model Provider...")
        logger.info(f"  Model: {config.MODEL_NORMAL}")
        logger.info(f"  Base URL: {config.BASE_URL}")

        self._llm = None

        try:
            with open("prompts.json", "r", encoding="utf-8") as f:
                self.prompts = json.load(f)
            logger.info(f"Loaded prompts for {len(self.prompts)} features")
        except FileNotFoundError:
            logger.warning("prompts.json not found, using defaults")

    @property
    def llm(self):
        if self._llm is None:
            from langchain_openai import ChatOpenAI
            self._llm = ChatOpenAI(
                model=config.MODEL_NORMAL,
                openai_api_key=config.API_KEY,
                openai_api_base=config.BASE_URL,
                temperature=0.1,
                timeout=config.TIMEOUT,
                max_retries=config.MAX_RETRIES,
                max_tokens=self.MAX_OUTPUT_TOKENS,
            )
        return self._llm

    def _truncate_context(self, context: str) -> str:
        if len(context) <= self.MAX_INPUT_CHARS:
            return context
        keep_head = int(self.MAX_INPUT_CHARS * 0.6)
        keep_tail = self.MAX_INPUT_CHARS - keep_head - 50
        truncated = (
            f"{context[:keep_head]}\n\n... [truncated {len(context) - self.MAX_INPUT_CHARS} chars] ...\n\n"
            f"{context[-keep_tail:] if keep_tail > 0 else ''}"
        )
        logger.info(f"Truncated {len(context)} -> {len(truncated)} chars")
        return truncated

    def _extract_json(self, text: str) -> dict:
        # Remove markdown fences
        cleaned = re.sub(r"^```(?:json)?\s*|```\s*$", "", text.strip(), flags=re.MULTILINE).strip()

        def _try_parse(s: str):
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                pass
            try:
                fixed = s.replace("'", '"')
                fixed = re.sub(r",\s*}", "}", fixed)
                fixed = re.sub(r",\s*\]", "]", fixed)
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass
            return None

        # Direct full-text parse
        result = _try_parse(cleaned)
        if result is not None:
            return result

        # Find outermost JSON object by balanced brace matching
        brace_depth = 0
        json_start = -1
        for i, ch in enumerate(cleaned):
            if ch == "{":
                if brace_depth == 0:
                    json_start = i
                brace_depth += 1
            elif ch == "}":
                brace_depth -= 1
                if brace_depth == 0 and json_start >= 0:
                    result = _try_parse(cleaned[json_start:i+1])
                    if result is not None:
                        return result
                    json_start = -1

        # Find outermost JSON array by balanced bracket matching
        bracket_depth = 0
        json_start = -1
        for i, ch in enumerate(cleaned):
            if ch == "[":
                if bracket_depth == 0:
                    json_start = i
                bracket_depth += 1
            elif ch == "]":
                bracket_depth -= 1
                if bracket_depth == 0 and json_start >= 0:
                    result = _try_parse(cleaned[json_start:i+1])
                    if result is not None:
                        return result
                    json_start = -1

        logger.warning("Failed to extract JSON from AI response")
        logger.debug(f"Raw response (first 500): {text[:500]}")
        return {"error": "Failed to parse AI response", "raw": text[:800], "results": []}

    async def cv_screening_ai(
        self, context: str, feature: str, max_retries: int = 3, **kwargs
    ) -> dict | str:
        prompt_cfg = self.prompts.get(feature)
        if not prompt_cfg:
            return {"error": f"Unknown feature: {feature}", "results": []}

        context = self._truncate_context(context)
        kwarg_total = sum(len(str(v)) for v in kwargs.values())
        logger.info(f"AI CALL: {feature} (ctx={len(context)} + kwargs={kwarg_total} = {len(context)+kwarg_total} total chars)")

        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import StrOutputParser
        chain = ChatPromptTemplate.from_messages([
            ("system", prompt_cfg["system_prompt"]),
            ("user", prompt_cfg["user_template"]),
        ]) | self.llm | StrOutputParser()
        inputs = {"ctx": context, **kwargs}

        from openai import APIConnectionError, APITimeoutError, RateLimitError, APIError

        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                start = time.time()
                response = await asyncio.wait_for(chain.ainvoke(inputs), timeout=180)
                elapsed = time.time() - start
                logger.info(f"AI responded in {elapsed:.2f}s ({len(response)} chars)")

                if feature == "general_chat":
                    return response

                result = self._extract_json(response)
                if "error" not in result:
                    return result

                logger.warning(f"JSON parse failed (attempt {attempt})")
                if attempt < max_retries:
                    await asyncio.sleep(1)

            except (APIConnectionError, APITimeoutError) as e:
                last_error = e
                logger.warning(f"Connection/timeout (attempt {attempt}): {e}")
                if attempt < max_retries:
                    await asyncio.sleep(1)
            except RateLimitError as e:
                last_error = e
                logger.warning(f"Rate limit (attempt {attempt}): {e}")
                if attempt < max_retries:
                    await asyncio.sleep(2)
            except APIError as e:
                last_error = e
                logger.error(f"API error: {e}")
                break
            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error (attempt {attempt}): {e}", exc_info=True)
                if attempt < max_retries:
                    await asyncio.sleep(1)

        return {"error": f"AI call failed after {max_retries} attempts: {last_error}", "results": []}


    async def chat_stream(
        self, query: str, context: str = "", feature: str = None, **kwargs
    ):
        """Stream chat response token by token. Yields strings."""
        logger.info(f"STREAM: {query[:50]}... ({len(context)} ctx chars)")

        if not query.strip():
            yield "Error: Query cannot be empty."
            return

        prompt_cfg = self.prompts.get(feature)
        if not prompt_cfg:
            yield f"Error: Unknown feature: {feature}"
            return

        context = self._truncate_context(context)
        query = query[:10000]

        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import StrOutputParser
        chain = ChatPromptTemplate.from_messages([
            ("system", prompt_cfg["system_prompt"]),
            ("user", prompt_cfg["user_template"]),
        ]) | self.llm | StrOutputParser()
        inputs = {"query": query, "context": context, **kwargs}

        try:
            async for chunk in chain.astream(inputs):
                if chunk:
                    yield chunk
        except asyncio.TimeoutError:
            yield "\n\n[Response timed out. Please try a simpler question.]"
        except Exception as e:
            logger.error(f"Stream failed: {e}", exc_info=True)
            yield f"\n\n[Error: {str(e)}]"

    async def chat(self, query: str, context: str = "", feature: str = None, **kwargs) -> str:

        logger.info(f"CHAT: {query[:50]}... ({len(context)} ctx chars)")

        if not query.strip():
            return "Error: Query cannot be empty."

        prompt_cfg = self.prompts.get(feature)
        if not prompt_cfg:
            return f"Error: Unknown feature: {feature}"

        context = self._truncate_context(context)
        query = query[:10000]

        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import StrOutputParser
        chain = ChatPromptTemplate.from_messages([
            ("system", prompt_cfg["system_prompt"]),
            ("user", prompt_cfg["user_template"]),
        ]) | self.llm | StrOutputParser()
        inputs = {"query": query, "context": context, **kwargs}

        try:
            start = time.time()
            response = await asyncio.wait_for(chain.ainvoke(inputs), timeout=120)
            logger.info(f"Chat responded in {time.time() - start:.2f}s")
            return response[:50000] if response else ""
        except asyncio.TimeoutError:
            logger.error(f"Chat timed out after 120s")
            return "I'm sorry, the request timed out. Please try a simpler question or try again."
        except Exception as e:
            logger.error(f"Chat failed: {e}", exc_info=True)
            return f"I encountered an error: {str(e)}. Please try again."
