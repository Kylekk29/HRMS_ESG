"""
task_router.py  — AI-HR Bridge Platform v4.0
──────────────────────────────────────────────
Orchestrates HR workflows:
  1. Company-culture document upload & indexing
  2. Batch CV screening (embed all → single AI comparison call)
  3. Employee chat (RAG-powered Q&A)
  4. Interview transcript analysis

Uses shared screening_cache for resilience — never raises on AI failure.
"""
import asyncio
import logging
import os
import json
import time
import hashlib
from typing import List, Dict, Optional
from datetime import datetime

import config
import screening_cache
from model_provider import AIModelProvider
from embedding_mgr import EmbeddingManager

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = {
    "core_competency": 25,
    "experience": 20,
    "education": 10,
    "culture_fit": 15,
    "development": 15,
    "intelligence": 15,
}


def _screening_cache_key(jd: str, cv_files: List[Dict], weights: Optional[Dict] = None) -> str:
    cv_part = "|".join(sorted(f.get("file_name", "") for f in cv_files))
    w_part = json.dumps(weights or {}, sort_keys=True)
    raw = f"{jd}|{cv_part}|{w_part}"
    return "screen_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


class TaskRouter:
    def __init__(self, hrms_manager=None):
        logger.info("=" * 60)
        logger.info("Initializing TaskRouter...")
        start_time = time.time()

        self.ai = AIModelProvider()
        self.emb = EmbeddingManager()
        self.hrms = hrms_manager
        self._culture_db_id: str | None = None

        os.makedirs(config.SCREENING_HISTORY_DIR, exist_ok=True)

        logger.info(f"TaskRouter initialized in {time.time() - start_time:.2f}s")
        logger.info("=" * 60)

    # ── Company culture upload ──
