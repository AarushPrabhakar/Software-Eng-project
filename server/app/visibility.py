"""
Who may see what on a FOUND report.

Everyone logged in sees only a generic title + category. The details (description,
colour, brand, location, date, photo) are shown only to:
  * the finder (owner), and admins
  * someone whose own ACTIVE lost report matches the item with score >= UNLOCK_THRESHOLD
  * someone who already has a claim on it
The finder's private_detail is NEVER shown to anyone but the finder (and the finder-side
claim screen).  Lost reports stay public, because the owner wants them to be seen.
"""
from typing import Optional

from app.database import supabase_admin
from app.matching import POSSIBLE_THRESHOLD, rank_matches

UNLOCK_THRESHOLD = POSSIBLE_THRESHOLD  # 50 = "possible" or better

CATEGORY_LABELS = {
    "backpacks_bags": "Backpack or bag",
    "water_bottles": "Water bottle or tumbler",
    "wallets_purses": "Wallet or purse",
    "earbuds_headphones": "Earbuds or headphones",
    "keys_keychains": "Keys or keychain",
    "books_notebooks": "Book or notebook",
}

HIDDEN_FIELDS = ("public_description", "private_detail", "colour", "brand", "campus_location", "event_date", "image_url")
KEEP_WHEN_HIDDEN = ("id", "report_code", "reporter_id", "report_type", "category", "status", "created_at", "updated_at")


def generic_title(report: dict) -> str:
    return f"{CATEGORY_LABELS.get(report.get('category'), 'Item')} found"


def redact(report: dict) -> dict:
    out = {k: report.get(k) for k in KEEP_WHEN_HIDDEN}
    out["title"] = generic_title(report)  # ignore the stored title: old rows may contain description text
    out["redacted"] = True
    out["access"] = "hidden"
    return out


def candidates_for(report: dict) -> list:
    opposite = "found" if report["report_type"] == "lost" else "lost"
    res = (
        supabase_admin.table("item_reports")
        .select("*")
        .eq("report_type", opposite)
        .eq("category", report["category"])
        .eq("status", "active")
        .execute()
    )
    return res.data or []


def unlocked_found(user_id: str) -> dict:
    """{found_report_id: best_score} for found items matching one of the user's active lost reports."""
    lost = (
        supabase_admin.table("item_reports")
        .select("*")
        .eq("reporter_id", user_id)
        .eq("report_type", "lost")
        .eq("status", "active")
        .execute()
    ).data or []
    out: dict = {}
    for l in lost:
        for m in rank_matches(l, candidates_for(l)):
            if m["score"] >= UNLOCK_THRESHOLD:
                fid = m["report"]["id"]
                out[fid] = max(out.get(fid, 0), m["score"])
    return out


def claimed_report_ids(user_id: str) -> set:
    rows = supabase_admin.table("claims").select("report_id").eq("claimant_id", user_id).execute().data or []
    return {r["report_id"] for r in rows}


def own_found_ids(user_id: str) -> set:
    rows = (
        supabase_admin.table("item_reports").select("id")
        .eq("reporter_id", user_id).eq("report_type", "found").execute()
    ).data or []
    return {r["id"] for r in rows}


class Viewer:
    """Computes once per request what a user is allowed to see."""

    def __init__(self, user_id: str, admin: bool):
        self.user_id = user_id
        self.admin = admin
        self.unlocked = {} if admin else unlocked_found(user_id)
        self.claimed = set() if admin else claimed_report_ids(user_id)

    def visible_found_ids(self) -> set:
        return set(self.unlocked) | self.claimed | own_found_ids(self.user_id)

    def view(self, report: dict) -> dict:
        if report.get("reporter_id") == self.user_id:
            return {**report, "redacted": False, "access": "owner"}
        public = {k: v for k, v in report.items() if k != "private_detail"}
        if report.get("report_type") == "lost":
            return {**public, "redacted": False, "access": "public"}
        if self.admin:
            return {**public, "redacted": False, "access": "admin"}
        if report["id"] in self.unlocked:
            return {**public, "redacted": False, "access": "matched", "match_score": self.unlocked[report["id"]]}
        if report["id"] in self.claimed:
            return {**public, "redacted": False, "access": "claimant"}
        return redact(report)
