from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from app.database import supabase_admin
from app.dependencies import require_admin
from app.schemas import FlagResolve
from app.services import audit, notify, one

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats")
async def stats(admin=Depends(require_admin)):
    def count(table, **eq):
        q = supabase_admin.table(table).select("id", count="exact")
        for k, v in eq.items():
            q = q.eq(k, v)
        return q.limit(1).execute().count or 0

    return {
        "reports": {
            "total": count("item_reports"),
            "active": count("item_reports", status="active"),
            "claimed": count("item_reports", status="claimed"),
            "returned": count("item_reports", status="returned"),
            "flagged": count("item_reports", status="flagged"),
        },
        "claims_total": count("claims"),
        "open_flags": count("flags", status="open"),
    }


@router.get("/flags")
async def list_flags(admin=Depends(require_admin), status_filter: str = "open"):
    res = supabase_admin.table("flags").select("*").eq("status", status_filter).order("created_at", desc=True).execute()
    out = []
    for f in res.data or []:
        r = one("item_reports", id=f["report_id"])
        out.append({**f, "report": {k: r.get(k) for k in ("id", "report_code", "title", "public_description", "report_type", "status", "image_url")} if r else None})
    return {"flags": out}


@router.patch("/flags/{flag_id}")
async def resolve_flag(flag_id: str, payload: FlagResolve, admin=Depends(require_admin)):
    flag = one("flags", id=flag_id)
    if not flag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flag not found.")
    if flag["status"] != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This flag was already resolved.")

    report = one("item_reports", id=flag["report_id"])
    new_status = "dismissed" if payload.action == "dismiss" else "actioned"
    supabase_admin.table("flags").update(
        {"status": new_status, "resolved_by": admin.id, "resolved_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", flag_id).execute()

    if report:
        if payload.action == "remove":
            supabase_admin.table("item_reports").update({"status": "closed"}).eq("id", report["id"]).execute()
            # the other open flags on this report are settled by the same decision
            supabase_admin.table("flags").update({"status": "actioned", "resolved_by": admin.id}).eq("report_id", report["id"]).eq("status", "open").execute()
            notify(report["reporter_id"], "moderation", f"Your report {report['report_code']} was removed by a moderator.", None)
        else:
            remaining = supabase_admin.table("flags").select("id").eq("report_id", report["id"]).eq("status", "open").execute()
            if report["status"] == "flagged" and not remaining.data:
                supabase_admin.table("item_reports").update({"status": "active"}).eq("id", report["id"]).execute()

    audit(admin.id, f"flag.{payload.action}", "flag", flag_id, report=report["report_code"] if report else None)
    return {"ok": True}


@router.get("/audit")
async def audit_log(admin=Depends(require_admin), limit: int = 50):
    res = supabase_admin.table("audit_log").select("*").order("created_at", desc=True).limit(min(limit, 200)).execute()
    return {"entries": res.data or []}
