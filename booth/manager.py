"""Booth Game matching engine with category support and cached AI screening."""

import logging
import os
import random
import time
from datetime import datetime
from typing import Dict, Optional

from fastapi import HTTPException
import screening_cache

logger = logging.getLogger(__name__)
BASE_DIR = os.path.join(os.path.dirname(__file__), "candidates")

# ── Per-category level definitions (4×4×2×3 = 96 combos) ──
EDU_LEVELS = ["phd", "master", "bachelor", "highschool"]
EXP_LEVELS = ["7plus", "3to5", "1to3", "under1"]
SKILL_LEVELS = ["high", "low"]
AVAIL_LEVELS = ["6months", "1week", "tomorrow"]

EDU_LABEL = {"phd": "博士", "master": "碩士", "bachelor": "學士", "highschool": "中學"}
EXP_LABEL = {"7plus": "7年以上", "3to5": "3-5年", "1to3": "1-3年", "under1": "1年以下"}
SKILL_LABEL = {"high": "高", "low": "低"}
AVAIL_LABEL = {"6months": "半年", "1week": "一周內", "tomorrow": "明天早上就上班"}

EDU_WEIGHT = {"phd": 4, "master": 3, "bachelor": 2, "highschool": 1}
EXP_WEIGHT = {"7plus": 4, "3to5": 3, "1to3": 2, "under1": 1}
SKILL_WEIGHT = {"high": 2, "low": 1}
AVAIL_WEIGHT = {"6months": 1, "1week": 2, "tomorrow": 3}

CATEGORY_META = {
    "engineer": {
        "label": "工程師 (Engineer)", "icon": "⚙️",
        "description": "軟體開發、系統設計、技術研發",
        "default_jd": "軟體工程師\n工作內容：系統開發與維護、API設計、技術文件撰寫、程式碼審查\n需求條件：熟悉Python/Java、資料庫設計、版本控制\n加分條件：雲端服務經驗、容器化技術、CI/CD",
    },
    "management": {
        "label": "管理職 (Management)", "icon": "📊",
        "description": "專案管理、團隊領導、策略規劃",
        "default_jd": "專案經理\n工作內容：專案規劃與執行、團隊管理、預算控管、利害關係人溝通\n需求條件：專案管理經驗、團隊領導能力、跨部門協作\n加分條件：PMP認證、敏捷開發經驗、產業知識",
    },
    "sales": {
        "label": "業務 (Sales)", "icon": "🤝",
        "description": "客戶開發、銷售管理、市場拓展",
        "default_jd": "業務專員\n工作內容：客戶開發與維護、產品銷售、市場分析、貿易文件處理\n需求條件：業務開發能力、溝通技巧、客戶關係管理\n加分條件：國際貿易經驗、外語能力、產業知識",
    },
}

_NAMES = [
    ("陳志明","Chen Ming"), ("林怡君","Lin Yi-Jun"), ("黃雅婷","Huang Ya-Ting"),
    ("張建宏","Chang Jian-Hong"), ("李美玲","Lee Mei-Ling"), ("王俊傑","Wang Chun-Chieh"),
    ("吳淑芬","Wu Shu-Fen"), ("劉偉成","Liu Wei-Cheng"), ("蔡靜怡","Tsai Ching-Yi"),
    ("楊國華","Yang Kuo-Hua"), ("許佳琪","Hsu Chia-Chi"), ("謝文雄","Hsieh Wen-Hsiung"),
    ("洪惠如","Hung Hui-Ju"), ("郭宗翰","Kuo Tsung-Han"), ("賴婉婷","Lai Wan-Ting"),
    ("周勝雄","Chou Sheng-Hsiung"), ("葉佩珊","Yeh Pei-Shan"), ("廖信宏","Liao Hsin-Hung"),
    ("鄭雅琳","Cheng Ya-Lin"), ("何家豪","Ho Chia-Hao"), ("陳美華","Chen Mei-Hua"),
    ("林正義","Lin Cheng-Yi"), ("黃麗君","Huang Li-Chun"), ("張志豪","Chang Chih-Hao"),
    ("李淑惠","Lee Shu-Hui"), ("王國龍","Wang Kuo-Long"), ("吳佳穎","Wu Chia-Ying"),
    ("沈怡君","Shen Yi-Chun"), ("許智偉","Hsu Chih-Wei"), ("曾雅雯","Tseng Ya-Wen"),
    ("彭國豪","Peng Kuo-Hao"), ("韓詩婷","Han Shih-Ting"),
]