# Add this method to TaskRouter class in task_router.py

    async def screen_single_candidate_with_text(
        self,
        jd: str,
        cv_data: Dict,
        weights: Optional[Dict] = None
    ) -> Dict:
        """
        Screen a single candidate using text content.
        cv_data should contain: {'file_name': str, 'content': str}
        """
        try:
            from screening_cache import default_scores
            
            content = cv_data.get("content", "").strip()
            file_name = cv_data.get("file_name", "candidate.txt")
            
            # If no content, return default scores
            if not content:
                fallback = default_scores("mid", "mid", "mid").copy()
                fallback["candidate_file"] = file_name
                fallback["candidate_name"] = file_name
                fallback["analysis"] = "No CV content provided."
                return fallback
            
            # Use the AI provider to analyze the CV
            # Build the prompt with the CV content and job description
            prompt = f"""
            Analyze the following CV for the job description.
            
            Job Description:
            {jd}
            
            CV Content:
            {content}
            
            Return a JSON response with the following structure:
            {{
                "scores": {{
                    "skills": 0-100,
                    "experience": 0-100,
                    "education": 0-100,
                    "culture_fit": 0-100,
                    "growth_potential": 0-100
                }},
                "total_score": 0-100,
                "analysis": "Detailed analysis text",
                "strengths": ["strength1", "strength2"],
                "weaknesses": ["weakness1", "weakness2"],
                "hiring_risk": "Low/Medium/High",
                "interview_questions": ["q1", "q2"],
                "recommendation": "Overall recommendation"
            }}
            
            Be thorough and specific based on the CV content.
            """
            
            # Get AI response
            ai_response = await self.ai_provider.generate(prompt)
            
            # Parse the response
            import json
            try:
                if isinstance(ai_response, str):
                    # Try to extract JSON from the response
                    # Find JSON content between ```json and ``` or just parse
                    if "```json" in ai_response:
                        json_start = ai_response.find("```json") + 7
                        json_end = ai_response.find("```", json_start)
                        json_str = ai_response[json_start:json_end].strip()
                    elif "```" in ai_response:
                        json_start = ai_response.find("```") + 3
                        json_end = ai_response.find("```", json_start)
                        json_str = ai_response[json_start:json_end].strip()
                    else:
                        json_str = ai_response
                    
                    result = json.loads(json_str)
                else:
                    result = ai_response
                    
                # Ensure all required fields exist
                scores = result.get("scores", {})
                return {
                    "candidate_file": file_name,
                    "candidate_name": file_name,
                    "analysis": result.get("analysis", "AI analysis completed"),
                    "scores": {
                        "skills": scores.get("skills", 70),
                        "experience": scores.get("experience", 70),
                        "education": scores.get("education", 70),
                        "culture_fit": scores.get("culture_fit", 70),
                        "growth_potential": scores.get("growth_potential", 70)
                    },
                    "total_score": result.get("total_score", 70),
                    "strengths": result.get("strengths", []),
                    "weaknesses": result.get("weaknesses", []),
                    "hiring_risk": result.get("hiring_risk", "Medium"),
                    "interview_questions": result.get("interview_questions", []),
                    "recommendation": result.get("recommendation", ""),
                    "cv_source": "text_input"
                }
                
            except (json.JSONDecodeError, KeyError) as parse_error:
                logger.error(f"Failed to parse AI response: {parse_error}")
                # Return default scores with the AI response as analysis
                fallback = default_scores("mid", "mid", "mid").copy()
                fallback["candidate_file"] = file_name
                fallback["candidate_name"] = file_name
                fallback["analysis"] = ai_response[:500] if isinstance(ai_response, str) else "AI analysis failed"
                return fallback
                
        except Exception as e:
            logger.error(f"Error in screen_single_candidate_with_text: {e}")
            fallback = default_scores("mid", "mid", "mid").copy()
            fallback["candidate_file"] = cv_data.get("file_name", "unknown")
            fallback["candidate_name"] = cv_data.get("file_name", "unknown")
            fallback["analysis"] = f"Error during analysis: {str(e)}"
            return fallback
    async def upload_company_culture(self, file_path: str, file_name: str) -> Dict:
        logger.info("=" * 60)
        logger.info(f"📄 UPLOADING COMPANY CULTURE: {file_name}")
        start_time = time.time()
        try:
            result = self.emb.embed_file_with_versioning(
                file_path, "company_culture", config.CULTURE_DB_DIR, "culture",
            )
            if "error" in result:
                logger.error(f"Failed: {result['error']}")
                return {"success": False, "message": result["error"], "db_id": None}
            self._culture_db_id = result["db_id"]
            elapsed = time.time() - start_time
            response = {
                "success": True, "message": result["message"],
                "db_id": result["db_id"], "action": result["action"],
                "version_number": result.get("version_number"),
                "chunk_count": result.get("chunk_count", 0),
                "is_new": result["is_new"],
            }
            logger.info(f"✅ Culture upload complete in {elapsed:.2f}s")
            return response
        except Exception as exc:
            logger.error(f"❌ Upload failed: {exc}", exc_info=True)
            return {"success": False, "message": str(exc), "db_id": None}

    # ── Batch CV screening ──

    async def batch_screen_cvs(
        self,
        jd: str,
        cv_files: List[Dict],
        weights: Optional[Dict[str, int]] = None,
    ) -> Dict:
        logger.info("=" * 60)
        logger.info("🔍 BATCH CV SCREENING STARTED")
        logger.info(f"  Files: {len(cv_files)}, JD length: {len(jd)}")

        overall_start = time.time()

        if weights is None:
            weights = DEFAULT_WEIGHTS.copy()
            logger.info(f"  Using default weights: {weights}")
        else:
            full_weights = DEFAULT_WEIGHTS.copy()
            full_weights.update(weights)
            weights = full_weights
            logger.info(f"  Custom weights provided, merged: {weights}")

        total = sum(weights.values())
        if total > 0:
            for k in weights:
                weights[k] = round(weights[k] / total * 100)

        logger.info(f"  Normalized weights: {weights} (sum={sum(weights.values())})")

        cache_key = _screening_cache_key(jd, cv_files, weights)
        cached = screening_cache.peek(cache_key)
        if cached is not None:
            logger.info(f"[CACHE] PEEK HIT — returning cached result (key={cache_key[:40]}...)")
            return cached

        if len(cv_files) > config.MAX_CV_BATCH_SIZE:
            logger.warning(f"  Batch size {len(cv_files)} exceeds limit {config.MAX_CV_BATCH_SIZE}, truncating")
            cv_files = cv_files[:config.MAX_CV_BATCH_SIZE]

        errors: List[Dict] = []
        step_times = {}

        t0 = time.time()
        logger.info("STEP 1/4: Embedding CVs...")
        embed_results = self.emb.embed_cv_batch(cv_files)
        step_times["embed"] = time.time() - t0
        logger.info(f"  Embedded {len(embed_results)} CVs in {step_times['embed']:.2f}s")

        t0 = time.time()
        logger.info("STEP 2/4: Retrieving company culture context...")
        culture_ctx = self._get_culture_context(jd)
        step_times["culture"] = time.time() - t0
        logger.info(f"  Culture context length: {len(culture_ctx)} chars ({step_times['culture']:.2f}s)")

        t0 = time.time()
        logger.info("STEP 3/4: Building candidate contexts via similarity search...")
        candidate_sections: List[str] = []
        successful_meta: List[Dict] = []

        for i, embed in enumerate(embed_results):
            if "error" in embed:
                logger.warning(f"  Embed error [{i+1}/{len(embed_results)}]: {embed['file_name']} — {embed['error']}")
                errors.append({"file": embed["file_name"], "error": embed["error"]})
                continue
            try:
                db = self.emb.load_db(embed["db_id"], config.CV_DB_DIR)
                docs = db.similarity_search(jd, k=config.CV_RETRIEVAL_K)
                cv_text = "\n".join(d.page_content for d in docs)
                section = (
                    f"=== CANDIDATE FILE: {embed['file_name']} ===\n"
                    f"{cv_text}\n"
                    f"=== END CANDIDATE: {embed['file_name']} ==="
                )
                candidate_sections.append(section)
                successful_meta.append({
                    "file_name": embed["file_name"],
                    "file_id": embed["file_id"],
                    "db_id": embed["db_id"],
                    "action": embed["action"],
                    "is_new": embed["is_new"],
                    "version_number": embed.get("version_number"),
                })
                logger.info(f"  Processed [{i+1}/{len(embed_results)}]: {embed['file_name']} (OK)")
            except Exception as exc:
                logger.error(f"  Search error [{i+1}/{len(embed_results)}]: {embed.get('file_name', '?')} — {exc}")
                errors.append({"file": embed.get("file_name", "?"), "error": str(exc)})

        step_times["build"] = time.time() - t0
        logger.info(f"  Built {len(candidate_sections)} candidate contexts in {step_times['build']:.2f}s")

        if not candidate_sections:
            logger.error("  All CV embeddings failed — no candidate sections built")
            return {
                "success": False, "total_processed": len(cv_files),
                "successful": 0, "failed": len(errors),
                "screening_results": [], "errors": errors,
                "message": "All CV embeddings failed.",
            }

        t0 = time.time()
        logger.info(f"STEP 4/4: Calling AI screening with {len(candidate_sections)} candidates...")
        all_candidates_ctx = "\n\n".join(candidate_sections)
        logger.info(f"  Combined context length: {len(all_candidates_ctx)} chars")

        weights_text_full = (
            f"Core Competency (core_competency_match): {weights.get('core_competency', 25)}%\n"
            f"Experience (experience_match): {weights.get('experience', 20)}%\n"
            f"Education (education_match): {weights.get('education', 10)}%\n"
            f"Culture Fit (culture_fit_score): {weights.get('culture_fit', 15)}%\n"
            f"Development Potential (development_potential): {weights.get('development', 15)}%\n"
            f"Intelligence (intelligence_score): {weights.get('intelligence', 15)}%\n"
            f"\nOverall Score Formula: overall_score = "
            f"(core_competency_match × {weights.get('core_competency', 25)} + "
            f"experience_match × {weights.get('experience', 20)} + "
            f"education_match × {weights.get('education', 10)} + "
            f"culture_fit_score × {weights.get('culture_fit', 15)} + "
            f"development_potential × {weights.get('development', 15)} + "
            f"intelligence_score × {weights.get('intelligence', 15)}) / 100"
        )

        ai_raw = await self.ai.cv_screening_ai(
            all_candidates_ctx, "cv_screening",
            jd=jd, culture_ctx=culture_ctx,
            weights_text=weights_text_full,
        )
        step_times["ai"] = time.time() - t0

        if isinstance(ai_raw, dict) and "results" in ai_raw:
            results_list = ai_raw["results"]
        elif isinstance(ai_raw, list):
            results_list = ai_raw
        else:
            results_list = []
        step_times["parse"] = time.time() - t0
        logger.info(f"  AI returned {len(results_list)} results in {step_times['ai']:.2f}s (+{step_times['parse']:.2f}s parse)")

        for i, res in enumerate(results_list):
            if i < len(successful_meta):
                res.setdefault("candidate_file", successful_meta[i]["file_name"])
                res["_meta"] = {
                    "db_id": successful_meta[i]["db_id"],
                    "action": successful_meta[i]["action"],
                    "is_new": successful_meta[i]["is_new"],
                    "version": successful_meta[i].get("version_number"),
                }
                logger.info(f"  Result [{i+1}/{len(results_list)}]: {res.get('candidate_file','?')} — score={res.get('overall_score','?')} status={res.get('match_status','?')}")

        screening_record = {
            "screening_id": f"SCR_{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.urandom(3).hex()}",
            "timestamp": datetime.now().isoformat(),
            "jd": jd[:2000],
            "weights": weights,
            "total_candidates": len(cv_files),
            "successful_candidates": len(successful_meta),
            "results": results_list,
            "ranking_summary": ai_raw.get("ranking_summary", "") if isinstance(ai_raw, dict) else "",
        }
        self._save_screening_history(screening_record)

        overall_elapsed = time.time() - overall_start

        response = {
            "success": len(errors) == 0,
            "total_processed": len(cv_files),
            "successful": len(candidate_sections),
            "failed": len(errors),
            "screening_id": screening_record["screening_id"],
            "weights_used": weights,
            "screening_results": [{
                "results": results_list,
                "culture_context_used": bool(culture_ctx and culture_ctx != "No company culture rules provided."),
            }],
            "errors": errors,
        }

        screening_cache.store(cache_key, response)
        self.emb.clear_faiss_cache()

        logger.info(f"✅ Screening complete in {overall_elapsed:.2f}s")
        logger.info(f"  Steps: embed={step_times.get('embed',0):.1f}s culture={step_times.get('culture',0):.1f}s build={step_times.get('build',0):.1f}s ai={step_times.get('ai',0):.1f}s")
        logger.info(f"  ID: {screening_record['screening_id']}")
        logger.info(f"  Results: {len(results_list)} successful, {len(errors)} failed")
        return response

    # ── Screening history CRUD ──

    def _save_screening_history(self, record: Dict) -> None:
        history = self._load_screening_history()
        history.insert(0, record)
        history = history[:100]
        with open(config.SCREENING_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)

    def _load_screening_history(self) -> List[Dict]:
        if os.path.exists(config.SCREENING_HISTORY_FILE):
            with open(config.SCREENING_HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def get_screening_history(self, limit: int = 20, offset: int = 0) -> Dict:
        history = self._load_screening_history()
        total = len(history)
        page = history[offset:offset + limit]
        summaries = []
        for h in page:
            summaries.append({
                "screening_id": h["screening_id"],
                "timestamp": h["timestamp"],
                "jd_preview": h.get("jd", "")[:200],
                "weights": h.get("weights", {}),
                "total_candidates": h.get("total_candidates", 0),
                "successful_candidates": h.get("successful_candidates", 0),
                "ranking_summary": h.get("ranking_summary", "")[:300],
            })
        return {"total": total, "offset": offset, "limit": limit, "screenings": summaries}

    def get_screening_detail(self, screening_id: str) -> Optional[Dict]:
        history = self._load_screening_history()
        for h in history:
            if h["screening_id"] == screening_id:
                return h
        return None

    # ── Employee chat ──


    @staticmethod
    def _classify_query(query: str) -> set:
        q = query.lower()
        sections = set()

        broad = ["all", "everything", "overview", "summary", "profile", "background", "tell me about", "detail", "full"]
        if any(w in q for w in broad) and len(q.split()) <= 8:
            return sections

        salary_kw = ["salary", "pay", "compensation", "bonus", "raise", "income", "wage", "earning", "paid"]
        if any(w in q for w in salary_kw):
            sections.add("salary")

        leave_kw = ["leave", "vacation", "annual leave", "sick leave", "personal leave", "time off",
                     "holiday", "off day", "maternity", "absence", "day off"]
        if any(w in q for w in leave_kw):
            sections.add("leave")

        contact_kw = ["contact", "emergency", "phone", "call", "reach"]
        if any(w in q for w in contact_kw):
            sections.add("contact")

        kpi_kw = ["kpi", "performance", "review", "score", "rating", "evaluation", "appraisal",
                   "goal", "metric", "target", "result", "assess"]
        if any(w in q for w in kpi_kw):
            sections.add("kpi")

        attendance_kw = ["attendance", "late", "absent", "tardy", "check in", "check out", "punctual",
                          "on time", "show up", "present"]
        if any(w in q for w in attendance_kw):
            sections.add("attendance")

        skill_kw = ["skill", "experience", "expertise", "technology", "technical", "background",
                     "qualification", "proficient", "competent", "know", "learn", "ability"]
        if any(w in q for w in skill_kw):
            sections.add("rag")

        return sections

    def _build_context(self, emp: dict, employee_id: str, query: str, sections: set) -> tuple:
        parts = []
        rag_used = False

        parts.append("=== EMPLOYEE PROFILE ===")
        parts.append(f"Name: {emp.get('full_name', 'N/A')}")
        parts.append(f"Position: {emp.get('position', 'N/A')}")
        parts.append(f"Department: {emp.get('department', 'N/A')}")
        parts.append(f"Status: {emp.get('status', 'N/A')}")
        parts.append(f"Hire Date: {emp.get('hire_date', 'N/A')}")
        parts.append(f"Employment Type: {emp.get('employment_type', 'N/A')}")
        parts.append(f"Notes: {emp.get('notes', 'N/A')}")

        if not sections or "salary" in sections:
            salary = emp.get('salary', {})
            parts.append("\n=== SALARY ===")
            parts.append(f"Base: {salary.get('base', 0)} {salary.get('currency', 'HKD')}")
            parts.append(f"Bonus: {salary.get('bonus', 0)}")
            parts.append(f"Last Review: {salary.get('last_review', 'N/A')}")

        if not sections or "leave" in sections:
            leave = emp.get('leave', {})
            parts.append("\n=== LEAVE BALANCE ===")
            for lt in ['annual_leave', 'sick_leave', 'personal_leave', 'maternity_leave', 'special_leave']:
                total = leave.get(f'{lt}_total', 0)
                used = leave.get(f'{lt}_used', 0)
                if total or used:
                    parts.append(f"{lt}: {used}/{total} (remaining: {total - used})")

            if self.hrms:
                leave_requests = self.hrms.get_all_leave_requests(employee_id=employee_id)
                if leave_requests:
                    parts.append("\n=== LEAVE REQUESTS ===")
                    for lr in leave_requests[-5:]:
                        parts.append(
                            f"ID: {lr.get('request_id', 'N/A')}, Type: {lr.get('leave_type', 'N/A')}, "
                            f"Dates: {lr.get('start_date', 'N/A')} to {lr.get('end_date', 'N/A')}, "
                            f"Status: {lr.get('status', 'N/A')}"
                        )

        if not sections or "contact" in sections:
            ec = emp.get('emergency_contact', {})
            if ec.get('name'):
                parts.append("\n=== EMERGENCY CONTACT ===")
                parts.append(f"Name: {ec.get('name', 'N/A')}")
                parts.append(f"Relationship: {ec.get('relationship', 'N/A')}")
                parts.append(f"Phone: {ec.get('phone', 'N/A')}")

        if not sections or "kpi" in sections:
            kpis = emp.get('kpi', [])
            if kpis:
                parts.append("\n=== KPI HISTORY ===")
                for kpi in kpis[-8:]:
                    parts.append(
                        f"Period: {kpi.get('period', 'N/A')}, Score: {kpi.get('score', 0)}, "
                        f"Rating: {kpi.get('rating', 'N/A')}, Comments: {kpi.get('comments', 'N/A')}"
                    )

        if not sections or "attendance" in sections:
            if self.hrms:
                now = datetime.now()
                attendance_records = self.hrms.get_monthly_attendance(employee_id, now.year, now.month)
                if attendance_records:
                    parts.append("\n=== ATTENDANCE (Current Month) ===")
                    for rec in attendance_records[-15:]:
                        parts.append(
                            f"Date: {rec.get('date', 'N/A')}, Check-in: {rec.get('check_in', 'N/A')}, "
                            f"Check-out: {rec.get('check_out', 'N/A')}, Status: {rec.get('status', 'N/A')}"
                        )

        doc_types = ["cv", "profile"]
        if sections and "rag" not in sections:
            doc_types = []
        for doc_type in doc_types:
            try:
                db = self.emb.load_employee_db(employee_id, doc_type)
                docs = db.similarity_search(query, k=3)
                if docs:
                    rag_used = True
                    parts.append(f"\n=== {doc_type.upper()} DOCUMENT (Relevant Excerpts) ===")
                    for i, doc in enumerate(docs):
                        parts.append(f"[Excerpt {i+1}]: {doc.page_content[:800]}")
            except FileNotFoundError:
                pass
            except Exception as exc:
                logger.warning(f"  Error loading {doc_type} DB: {exc}")

        return parts, rag_used

    async def employee_chat_stream(
        self, employee_id: str, query: str, conversation_history: str = ""
    ):
        """Stream AI chat response token by token."""
        logger.info(f"STREAM CHAT: {employee_id}")

        emp = self.hrms.get_employee(employee_id) if self.hrms else None
        if not emp:
            yield json.dumps({"error": f"Employee {employee_id} not found"})
            return

        sections = self._classify_query(query)
        context_parts, rag_used = self._build_context(emp, employee_id, query, sections)
        context = "\n".join(context_parts)
        if len(context) > 120000:
            context = context[:100000] + "\n...[truncated]"

        conversation_history = conversation_history[:10000] if conversation_history else ""

        async for token in self.ai.chat_stream(
            query=query,
            context=context,
            feature="employee_chat",
            conversation_history=conversation_history,
        ):
            yield token

    async def employee_chat(
        self, employee_id: str, query: str, conversation_history: str = ""
    ) -> Dict:
        logger.info(f"👤 EMPLOYEE CHAT: {employee_id}")
        logger.info(f"  Query: {query[:100]}...")
        if conversation_history:
            logger.info(f"  Has conversation history: {len(conversation_history)} chars")

        try:
            emp = self.hrms.get_employee(employee_id) if self.hrms else None
            if not emp:
                return {"success": False, "error": f"Employee {employee_id} not found or HRMS unavailable", "response": None}

            sections = self._classify_query(query)
            context_parts, rag_used = self._build_context(emp, employee_id, query, sections)
            context = "\n".join(context_parts)
            if len(context) > 120000:
                context = context[:100000] + "\n...[truncated]"

            if conversation_history and conversation_history.strip():
                conversation_history = conversation_history[:10000]
                enhanced_query = f"""Previous conversation:
{conversation_history}

New question:
{query}

Answer based on the employee data and conversation context."""
            else:
                enhanced_query = query

            rag_status = "RAG enhanced" if rag_used else "HRMS only"
            matched = ", ".join(sorted(sections)) if sections else "all"
            logger.info(f"  Context built ({rag_status}) sections=[{matched}]: {len(context)} chars")
            logger.info(f"  Query with history: {len(enhanced_query)} chars")

            response = await self.ai.chat(query=enhanced_query, context=context, feature="employee_chat")

            return {"success": True, "employee_id": employee_id, "response": response, "rag_used": rag_used, "error": None}

        except Exception as exc:
            logger.error(f"Employee chat failed for {employee_id}: {exc}", exc_info=True)
            return {"success": False, "error": str(exc), "response": None}

    # ── Development Suggestions ──

    async def get_development_suggestions(self, employee_id: str) -> Dict:
        logger.info(f"📚 DEVELOPMENT SUGGESTIONS for: {employee_id}")
        try:
            emp = self.hrms.get_employee(employee_id) if self.hrms else None
            if not emp:
                return {"success": False, "error": f"Employee {employee_id} not found", "suggestions": None}

            context_parts = []
            context_parts.append(f"Name: {emp.get('full_name', 'N/A')}")
            context_parts.append(f"Current Position: {emp.get('position', 'N/A')}")
            context_parts.append(f"Department: {emp.get('department', 'N/A')}")
            context_parts.append(f"Years of Service: {emp.get('hire_date', 'N/A')}")

            kpis = emp.get('kpi', [])
            if kpis:
                avg_score = sum(k.get('score', 0) for k in kpis if k.get('score')) / len(kpis)
                context_parts.append(f"\nPerformance Summary: Average KPI Score = {avg_score:.1f}/100")
                kpi_str = ", ".join([f"{k.get('period', '?')}: {k.get('score', 0)}" for k in kpis[-3:]])
                context_parts.append(f"Recent KPIs: {kpi_str}")

            skills_found = []
            for doc_type in ["cv", "profile"]:
                try:
                    db = self.emb.load_employee_db(employee_id, doc_type)
                    docs = db.similarity_search("skills programming languages technical abilities", k=5)
                    for doc in docs:
                        skills_found.append(doc.page_content[:800])
                except:
                    pass

            if skills_found:
                context_parts.append("\n=== Current Skills (from documents) ===")
                context_parts.append("\n".join(skills_found[:2]))

            position = emp.get('position', '').lower()
            if 'senior' in position or 'lead' in position or 'manager' in position:
                career_stage = "Senior/Leadership"
            elif 'junior' in position or 'associate' in position or 'entry' in position:
                career_stage = "Early Career"
            else:
                career_stage = "Mid Career"
            context_parts.append(f"\nCareer Stage: {career_stage}")

            context = "\n".join(context_parts)
            if len(context) > 30000:
                context = context[:25000] + "\n...[truncated]"

            development_prompt = f"""You are a senior career development consultant and HR strategy expert. Based on the following employee information, provide detailed career development suggestions.

Employee Information:
{context}

Please provide the following:

1. **Skill Development Suggestions** — What skills should this employee learn or improve? (Consider current position and future growth)
2. **Training Course Recommendations** — Recommend 3-5 specific training courses or certifications
3. **Career Path** — Suggested next position and long-term development direction
4. **Performance Improvement Tips** — Based on KPI performance, how to further improve
5. **Potential Risks** — Factors that may affect development

Provide professional, specific, and actionable suggestions. Use markdown formatting with clear headings and sections. Avoid vague content."""

            response = await self.ai.chat(query=development_prompt, context=context, feature="employee_chat")

            return {"success": True, "employee_id": employee_id, "employee_name": emp.get('full_name', employee_id), "suggestions": response, "error": None}

        except Exception as exc:
            logger.error(f"Development suggestions failed for {employee_id}: {exc}", exc_info=True)
            return {"success": False, "error": str(exc), "suggestions": None}

    # ── Interview analysis ──

    RED_FLAG_PATTERNS = {
        "VAGUENESS": {
            "patterns": [
                r"\bI don'?t know\b", r"\bnot sure\b", r"\bmaybe\b", r"\bkind of\b",
                r"\bsort of\b", r"\bbasically\b", r"\byou know\b", r"\bsomething like that\b",
                r"\bI can'?t remember\b", r"\bI forget\b", r"\bI don'?t recall\b",
                r"\bnot really sure\b", r"\bI guess\b", r"\bprobably\b",
                r"\bit was like\b", r"\bthings like that\b",
            ],
            "severity": "warning",
            "label": "Vague / Lacks Specifics",
            "explanation": "Candidate used vague language instead of concrete examples"
        },
        "NEGATIVITY": {
            "patterns": [
                r"\bbad\s+(manager|boss|company|team|environment|culture)\b",
                r"\bterrible\b", r"\bhorrible\b", r"\bworst\b", r"\btoxic\b",
                r"\bblame\b", r"\bthey never\b", r"\balways had to\b",
                r"\bmicromanage", r"\bpolitics?\b", r"\bdrama\b",
                r"\bdidn'?t like\b", r"\bhated\b", r"\bhate\b",
                r"\bunfair\b", r"\bunreasonable\b", r"\bno support\b",
                r"\bthey didn'?t (care|help|support|listen)\b",
            ],
            "severity": "warning",
            "label": "Negative About Past",
            "explanation": "Candidate spoke negatively about past employers, managers, or colleagues"
        },
        "EXAGGERATION": {
            "patterns": [
                r"\b100%?\b", r"\balways\b", r"\bnever\b", r"\beveryone\b",
                r"\bnobody\b", r"\bperfect\b", r"\bflawless\b", r"\bzero (defects?|bugs?|issues?)\b",
                r"\bby myself\b", r"\bentire (project|system|company)\b",
                r"\ball by myself\b", r"\bevery single\b",
                r"\brevolutionized\b", r"\btransformed\b",
                r"\bnobody else could\b",
            ],
            "severity": "info",
            "label": "Possible Exaggeration",
            "explanation": "Candidate used absolute language that may overstate achievements"
        },
        "EVASION": {
            "patterns": [
                r"\bthat'?s a (good|great) question\b",
                r"\bnext question\b", r"\bpass\b", r"\bmove on\b",
                r"\bI'?d rather not\b", r"\bI prefer not to\b",
                r"\bcan'?t say\b", r"\bwon'?t answer\b",
                r"\bthat'?s (not|irrelevant)\b",
                r"\bI don'?t (think|want to) (answer|say|discuss)\b",
                r"\bnot comfortable\b",
                r"\bcan we skip\b",
            ],
            "severity": "critical",
            "label": "Evasion / Avoidance",
            "explanation": "Candidate avoided answering a direct question"
        },
        "CONTRADICTION": {
            "patterns": [
                r"\b(on one hand|however|but actually).{20,}(on the other hand|actually|however)\b",
                r"\bI (love|enjoy|like).{30,}(but|however|honestly)\b",
            ],
            "severity": "critical",
            "label": "Self-Contradiction",
            "explanation": "Candidate's statements contradict each other"
        },
        "SKILL_MISMATCH": {
            "patterns": [
                r"\bI don'?t have (experience|knowledge|skills?|background)\b",
                r"\bnever (worked with|used|done)\b",
                r"\bbasic (knowledge|understanding|experience)\b",
                r"\bnot my (area|field|specialty|expertise)\b",
                r"\bno (experience|exposure|background)\b",
                r"\blimited (experience|exposure|knowledge)\b",
                r"\bI'?m (not|still) learning\b",
                r"\bI only know\b",
            ],
            "severity": "warning",
            "label": "Skill Gap Acknowledged",
            "explanation": "Candidate admitted lacking required skills or experience"
        },
        "ATTITUDE": {
            "patterns": [
                r"\bthat'?s (not|below) me\b", r"\bnot my (job|responsibility)\b",
                r"\bI don'?t need to\b", r"\bI already know\b",
                r"\bthat'?s (easy|simple|trivial)\b",
                r"\bI'?m overqualified\b",
                r"\bI don'?t do\b",
                r"\bwhy would I\b", r"\bI shouldn'?t have to\b",
                r"\binterrupt", r"\btalk over\b",
            ],
            "severity": "critical",
            "label": "Attitude Concern",
            "explanation": "Candidate displayed poor attitude, entitlement, or defensiveness"
        },
        "GAP": {
            "patterns": [
                r"\bpersonal reasons?\b", r"\bfamily reasons?\b",
                r"\btook (time|a break|some time) off\b",
                r"\bwas between (jobs|roles|positions?)\b",
                r"\bleft without\b", r"\bnot working\b",
                r"\bgap in (my|the) (resume|CV|employment)\b",
                r"\bdidn'?t work for\b",
            ],
            "severity": "info",
            "label": "Unexplained Gap",
            "explanation": "Candidate mentioned an employment gap without clear explanation"
        },
    }

    @staticmethod
    def _detect_red_flags(transcript: str) -> list:
        results = []
        seen_quotes = set()
        import re
        for category, config in TaskRouter.RED_FLAG_PATTERNS.items():
            for pattern in config["patterns"]:
                for match in re.finditer(pattern, transcript, re.IGNORECASE):
                    start = max(0, match.start() - 40)
                    end = min(len(transcript), match.end() + 60)
                    context = transcript[start:end].strip()
                    key = category + context[:80]
                    if key not in seen_quotes:
                        seen_quotes.add(key)
                        results.append({
                            "category": category,
                            "severity": config["severity"],
                            "label": config["label"],
                            "quote": context[:150],
                            "explanation": config["explanation"],
                        })
        return results

    async def analyze_interview(self, transcript: str, jd: str, competency: str = "") -> Dict:
        logger.info("🎤 INTERVIEW ANALYSIS")
        logger.info(f"  Transcript length: {len(transcript)} chars")
        logger.info(f"  JD length: {len(jd)} chars")

        if not transcript.strip():
            return {"success": False, "error": "Interview transcript cannot be empty.", "analysis": None}
        if not jd.strip():
            return {"success": False, "error": "Job description cannot be empty.", "analysis": None}

        red_flags = self._detect_red_flags(transcript)

        try:
            result = await self.ai.cv_screening_ai(transcript, "interview_assistant", jd=jd, competency=competency or "Not specified")
            if isinstance(result, dict):
                if "error" in result:
                    return {
                        "success": True,
                        "analysis": self._merge_red_flags({}, red_flags),
                        "error": None,
                        "_fallback": True,
                    }
                analysis = self._merge_red_flags(result, red_flags)
                return {"success": True, "analysis": analysis, "error": None, "red_flag_count": len(red_flags)}
            return {"success": False, "error": "Unexpected response format from AI", "analysis": None}
        except Exception as exc:
            logger.error(f"  ❌ Interview analysis failed: {exc}", exc_info=True)
            return {
                "success": True,
                "analysis": self._merge_red_flags({}, red_flags),
                "error": None,
                "_fallback": True,
            }

    def _merge_red_flags(self, ai_result: dict, auto_flags: list) -> dict:
        ai_red_flags = ai_result.get("red_flags", [])
        if isinstance(ai_red_flags, list) and len(ai_red_flags) > 0:
            if isinstance(ai_red_flags[0], str):
                ai_red_flags = [{
                    "category": "AI_DETECTED",
                    "severity": "warning",
                    "label": "AI Identified Concern",
                    "quote": "",
                    "explanation": rf,
                } for rf in ai_red_flags]
        all_flags = auto_flags + ai_red_flags
        severity_score = sum(
            {"critical": 3, "warning": 2, "info": 1}.get(f.get("severity", "info"), 1)
            for f in all_flags
        )
        ai_result["red_flags"] = all_flags
        ai_result["red_flag_summary"] = {
            "total": len(all_flags),
            "critical": sum(1 for f in all_flags if f.get("severity") == "critical"),
            "warning": sum(1 for f in all_flags if f.get("severity") == "warning"),
            "info": sum(1 for f in all_flags if f.get("severity") == "info"),
            "severity_score": severity_score,
            "auto_detected": len(auto_flags),
        }
        if "overall_score" in ai_result:
            penalty = min(severity_score * 2, 30)
            ai_result["overall_score"] = max(0, ai_result["overall_score"] - penalty)
        return ai_result

    # ── Predictive Labour Demand Analysis ──

    async def workforce_forecast(
        self,
        company_name: str = "Our Company",
        industry: str = "General",
    ) -> Dict:
        logger.info("PREDICTIVE LABOUR DEMAND ANALYSIS")
        logger.info(f"  Company: {company_name}, Industry: {industry}")

        employees = self.hrms.list_employees() if self.hrms else []
        if not employees:
            return {"success": False, "error": "No employee data available", "analysis": None}

        employee_count = len(employees)
        logger.info(f"  Employees: {employee_count}")

        # Build a stable cache hash from the employee data
        employees_hash = hashlib.sha256(
            json.dumps([e.get("employee_id") for e in employees], sort_keys=True).encode()
        ).hexdigest()[:16]

        async def compute_forecast() -> dict:
            dept_summary = self.hrms.get_department_summary() if self.hrms else {}

            dept_groups = {}
            for emp in employees:
                d = emp.get("department", "Unknown")
                dept_groups.setdefault(d, []).append(emp)

            dept_rollup = {}
            for dept, emps in dept_groups.items():
                kpi_scores = [k.get("score", 0) for e in emps for k in e.get("kpi", []) if k.get("score")]
                salaries = [e.get("salary", {}).get("base", 0) for e in emps]
                dept_rollup[dept] = {
                    "count": len(emps), "avg_kpi": round(sum(kpi_scores)/len(kpi_scores), 1) if kpi_scores else 0,
                    "avg_salary": round(sum(salaries)/len(salaries)) if salaries else 0,
                    "min_salary": min(salaries) if salaries else 0, "max_salary": max(salaries) if salaries else 0,
                }

            sample_records = []
            for dept, emps in dept_groups.items():
                for emp in emps[:max(2, len(emps)//2)]:
                    kpi_list = emp.get("kpi", [])
                    scores = [k.get("score", 0) for k in kpi_list if k.get("score")]
                    trend = "up" if len(scores) >= 2 and scores[-1] > scores[0] else ("down" if len(scores) >= 2 and scores[-1] < scores[0] else "stable")
                    sample_records.append({
                        "id": emp.get("employee_id")[-4:], "r": emp.get("position")[:20],
                        "d": dept, "t": round(self._calc_tenure(emp.get("hire_date")), 1),
                        "s": emp.get("salary", {}).get("base", 0), "k": round(sum(scores)/len(scores), 1) if scores else 0,
                        "tr": trend, "lk": scores[-1] if scores else 0,
                    })

            emp_kpi = []
            low_performers = []
            for emp in employees:
                kpi_list = emp.get("kpi", [])
                scores = [k.get("score", 0) for k in kpi_list if k.get("score")]
                avg_kpi = round(sum(scores)/len(scores), 1) if scores else 0
                trend = "up" if len(scores) >= 2 and scores[-1] > scores[0] else ("down" if len(scores) >= 2 and scores[-1] < scores[0] else "stable")
                last_kpi = scores[-1] if scores else 0
                emp_rec = {
                    "id": emp.get("employee_id"), "name": emp.get("full_name", "").split()[0],
                    "dept": emp.get("department"), "pos": emp.get("position"),
                    "avg_kpi": avg_kpi, "trend": trend, "last_kpi": last_kpi,
                    "tenure_yrs": round(self._calc_tenure(emp.get("hire_date")), 1),
                    "salary": emp.get("salary", {}).get("base", 0),
                }
                emp_kpi.append(emp_rec)
                if trend == "down" and avg_kpi < 75 and last_kpi < 70:
                    low_performers.append(emp_rec)

            employee_data_text = json.dumps(
                {"departments": dept_rollup, "sample": sample_records, "all_employees": emp_kpi, "low_performers": low_performers},
                ensure_ascii=False
            )[:12000]

            dept_text = json.dumps({d: v for d, v in (dept_summary or {}).items()}, ensure_ascii=False)[:3000]
            attendance_summary = self._build_attendance_summary(employees)[:2000]

            company_culture_ctx = self._get_culture_context(
                "company strategy financial outlook expansion workforce planning"
            )
            docs_text = company_culture_ctx[:8000] if company_culture_ctx and "No company culture" not in company_culture_ctx else "No company culture documents."

            now = datetime.now()
            ai_result = await self.ai.cv_screening_ai(
                f"Labour demand analysis for {company_name} ({industry}, {employee_count} employees)",
                "labour_demand",
                max_retries=1,
                company_name=company_name or "Our Company",
                industry=industry or "General",
                current_date=now.strftime("%Y-%m-%d"),
                company_docs=docs_text,
                employee_count=employee_count,
                employee_data=employee_data_text,
                department_summary=dept_text,
                attendance_summary=attendance_summary,
                market_context=(
                    "Trends: AI/ML demand rising, remote work standard, "
                    "salary growth in tech, automation replacing routine roles, "
                    "ESG roles growing, digital transformation accelerating"
                ),
            )

            if isinstance(ai_result, dict) and "error" not in ai_result:
                return {"success": True, "analysis": ai_result, "error": None, "_fallback": False}

            raise RuntimeError(ai_result.get("error", "AI returned no valid result"))

        result = await screening_cache.forecast_get_or_compute(
            company_name, industry, employees_hash, compute_forecast
        )
        if "analysis" not in result or result.get("_fallback"):
            result.setdefault("_cached", False)
        return result

    def _calc_tenure(self, hire_date: str) -> float:
        if not hire_date:
            return 0
        try:
            hired = datetime.strptime(hire_date, "%Y-%m-%d")
            return round((datetime.now() - hired).days / 365.25, 1)
        except ValueError:
            return 0

    def _calc_avg_kpi(self, kpis: List[Dict]) -> float:
        scores = [k.get("score", 0) for k in kpis if k.get("score")]
        return round(sum(scores) / len(scores), 1) if scores else 0.0

    def _build_attendance_summary(self, employees: List[Dict]) -> str:
        if not self.hrms:
            return "Attendance data unavailable"
        try:
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")
            daily = self.hrms.get_daily_attendance_summary(today)
            return json.dumps(daily, indent=2, ensure_ascii=False) if daily else "No attendance data today"
        except Exception:
            return "Attendance data unavailable"

    # ── Helper: culture context ──

    def _get_culture_context(self, query: str) -> str:
        if not self._culture_db_id:
            db_id = self.emb.version_mgr.get_current_db_id("company_culture")
            if db_id:
                self._culture_db_id = db_id
        if not self._culture_db_id:
            return "No company culture rules provided."
        try:
            db = self.emb.load_db(self._culture_db_id, config.CULTURE_DB_DIR)
            docs = db.similarity_search(query, k=config.CULTURE_RETRIEVAL_K)
            return "\n".join(d.page_content for d in docs)
        except Exception:
            return "No company culture rules provided."
