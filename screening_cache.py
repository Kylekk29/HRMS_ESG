"""Global async screening + forecast cache. Semaphore(3) for concurrent compute.
JSON persistence. Fallback scores when AI unavailable."""

import asyncio
import hashlib
import json
import logging
import os
from typing import Callable, Dict, Optional
import time
import config

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(config.DATA_ROOT, "screen_cache")
CACHE_FILE = os.path.join(CACHE_DIR, "screening_cache.json")
os.makedirs(CACHE_DIR, exist_ok=True)

_cache: Dict[str, dict] = {}
_cache_lock = asyncio.Lock()
_cache_semaphore = asyncio.Semaphore(3)

if os.path.exists(CACHE_FILE):
    try:
        t0 = time.time()
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            if isinstance(loaded, dict):
                _cache.update(loaded)
        logger.info(f"[CACHE] Loaded {len(loaded)} entries from disk in {time.time()-t0:.3f}s")
    except Exception as e:
        logger.warning(f"[CACHE] Load failed: {e}")


def _save():
    try:
        t0 = time.time()
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False, indent=2)
        logger.info(f"[CACHE] Saved {len(_cache)} entries to disk in {time.time()-t0:.3f}s")
    except Exception as e:
        logger.warning(f"[CACHE] Save failed: {e}")


def _score_level(val: str) -> int:
    m = {
        "phd": 90, "master": 75, "bachelor": 60, "highschool": 45,
        "7plus": 90, "3to5": 75, "1to3": 60, "under1": 40,
        "high": 85, "mid": 65, "low": 45,
        "6months": 50, "1week": 70, "tomorrow": 90,
    }
    return m.get(val, 65)

def default_scores(edu: str = "mid", exp: str = "mid", skill: str = "mid") -> dict:
    e = _score_level(edu)
    x = _score_level(exp)
    s = _score_level(skill)
    i = round((e + x + s) / 3)
    return {
        "overall_score": round(e * 0.20 + x * 0.25 + s * 0.35 + i * 0.20),
        "core_competency_match": s,
        "experience_match": x,
        "education_match": e,
        "culture_fit_score": round(e * 0.5 + x * 0.5),
        "development_potential": s,
        "intelligence_score": i,
        "eight_dim_scores": {
            "professional_skills": s,
            "communication": round(s * 0.6 + x * 0.4),
            "teamwork": round(s * 0.4 + e * 0.3 + x * 0.3),
            "problem_solving": round(s * 0.6 + e * 0.4),
            "learning_ability": round(s * 0.5 + e * 0.5),
            "execution": round(s * 0.5 + x * 0.5),
            "cultural_fit": round(e * 0.5 + x * 0.5),
            "leadership": round(x * 0.6 + s * 0.4),
        },
        "summary": f"Candidate with {edu} education, {exp} experience, {skill} skills. (AI default)",
        "analysis": {
            "strengths": ["Background aligns with selection criteria", "Structured skill progression"],
            "weaknesses": ["Full AI evaluation pending service restoration"],
            "culture_alignment": ["Presumed compatible based on level assessment"],
            "development_potential_and_suggestions": ["Further AI-driven assessment unavailable"],
            "hiring_risks": ["AI risk assessment unavailable; review manually"]
        },
        "interview_focus": ["Walk me through your relevant experience", "What interests you about this role?"],
        "_fallback": True,
    }


def _make_booth_cache_key(category: str, edu: str, exp: str, skill: str, jd: str) -> str:
    return f"booth_{category}_{edu}_{exp}_{skill}_{hashlib.sha256(jd.encode('utf-8')).hexdigest()[:16]}"


async def get_or_compute(key: str, compute_fn: Callable, fallback_key: Optional[dict] = None) -> dict:
    async with _cache_lock:
        if key in _cache:
            logger.info(f"[CACHE] HIT — {key[:60]}")
            logger.info(f"[CACHE] Returning cached result for {key[:60]}")
            result = dict(_cache[key])
            result["_cached"] = True
            return result
    async with _cache_semaphore:
        async with _cache_lock:
            if key in _cache:
                logger.info(f"[CACHE] HIT (2nd check) — {key[:60]}")
                logger.info(f"[CACHE] Returning cached result for {key[:60]}")
                result = dict(_cache[key])
                result["_cached"] = True
                return result
        logger.info(f"[CACHE] MISS — computing {key[:60]}")
        try:
            result = await compute_fn()
            if isinstance(result, dict) and result.get("success") is not False:
                async with _cache_lock:
                    _cache[key] = result
                    _save()
                logger.info(f"[CACHE] Computed and stored {key[:60]}")
                result["_cached"] = False
                return result
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[CACHE] Compute failed ({key[:60]}): {e}")
    if fallback_key:
        logger.warning(f"[CACHE] Using fallback scores for {key[:60]}")
        return default_scores(
            fallback_key.get("edu", "mid"),
            fallback_key.get("exp", "mid"),
            fallback_key.get("skill", "mid"),
        )
    return {"success": False, "error": "AI unavailable", "fallback": True, "screening_results": []}