CANDIDATE_TAGS: Dict[str, Dict] = {}
for cat in CATEGORY_META:
    idx = 0
    for edu in EDU_LEVELS:
        for exp in EXP_LEVELS:
            for skill in SKILL_LEVELS:
                for avail in AVAIL_LEVELS:
                    name = _NAMES[idx % len(_NAMES)]
                    fname = f"{idx+1:03d}_{edu}_{exp}_{skill}_{avail}.txt"
                    diff = 13 - (EDU_WEIGHT[edu] + EXP_WEIGHT[exp] + SKILL_WEIGHT[skill] + AVAIL_WEIGHT[avail])
                    CANDIDATE_TAGS[f"{cat}/{fname}"] = {
                        "category": cat, "file": fname,
                        "name": f"{name[0]} ({name[1]})",
                        "summary": f"學歷：{EDU_LABEL[edu]} | 經歷：{EXP_LABEL[exp]} | 技能：{SKILL_LABEL[skill]} | 報到：{AVAIL_LABEL[avail]}",
                        "edu": edu, "exp": exp, "skill": skill, "avail": avail, "difficulty": diff,
                    }
                    idx += 1

MATCH_OPTIONS = {
    "edu": {"label": "🎓 學歷", "options": [
        {"id": "phd", "label": "博士學位", "icon": "🎓"},
        {"id": "master", "label": "碩士學位", "icon": "📚"},
        {"id": "bachelor", "label": "學士學位", "icon": "📖"},
        {"id": "highschool", "label": "中學畢業", "icon": "📝"}]},
    "exp": {"label": "💼 工作經驗", "options": [
        {"id": "7plus", "label": "7 年以上", "icon": "🌟"},
        {"id": "3to5", "label": "3-5 年", "icon": "⭐"},
        {"id": "1to3", "label": "1-3 年", "icon": "🌱"},
        {"id": "under1", "label": "1 年以下", "icon": "🆕"}]},
    "skill": {"label": "🔧 專業技能", "options": [
        {"id": "high", "label": "高", "icon": "🏆"},
        {"id": "low", "label": "低", "icon": "📘"}]},
    "avail": {"label": "📅 預計入職時間", "options": [
        {"id": "6months", "label": "半年", "icon": "🕐"},
        {"id": "1week", "label": "一周內", "icon": "⏳"},
        {"id": "tomorrow", "label": "明天早上就上班", "icon": "💨"}]},
}


