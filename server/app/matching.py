"""
Matching v2: evidence-based scoring (explainable, pure Python, no ML dependencies).

Mandatory filters : opposite report type, same category, candidate still active, different reporter.

Score (0..100)    : category 15, colour 20, brand 20, description 25, location 10, date 10.
  Each attribute gives a SIMILARITY between 0 and 1, not just a yes/no:
    colour       colour families, so "navy" matches "blue" and "grey" is close to "black"
    brand        typo-tolerant ("Milton" ~ "Miltin" ~ "Milton steel")
    description  IDF-weighted keywords: rare words ("sticker", "dent") count more than "bottle";
                 synonyms and light stemming, so "flask" ~ "bottle" and "stickers" ~ "sticker"
    location     same place 1.0, nearby place 0.5
    date         the item can't be found before it was lost, and the score fades over ~2 weeks
  A missing field is neutral (35% of its weight) instead of counting against the report.
  A clear contradiction (two different brands, two unrelated colours, found before lost) subtracts points.

Evidence gate     : place + date alone must never unlock an item. Without at least one distinctive match
                    (brand, colour or description) the score is capped at 45; with only one it is capped at 74.
Tiers             : >= 75 high-likelihood, 60-74 possible, < 60 weak

This module has no database access so it is easy to test; see eval/ for the accuracy benchmark.
"""
import math
import re
from datetime import date, datetime
from difflib import SequenceMatcher
from typing import Dict, Optional

WEIGHTS = {"category": 15, "colour": 20, "brand": 20, "description": 25, "location": 10, "date": 10}
UNKNOWN_FRACTION = 0.35          # share of a field's weight given when either side left it blank
CONTRADICTION_PENALTY = {"brand": 12, "colour": 12, "date": 10}
HIGH_THRESHOLD = 75
POSSIBLE_THRESHOLD = 60
CAP_NO_EVIDENCE = 45
CAP_ONE_EVIDENCE = 74

STOPWORDS = frozenset(
    """a an the and or but of in on at to for with from by is are was were be been it its this that
    these those my your his her their our i me we you he she they them as has have had near
    around very some any one lost found please left small big little""".split()
)

# --- description vocabulary --------------------------------------------------------------------
SYNONYMS = {
    "flask": "bottle", "tumbler": "bottle", "sipper": "bottle", "thermos": "bottle", "bottle": "bottle",
    "backpack": "bag", "rucksack": "bag", "satchel": "bag", "sack": "bag", "bag": "bag", "pouch": "bag",
    "earphone": "earbud", "earbud": "earbud", "airpod": "earbud", "bud": "earbud", "tws": "earbud",
    "headphone": "headphone", "headset": "headphone",
    "wallet": "wallet", "purse": "wallet", "cardholder": "wallet", "billfold": "wallet",
    "key": "key", "keychain": "key", "keyring": "key", "fob": "key",
    "notebook": "book", "copy": "book", "diary": "book", "register": "book", "book": "book", "textbook": "book",
    "sticker": "sticker", "decal": "sticker",
    "scratch": "scratch", "scratched": "scratch", "scrape": "scratch",
    "dent": "dent", "dented": "dent", "crack": "crack", "cracked": "crack", "broken": "crack",
    "strap": "strap", "belt": "strap", "string": "strap",
    "zip": "zip", "zipper": "zip", "chain": "zip",
}

# --- colours -----------------------------------------------------------------------------------
COLOUR_FAMILIES = {
    "black": {"black", "jet", "charcoal"},
    "white": {"white", "cream", "ivory", "offwhite"},
    "grey": {"grey", "gray", "silver", "steel", "metallic", "ash", "chrome"},
    "blue": {"blue", "navy", "sky", "royal", "teal", "cyan", "turquoise", "indigo"},
    "red": {"red", "maroon", "crimson", "wine", "burgundy", "scarlet"},
    "green": {"green", "olive", "lime", "mint", "emerald"},
    "yellow": {"yellow", "gold", "golden", "mustard"},
    "orange": {"orange", "peach", "coral"},
    "pink": {"pink", "rose", "magenta"},
    "purple": {"purple", "violet", "lavender", "lilac"},
    "brown": {"brown", "tan", "beige", "khaki", "coffee", "camel"},
    "multi": {"multi", "multicolor", "multicolour", "colorful", "colourful", "printed", "patterned"},
}
COLOUR_OF = {w: fam for fam, words in COLOUR_FAMILIES.items() for w in words}
COLOUR_CLOSE = {
    frozenset(("black", "grey")): 0.5, frozenset(("white", "grey")): 0.4, frozenset(("brown", "orange")): 0.4,
    frozenset(("red", "pink")): 0.4, frozenset(("red", "orange")): 0.3, frozenset(("blue", "purple")): 0.3,
    frozenset(("brown", "black")): 0.3, frozenset(("yellow", "orange")): 0.3, frozenset(("white", "yellow")): 0.2,
}

