"""
Weighted matching (proposal sections 5.1 / 5.2).

Mandatory filters : opposite report type, same category, candidate still active.
Score (max 100)   : category 30 + brand 15 + colour 15 + location 15
                    + date within 3 days 15 + description keyword overlap 10
Tiers             : >= 75 high-likelihood, 50-74 possible, < 50 weak

This module is pure Python (no database access) so it is easy to unit test.
"""
import re
from datetime import date, datetime
from typing import Optional

WEIGHTS = {"category": 30, "brand": 15, "colour": 15, "location": 15, "date": 15, "description": 10}
DATE_WINDOW_DAYS = 3
HIGH_THRESHOLD = 75
POSSIBLE_THRESHOLD = 50

STOPWORDS = frozenset(
    """a an the and or but of in on at to for with from by is are was were be been it its this that
    these those my your his her their our i me we you he she they them as has have had near
    around very some any one lost found please left""".split()
)


def keywords(text: Optional[str]) -> set:
    """lower-case, strip punctuation, drop stopwords and 1-2 letter tokens."""
    if not text:
        return set()
    cleaned = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return {w for w in cleaned.split() if len(w) > 2 and w not in STOPWORDS}


def description_similarity(a: Optional[str], b: Optional[str]) -> float:
    """Share of keywords in common, relative to the shorter description (0..1)."""
    ka, kb = keywords(a), keywords(b)
    if not ka or not kb:
        return 0.0
    return len(ka & kb) / min(len(ka), len(kb))


def _same(a: Optional[str], b: Optional[str]) -> bool:
    return bool(a) and bool(b) and a.strip().lower() == b.strip().lower()


def _to_date(v) -> Optional[date]:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str) and v:
        return date.fromisoformat(v[:10])
    return None


def tier_for(score: int) -> str:
    if score >= HIGH_THRESHOLD:
        return "high"
    if score >= POSSIBLE_THRESHOLD:
        return "possible"
    return "weak"


def score_pair(a: dict, b: dict) -> dict:
    """Score two report rows. Returns {score, tier, breakdown}."""
    breakdown = {
        "category": WEIGHTS["category"] if a.get("category") == b.get("category") else 0,
        "brand": WEIGHTS["brand"] if _same(a.get("brand"), b.get("brand")) else 0,
        "colour": WEIGHTS["colour"] if _same(a.get("colour"), b.get("colour")) else 0,
        "location": WEIGHTS["location"] if _same(a.get("campus_location"), b.get("campus_location")) else 0,
        "date": 0,
        "description": 0,
    }
    da, db = _to_date(a.get("event_date")), _to_date(b.get("event_date"))
    if da and db and abs((da - db).days) <= DATE_WINDOW_DAYS:
        breakdown["date"] = WEIGHTS["date"]
    sim = description_similarity(
        f"{a.get('title') or ''} {a.get('public_description') or ''}",
        f"{b.get('title') or ''} {b.get('public_description') or ''}",
    )
    breakdown["description"] = round(WEIGHTS["description"] * sim)
    score = min(100, sum(breakdown.values()))
    return {"score": score, "tier": tier_for(score), "breakdown": breakdown}


def is_candidate(report: dict, other: dict) -> bool:
    """Mandatory filters."""
    return (
        other.get("id") != report.get("id")
        and other.get("report_type") != report.get("report_type")
        and other.get("category") == report.get("category")
        and other.get("status") == "active"
        and other.get("reporter_id") != report.get("reporter_id")
    )


def rank_matches(report: dict, others: list) -> list:
    """Filter + score + sort (best first). Each item: {report, score, tier, breakdown}."""
    ranked = []
    for other in others:
        if not is_candidate(report, other):
            continue
        ranked.append({"report": other, **score_pair(report, other)})
    ranked.sort(key=lambda m: m["score"], reverse=True)
    return ranked