class BoothManager:
    def get_options(self) -> Dict:
        cats = {k: {"label": v["label"], "icon": v["icon"], "description": v["description"]}
                for k, v in CATEGORY_META.items()}
        return {"categories": cats, "match_options": MATCH_OPTIONS}

    def get_default_jd(self, category: str) -> str:
        meta = CATEGORY_META.get(category)
        if not meta:
            raise HTTPException(400, f"Unknown category: {category}")
        return meta["default_jd"]

    def match(self, category: str, selections: Dict[str, str]) -> Dict:
        pool = {k: v for k, v in CANDIDATE_TAGS.items() if k.startswith(f"{category}/")}
        if not pool:
            raise HTTPException(404, f"No candidates for category: {category}")

        best_key = max(pool, key=lambda k: sum(
            25 if val == pool[k].get(cat) else 0
            for cat, val in selections.items()
        ))
        tags = pool[best_key]
        label_map = {"edu": EDU_LABEL, "exp": EXP_LABEL, "skill": SKILL_LABEL, "avail": AVAIL_LABEL}
        details = {}
        for cat, val in selections.items():
            tv = tags.get(cat, "")
            lm = label_map.get(cat, {})
            details[cat] = {"match": val == tv, "selected": lm.get(val, val), "candidate_value": lm.get(tv, tv)}
        score = sum(25 if val == tags.get(cat) else 0
                    for cat, val in selections.items())
        return {
            "category": category, "candidate_file": tags["file"],
            "candidate_name": tags["name"], "candidate_summary": tags["summary"],
            "match_score": score, "match_pct": score, "difficulty": tags["difficulty"],
            "match_details": details,
        }

    def random_match(self, category: str) -> Dict:
        pool = {k: v for k, v in CANDIDATE_TAGS.items() if k.startswith(f"{category}/")}
        if not pool:
            raise HTTPException(404, f"No candidates for category: {category}")
        tags = random.choice(list(pool.values()))
        return {
            "category": category, "candidate_file": tags["file"],
            "candidate_name": tags["name"], "candidate_summary": tags["summary"],
            "match_score": 100, "match_pct": 100, "difficulty": tags["difficulty"],
            "match_details": {},
        }

    def get_candidate_content(self, category: str, candidate_file: str) -> str:
        path = os.path.join(BASE_DIR, category, candidate_file)
        if not os.path.exists(path):
            raise HTTPException(404, f"Candidate not found: {category}/{candidate_file}")
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    async def screen_candidate(self, category: str, candidate_file: str, jd: str,
                               router, weights=None) -> Dict:
        path = os.path.join(BASE_DIR, category, candidate_file)
        if not os.path.exists(path):
            raise HTTPException(404, f"Candidate not found: {category}/{candidate_file}")

        tags = CANDIDATE_TAGS.get(f"{category}/{candidate_file}", {})
        logger.info(f"[BOOTH] Screening: {category}/{candidate_file} (edu={tags.get('edu')} exp={tags.get('exp')} skill={tags.get('skill')} avail={tags.get('avail')})")

        async def compute():
            t0 = time.time()
            result = await router.batch_screen_cvs(jd, [{"file_path": path, "file_name": candidate_file}], weights=weights)
            elapsed = time.time() - t0
            logger.info(f"[BOOTH] AI compute finished in {elapsed:.2f}s for {candidate_file}")
            if not result.get("screening_results") or not result["screening_results"][0].get("results"):
                raise RuntimeError("AI returned no results")
            return result

        result = await screening_cache.booth_get_or_compute(
            category, tags.get("edu", "mid"), tags.get("exp", "mid"), tags.get("skill", "mid"), jd, compute,
        )
        if "screening_results" not in result:
            logger.warning(f"[BOOTH] Using fallback scores for {candidate_file}")
            return {
                "screening_id": f"BOOTH_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "total_processed": 1, "successful": 1, "failed": 0,
                "weights_used": weights,
                "screening_results": [{"results": [dict(result)], "culture_context_used": False}],
                "errors": [],
            }
        logger.info(f"[BOOTH] Screening result ready for {candidate_file}")
        return result

    async def screen_candidate_with_text(
        self,
        category: str,
        candidate_file: str,
        cv_content: str,
        jd: str,
        router,
        weights=None
    ) -> Dict:
        try:
            result = await router.screen_single_candidate_with_text(
                jd=jd,
                cv_data={
                    "file_name": candidate_file or "modified_candidate.txt",
                    "content": cv_content
                },
                weights=weights
            )
            if isinstance(result, dict) and "scores" in result:
                return {
                    "success": True,
                    "screening_id": f"SCR_{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.urandom(3).hex()}",
                    "total_processed": 1, "successful": 1, "failed": 0,
                    "weights_used": weights or {},
                    "screening_results": [{"results": [result], "culture_context_used": False}],
                    "errors": [],
                    "cv_modified": True
                }
            elif isinstance(result, dict) and "screening_results" in result:
                return result
            else:
                return {
                    "success": True,
                    "screening_id": f"SCR_{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.urandom(3).hex()}",
                    "total_processed": 1, "successful": 1, "failed": 0,
                    "weights_used": weights or {},
                    "screening_results": [{"results": [result], "culture_context_used": False}],
                    "errors": [],
                    "cv_modified": True
                }
        except Exception as e:
            logger.error(f"Failed to screen with text: {e}")
            fallback = screening_cache.default_scores("mid", "mid", "mid").copy()
            fallback["candidate_file"] = candidate_file or "unknown"
            fallback["candidate_name"] = candidate_file or "unknown"
            return {
                "screening_id": f"BOOTH_{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.urandom(3).hex()}",
                "total_processed": 1, "successful": 1, "failed": 0,
                "weights_used": weights or {},
                "screening_results": [{"results": [fallback], "culture_context_used": False}],
                "errors": [str(e)],
                "_fallback": True,
                "cv_modified": True
            }