async def booth_get_or_compute(category: str, edu: str, exp: str, skill: str, jd: str, compute_fn: Callable) -> dict:
    key = _make_booth_cache_key(category, edu, exp, skill, jd)
    return await get_or_compute(key, compute_fn, {"edu": edu, "exp": exp, "skill": skill})


def peek(key: str) -> Optional[dict]:
    return _cache.get(key)


def store(key: str, value: dict):
    async def _store():
        async with _cache_lock:
            _cache[key] = value
            _save()
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_store())
    except RuntimeError:
        asyncio.run(_store())


def get_cache_size() -> int:
    return len(_cache)


def clear_cache():
    global _cache
    _cache = {}
    if os.path.exists(CACHE_FILE):
        try:
            os.remove(CACHE_FILE)
        except OSError:
            pass


# ── Unified Cache API (screening + forecast both use _cache) ──

FORECAST_PREFIX = "fc_"

def _forecast_cache_key(company_name: str, industry: str, employees_hash: str) -> str:
    raw = f"forecast|{company_name}|{industry}|{employees_hash}"
    return FORECAST_PREFIX + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


async def forecast_get_or_compute(
    company_name: str,
    industry: str,
    employees_hash: str,
    compute_fn: Callable,
) -> dict:
    """Same pattern as get_or_compute() above — lock, semaphore, cache hit, compute, store."""
    key = _forecast_cache_key(company_name, industry, employees_hash)

    async with _cache_lock:
        if key in _cache:
            logger.info("[FORECAST CACHE] HIT")
            return _cache[key]

    async with _cache_semaphore:
        async with _cache_lock:
            if key in _cache:
                logger.info("[FORECAST CACHE] HIT")
                return _cache[key]

        logger.info("[FORECAST CACHE] MISS — computing")
        try:
            result = await compute_fn()
            if isinstance(result, dict):
                async with _cache_lock:
                    _cache[key] = result
                    _save()
                logger.info("[FORECAST CACHE] stored")
                return result
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[FORECAST CACHE] Compute failed: {e}")

    return default_forecast()


def forecast_cache_invalidate():
    """Clear only forecast entries from cache."""
    global _cache
    keys = [k for k in _cache if k.startswith(FORECAST_PREFIX)]
    for k in keys:
        del _cache[k]
    _save()


def default_forecast(employee_count: int = 35) -> dict:
    """Fallback forecast when AI is unavailable — returns sensible defaults."""
    import datetime
    now = datetime.datetime.now()
    return {
        "success": True,
        "analysis": {
            "forecast": {
                "current_headcount": employee_count,
                "projected_headcount_3m": employee_count,
                "projected_headcount_6m": employee_count + 2,
                "projected_headcount_12m": employee_count + 5,
                "recruitment_needs": {
                    "3_months": [],
                    "6_months": [],
                    "12_months": [{"position": "General", "count": 2, "urgency": "Medium", "reason": "Natural growth"}]
                }
            },
            "turnover_analysis": {
                "historical_turnover_rate": 8.0,
                "projected_turnover_rate": 10.0,
                "high_risk_departments": []
            },
            "employee_competitiveness": [],
            "termination_suggestions": [],
            "department_projections": [],
            "termination_analysis": [],
            "market_trends": {
                "industry_outlook": "Analysis pending — AI service was unavailable. Default projections shown.",
                "key_trends": ["AI and automation reshaping workforce", "Remote work becoming standard"],
                "salary_benchmarks": "Check market reports for current data",
                "talent_availability": "Varies by role and location"
            },
            "recommendations": {
                "immediate_actions": ["Run AI analysis when service is available for accurate results"],
                "strategic_hiring_plan": "AI analysis unavailable — please re-run when DeepSeek service is accessible",
                "cost_savings_estimate": 0,
                "workforce_optimization": ["Review manually — AI-assisted analysis pending"]
            }
        },
        "error": None,
        "_fallback": True,
        "_cached": False,
    }

