from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.database import supabase_admin
from app.dependencies import get_current_user
from app.matching import HIGH_THRESHOLD, rank_matches
from app.schemas import ReportCreate, ReportStatusUpdate
from app.services import get_report_or_404, is_admin, notify
from app.visibility import UNLOCK_THRESHOLD, Viewer, candidates_for, generic_title

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _public(report: dict) -> dict:
    """A report as seen by anyone other than its owner."""
    return {k: v for k, v in report.items() if k != "private_detail"}


def _notify_new_matches(report: dict) -> None:
    """
    After a report is created: cache matches, then notify.
      * the LOST owner is told "an item that could be yours was found" when score >= 50
      * the FOUND owner is told someone may be looking for it when score >= 75
    The notification never contains the found item's details, only a generic title.
    """
    ranked = rank_matches(report, candidates_for(report))
    rows = []
    for m in ranked:
        lost, found = (report, m["report"]) if report["report_type"] == "lost" else (m["report"], report)
        rows.append(
            {
                "lost_report_id": lost["id"],
                "found_report_id": found["id"],
                "score": m["score"],
                "tier": m["tier"],
                "breakdown": m["breakdown"],
            }
        )
    if rows:
        supabase_admin.table("matches").upsert(rows, on_conflict="lost_report_id,found_report_id").execute()
    for m in ranked:
        lost, found = (report, m["report"]) if report["report_type"] == "lost" else (m["report"], report)
        if m["score"] >= UNLOCK_THRESHOLD:
            notify(
                lost["reporter_id"], "match",
                f"An item that could be yours was found: {generic_title(found)} ({found['report_code']}). Open it to see the details.",
                f"/item/{found['report_code']}",
            )
        if m["score"] >= HIGH_THRESHOLD:
            notify(
                found["reporter_id"], "match",
                f"Someone may be looking for the item you found ({found['report_code']}).",
                f"/item/{found['report_code']}",
            )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_report(payload: ReportCreate, current_user=Depends(get_current_user)):
    data = payload.model_dump(mode="json")
    data["reporter_id"] = current_user.id

    result = supabase_admin.table("item_reports").insert(data).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create report."
        )

    report = result.data[0]
    try:
        _notify_new_matches(report)
    except Exception as exc:  # matching must never break report creation
        print(f"[matching] skipped: {exc}")

    # Don't echo private_detail back even to the owner on create — the
    # frontend already has what it just submitted locally.
    report.pop("private_detail", None)
    return {"report": report}


@router.get("")
async def list_reports(
    current_user=Depends(get_current_user),
    category: Optional[str] = None,
    report_type: Optional[str] = None,
    status_: Optional[str] = Query("active", alias="status"),
    colour: Optional[str] = None,
    brand: Optional[str] = None,
    campus_location: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
):
    """
    Returns the public feed, with search/filtering. private_detail is
    always stripped unless the requester is the report's own reporter.
    """
    viewer = Viewer(current_user.id, is_admin(current_user.id))

    def build(rtype_override=None, exclude_found=False, only_ids=None):
        q = supabase_admin.table("item_reports").select("*", count="exact")
        rt = rtype_override or report_type
        if category:
            q = q.eq("category", category)
        if rt:
            q = q.eq("report_type", rt)
        if exclude_found:
            q = q.neq("report_type", "found")
        if only_ids is not None:
            q = q.in_("id", list(only_ids))
        if status_:
            q = q.eq("status", status_)
        if colour:
            q = q.ilike("colour", f"%{colour}%")
        if brand:
            q = q.ilike("brand", f"%{brand}%")
        if campus_location:
            q = q.ilike("campus_location", f"%{campus_location}%")
        if date_from:
            q = q.gte("event_date", str(date_from))
        if date_to:
            q = q.lte("event_date", str(date_to))
        if search:
            q = q.or_(f"title.ilike.%{search}%,public_description.ilike.%{search}%")
        return q

    hidden_filters = any([colour, brand, campus_location, date_from, date_to, search])
    start = (page - 1) * page_size
    end = start + page_size - 1

    if hidden_filters and not viewer.admin and report_type != "lost":
        # Filtering on colour/brand/location/date/text must never reveal hidden found items
        # (otherwise "?colour=blue" would work as an oracle). So: lost reports normally,
        # found reports only among the ones this user is already allowed to see.
        rows = []
        if report_type != "found":
            rows += build(exclude_found=True).execute().data or []
        visible = viewer.visible_found_ids()
        if visible and report_type in (None, "", "found"):
            rows += build(rtype_override="found", only_ids=visible).execute().data or []
        rows.sort(key=lambda r: r["created_at"], reverse=True)
        total = len(rows)
        rows = rows[start:end + 1]
    else:
        result = build().order("created_at", desc=True).range(start, end).execute()
        rows, total = result.data or [], result.count

    return {
        "reports": [viewer.view(r) for r in rows],
        "pagination": {"page": page, "page_size": page_size, "total": total},
    }


@router.get("/mine")
async def list_my_reports(current_user=Depends(get_current_user)):
    """The current user's own reports — private_detail included, since it's theirs."""
    result = (
        supabase_admin.table("item_reports")
        .select("*")
        .eq("reporter_id", current_user.id)
        .order("created_at", desc=True)
        .execute()
    )
    return {"reports": result.data or []}


@router.get("/{ref}")
async def get_report(ref: str, current_user=Depends(get_current_user)):
    """`ref` can be the UUID or the report code (e.g. LF-20260914-0002)."""
    report = get_report_or_404(ref)
    viewer = Viewer(current_user.id, is_admin(current_user.id))
    return {"report": viewer.view(report)}


@router.get("/{ref}/matches")
async def get_matches(ref: str, current_user=Depends(get_current_user)):
    """
    Ranked possible matches for a report. Only the report's owner (or an admin)
    can ask — matches are a tool for the person doing the searching.
    Candidates are returned WITHOUT private_detail.
    """
    report = get_report_or_404(ref)
    if report["reporter_id"] != current_user.id and not is_admin(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the report owner can view its matches.")

    ranked = rank_matches(report, candidates_for(report))
    if report["report_type"] == "lost":
        # found items below the unlock threshold stay hidden even from this list
        ranked = [m for m in ranked if m["score"] >= UNLOCK_THRESHOLD]
    ranked = ranked[:10]
    return {
        "report_code": report["report_code"],
        "matches": [
            {"report": {**_public(m["report"]), "redacted": False}, "score": m["score"], "tier": m["tier"], "breakdown": m["breakdown"]}
            for m in ranked
        ],
    }


@router.patch("/{ref}/status")
async def update_report_status(
    ref: str, payload: ReportStatusUpdate, current_user=Depends(get_current_user)
):
    """
    Owner can re-open or close their own report. Statuses that represent the claim
    lifecycle (claimed / returned) can only be set by the claims & handover flow,
    and a flagged report stays hidden until an admin reviews it.
    """
    report = get_report_or_404(ref)
    if report["reporter_id"] != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found or you do not own it.")
    if payload.status not in ("active", "closed"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You can only set a report to 'active' or 'closed'.")
    if report["status"] in ("claimed", "returned", "flagged"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"A {report['status']} report can't be changed manually.")

    result = (
        supabase_admin.table("item_reports").update({"status": payload.status}).eq("id", report["id"]).execute()
    )
    return {"report": result.data[0]}
