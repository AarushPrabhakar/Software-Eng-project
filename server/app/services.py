"""Small helpers shared by routers: single-row lookups, notifications, audit log."""
import re
from typing import Optional

from fastapi import HTTPException, status

from app.database import supabase_admin

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def one(table: str, **eq) -> Optional[dict]:
    q = supabase_admin.table(table).select("*")
    for k, v in eq.items():
        q = q.eq(k, v)
    res = q.limit(1).execute()
    return res.data[0] if res.data else None


def get_report_or_404(ref: str) -> dict:
    """Accept either the report UUID or the human report code (LF-20260914-0002)."""
    report = one("item_reports", id=ref) if UUID_RE.match(ref) else one("item_reports", report_code=ref)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    return report


def is_admin(user_id: str) -> bool:
    row = one("users", id=user_id)
    return bool(row and row.get("role") == "admin")


def notify(user_id: str, type_: str, message: str, link: Optional[str] = None) -> None:
    """Best-effort: a failed notification must never break the main action."""
    try:
        supabase_admin.table("notifications").insert(
            {"user_id": user_id, "type": type_, "message": message, "link": link}
        ).execute()
    except Exception as exc:  # pragma: no cover
        print(f"[notify] failed: {exc}")


def audit(actor_id: Optional[str], action: str, entity: str, entity_id: str, **meta) -> None:
    try:
        supabase_admin.table("audit_log").insert(
            {"actor_id": actor_id, "action": action, "entity": entity, "entity_id": str(entity_id), "meta": meta}
        ).execute()
    except Exception as exc:  # pragma: no cover
        print(f"[audit] failed: {exc}")