# --- campus map (EDIT THIS to match the real campus) -------------------------------------------
# Places inside the same zone count as "nearby". These groupings are a starting assumption.
LOCATION_ZONES = [
    {"lt complex", "academic block 2", "central library"},
    {"hostel a", "hostel j"},
    {"sports complex", "cafeteria"},
]

NO_BRAND = {"", "none", "na", "nobrand", "unknown", "generic", "unbranded", "noname", "nil"}

_TOKEN_RE = re.compile(r"[a-z0-9]+")


# ------------------------------------------------------------------------------------------------
# text helpers
# ------------------------------------------------------------------------------------------------
def _stem(w: str) -> str:
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("es") and not w.endswith(("ses", "xes")):
        w = w[:-2] if w[:-2] in SYNONYMS else w[:-1]
    elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    return w


def tokens(text: Optional[str]) -> list:
    """Canonical keyword tokens: lower-case, stopwords dropped, stemmed, synonyms and colours folded."""
    if not text:
        return []
    out = []
    for raw in _TOKEN_RE.findall(text.lower()):
        if len(raw) <= 2 or raw in STOPWORDS:
            continue
        w = _stem(raw)
        w = SYNONYMS.get(w, w)
        w = COLOUR_OF.get(w, w)
        out.append(w)
    return out


def keywords(text: Optional[str]) -> set:
    return set(tokens(text))


def _tok_match(a: str, b: str) -> bool:
    if a == b:
        return True
    return len(a) >= 5 and len(b) >= 5 and SequenceMatcher(None, a, b).ratio() >= 0.86


def build_idf(texts: list) -> Dict[str, float]:
    """Inverse document frequency over a pool of descriptions (rare words weigh more)."""
    docs = [set(tokens(t)) for t in texts]
    n = len(docs)
    df: Dict[str, int] = {}
    for d in docs:
        for t in d:
            df[t] = df.get(t, 0) + 1
    return {t: math.log((n + 1) / (c + 0.5)) + 0.5 for t, c in df.items()}


def description_similarity(a: Optional[str], b: Optional[str], idf: Optional[Dict[str, float]] = None) -> float:
    """IDF-weighted Dice similarity of two descriptions, 0..1."""
    ta, tb = set(tokens(a)), set(tokens(b))
    if not ta or not tb:
        return 0.0
    w = (lambda t: idf.get(t, 1.0)) if idf else (lambda t: 1.0)
    wa, wb = sum(w(t) for t in ta), sum(w(t) for t in tb)
    matched, used = 0.0, set()
    for t in ta:
        for u in tb:
            if u not in used and _tok_match(t, u):
                matched += min(w(t), w(u))
                used.add(u)
                break
    return min(1.0, 2 * matched / (wa + wb))


# ------------------------------------------------------------------------------------------------
# attribute similarities (each returns 0..1, or None when a side left the field blank)
# ------------------------------------------------------------------------------------------------
def colour_similarity(a: Optional[str], b: Optional[str]) -> Optional[float]:
    fa = {COLOUR_OF[w] for w in _TOKEN_RE.findall((a or "").lower()) if w in COLOUR_OF}
    fb = {COLOUR_OF[w] for w in _TOKEN_RE.findall((b or "").lower()) if w in COLOUR_OF}
    if not fa or not fb:
        return None
    if fa & fb:
        return 1.0
    if "multi" in fa or "multi" in fb:
        return 0.4
    return max(COLOUR_CLOSE.get(frozenset((x, y)), 0.0) for x in fa for y in fb)


def _norm_brand(v: Optional[str]) -> Optional[str]:
    s = re.sub(r"[^a-z0-9]", "", (v or "").lower())
    return None if s in NO_BRAND else s


