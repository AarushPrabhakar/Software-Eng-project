from fastapi import APIRouter, Depends, HTTPException, status
from app.database import supabase_admin
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(current_user=Depends(get_current_user)):
    res = (
        supabase_admin.table("notifications").select("*")
        .eq("user_id", current_user.id).order("created_at", desc=True).limit(50).execute()
    )
    items = res.data or []
    return {"notifications": items, "unread_count": sum(1 for n in items if not n["is_read"])}


@router.post("/read-all")
async def mark_all_read(current_user=Depends(get_current_user)):
    supabase_admin.table("notifications").update({"is_read": True}).eq("user_id", current_user.id).eq("is_read", False).execute()
    return {"ok": True}


@router.patch("/{notification_id}/read")
async def mark_read(notification_id: str, current_user=Depends(get_current_user)):
    res = (
        supabase_admin.table("notifications").update({"is_read": True})
        .eq("id", notification_id).eq("user_id", current_user.id).execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
    return {"ok": True}
