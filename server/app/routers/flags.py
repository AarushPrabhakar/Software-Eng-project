from fastapi import APIRouter, Depends, HTTPException, status
from app.config import settings
from app.database import supabase_admin
from app.dependencies import get_current_user
from app.ratelimit import limit
from app.schemas import FlagCreate
from app.services import audit, get_report_or_404

router = APIRouter(prefix="/api/flags", tags=["flags"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_flag(payload: FlagCreate, current_user=Depends(limit("flag_create", 10, 600))):
    report = get_report_or_404(payload.report_ref)
    if report["reporter_id"] == current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can't flag your own report.")

    dup = supabase_admin.table("flags").select("id").eq("report_id", report["id"]).eq("reporter_id", current_user.id).execute()
    if dup.data:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You have already flagged this report.")

    res = supabase_admin.table("flags").insert(
        {"report_id": report["id"], "reporter_id": current_user.id, "reason": payload.reason.strip()}
    ).execute()
    flag = res.data[0]

    # enough independent flags => hide the listing until an admin looks at it
    open_flags = supabase_admin.table("flags").select("id").eq("report_id", report["id"]).eq("status", "open").execute()
    hidden = False
    if len(open_flags.data or []) >= settings.flag_auto_hide_threshold and report["status"] == "active":
        supabase_admin.table("item_reports").update({"status": "flagged"}).eq("id", report["id"]).execute()
        hidden = True

    audit(current_user.id, "flag.created", "flag", flag["id"], report=report["report_code"], auto_hidden=hidden)
    return {"flag": flag, "report_hidden": hidden}