def brand_similarity(a: Optional[str], b: Optional[str]) -> Optional[float]:
    x, y = _norm_brand(a), _norm_brand(b)
    if x is None or y is None:
        return None
    if x == y:
        return 1.0
    if len(x) >= 3 and len(y) >= 3 and (x in y or y in x):
        return 0.9
    r = SequenceMatcher(None, x, y).ratio()
    return r if r >= 0.8 else r * 0.4


def location_similarity(a: Optional[str], b: Optional[str]) -> Optional[float]:
    x, y = (a or "").strip().lower(), (b or "").strip().lower()
    if not x or not y:
        return None
    if x == y:
        return 1.0
    return 0.5 if any(x in z and y in z for z in LOCATION_ZONES) else 0.0


def _to_date(v) -> Optional[date]:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str) and v:
        return date.fromisoformat(v[:10])
    return None


def date_similarity(lost_date, found_date) -> Optional[tuple]:
    """(similarity, contradiction). Found within a day of loss = 1; fades with a ~4-day half-life; zero after 2 weeks."""
    dl, df = _to_date(lost_date), _to_date(found_date)
    if not dl or not df:
        return None
    d = (df - dl).days  # days between losing it and finding it
    if d < -1:
        return 0.0, d < -2          # found before it was lost (a day of slack for sloppy dates)
    if d <= 1:
        return 1.0, False
    if d > 14:
        return 0.0, False
    return 0.5 ** ((d - 1) / 4.0), False


def tier_for(score: int) -> str:
    if score >= HIGH_THRESHOLD:
        return "high"
    if score >= POSSIBLE_THRESHOLD:
        return "possible"
    return "weak"


# ------------------------------------------------------------------------------------------------
# scoring
# ------------------------------------------------------------------------------------------------
def score_pair(a: dict, b: dict, idf: Optional[Dict[str, float]] = None) -> dict:
    """Score two report rows. Returns {score, tier, breakdown}."""
    lost, found = (a, b) if a.get("report_type") != "found" else (b, a)

    sims = {
        "colour": colour_similarity(a.get("colour"), b.get("colour")),
        "brand": brand_similarity(a.get("brand"), b.get("brand")),
        "location": location_similarity(a.get("campus_location"), b.get("campus_location")),
    }
    ds = date_similarity(lost.get("event_date"), found.get("event_date"))
    sims["date"] = ds[0] if ds else None
    text_a = f"{a.get('title') or ''} {a.get('public_description') or ''}"
    text_b = f"{b.get('title') or ''} {b.get('public_description') or ''}"
    desc = description_similarity(text_a, text_b, idf) if tokens(text_a) and tokens(text_b) else None
    sims["description"] = desc

    breakdown: Dict[str, float] = {"category": float(WEIGHTS["category"]) if a.get("category") == b.get("category") else 0.0}
    for field, s in sims.items():
        breakdown[field] = round(WEIGHTS[field] * (UNKNOWN_FRACTION if s is None else s), 1)

    penalties = 0.0
    if sims["brand"] is not None and sims["brand"] < 0.5:
        penalties += CONTRADICTION_PENALTY["brand"]
    if sims["colour"] is not None and sims["colour"] == 0.0:
        penalties += CONTRADICTION_PENALTY["colour"]
    if ds and ds[1]:
        penalties += CONTRADICTION_PENALTY["date"]
    breakdown["penalty"] = -penalties

    score = sum(breakdown.values())

    # evidence gate: place and date alone are never enough
    evidence = sum([
        sims["brand"] is not None and sims["brand"] >= 0.8,
        sims["colour"] is not None and sims["colour"] >= 0.8,
        desc is not None and desc >= 0.5,
    ])
    if evidence == 0:
        score = min(score, CAP_NO_EVIDENCE)
    elif evidence == 1:
        score = min(score, CAP_ONE_EVIDENCE)
    score = max(0, min(100, round(score)))
    breakdown["evidence"] = evidence
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
    pool = [o for o in others if is_candidate(report, o)]
    idf = build_idf([f"{report.get('title') or ''} {report.get('public_description') or ''}"] +
                    [f"{o.get('title') or ''} {o.get('public_description') or ''}" for o in pool])
    ranked = [{"report": o, **score_pair(report, o, idf)} for o in pool]
    ranked.sort(key=lambda m: m["score"], reverse=True)
    return ranked
