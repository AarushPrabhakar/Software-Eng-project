"""
Phase 3: claims -> finder review -> one-time handover code -> return confirmation.

Report status mapping:  active -> (claim approved) claimed -> (code confirmed) returned
Claim status machine :  submitted -> under_review -> approved | rejected   (+ withdrawn by claimant)
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app import handover as ho
from app.config import settings
from app.database import supabase_admin
from app.dependencies import get_current_user
from app.ratelimit import limit
from app.schemas import ClaimCreate, ClaimStatusUpdate, HandoverConfirm
from app.services import audit, get_report_or_404, is_admin, notify, one
from app.visibility import unlocked_found

router = APIRouter(prefix="/api", tags=["claims"])

LIVE = ("submitted", "under_review", "approved")

# allowed transitions: current -> set of next states
TRANSITIONS = {
    "submitted": {"under_review", "approved", "rejected", "withdrawn"},
    "under_review": {"approved", "rejected", "withdrawn"},
    "approved": set(),
    "rejected": set(),
    "withdrawn": set(),
}

ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def can_transition(current: str, new: str) -> bool:
    return new in TRANSITIONS.get(current, set())


def _sniff_image(data: bytes) -> str | None:
    """Check magic bytes so a renamed .exe can't pass as a .jpg."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _summary(report: dict) -> dict:
    return {k: report.get(k) for k in ("id", "report_code", "title", "image_url", "status", "category", "campus_location")}


def _load_claim_for(claim_id: str, user_id: str):
    """Return (claim, report, role) where role is 'claimant' | 'finder' | 'admin'. 404 for outsiders."""
    claim = one("claims", id=claim_id)
    if not claim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found.")
    report = one("item_reports", id=claim["report_id"])
    if claim["claimant_id"] == user_id:
        role = "claimant"
    elif report and report["reporter_id"] == user_id:
        role = "finder"
    elif is_admin(user_id):
        role = "admin"
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found.")
    return claim, report, role


def _signed_evidence_url(path: str | None):
    if not path:
        return None
    try:
        res = supabase_admin.storage.from_("claim-evidence").create_signed_url(path, 600)
        return res.get("signedURL") or res.get("signedUrl")
    except Exception:
        return None


def _contact(user_id: str):
    u = one("users", id=user_id)
    return {"name": u["name"], "email": u["email"]} if u else None


# ---------------------------------------------------------------- create


@router.post("/reports/{ref}/claims", status_code=status.HTTP_201_CREATED)
async def submit_claim(
    ref: str, payload: ClaimCreate, current_user=Depends(limit("claim_create", 5, 600))
):
    report = get_report_or_404(ref)
    if report["report_type"] != "found":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Claims can only be made on found-item reports.")
    if report["reporter_id"] == current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can't claim your own found report.")
    if report["status"] != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This item is no longer open for claims.")

    if report["id"] not in unlocked_found(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only claim an item that matches a lost report you filed. Report what you lost first.",
        )

    existing = (
        supabase_admin.table("claims").select("id")
        .eq("report_id", report["id"]).eq("claimant_id", current_user.id).in_("status", list(LIVE)).execute()
    )
    if existing.data:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already have an open claim on this item.")

    claim_id = str(uuid.uuid4())
    try:
        res = supabase_admin.table("claims").insert(
            {
                "id": claim_id,
                "claim_code": "CL-" + claim_id.replace("-", "")[:8].upper(),
                "report_id": report["id"],
                "claimant_id": current_user.id,
                "answers": payload.answers.strip(),
            }
        ).execute()
    except Exception:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already have an open claim on this item.")

    claim = res.data[0]
    notify(report["reporter_id"], "claim_submitted", f"New claim on your found item {report['report_code']}. Please review it.", f"/claim/{claim['id']}")
    audit(current_user.id, "claim.submitted", "claim", claim["id"], report=report["report_code"])
    return {"claim": claim}


# ---------------------------------------------------------------- lists (declared before /claims/{id})


@router.get("/claims/mine")
async def my_claims(current_user=Depends(get_current_user)):
    res = supabase_admin.table("claims").select("*").eq("claimant_id", current_user.id).order("created_at", desc=True).execute()
    out = []
    for c in res.data or []:
        r = one("item_reports", id=c["report_id"])
        out.append({**c, "report": _summary(r) if r else None})
    return {"claims": out}


@router.get("/claims/received")
async def received_claims(current_user=Depends(get_current_user)):
    mine = (
        supabase_admin.table("item_reports").select("*")
        .eq("reporter_id", current_user.id).eq("report_type", "found").execute()
    ).data or []
    if not mine:
        return {"claims": []}
    by_id = {r["id"]: r for r in mine}
    res = supabase_admin.table("claims").select("*").in_("report_id", list(by_id)).order("created_at", desc=True).execute()
    # claimant identity stays hidden until the claim is approved
    return {"claims": [{**c, "report": _summary(by_id[c["report_id"]])} for c in res.data or []]}


# ---------------------------------------------------------------- detail


@router.get("/claims/{claim_id}")
async def get_claim(claim_id: str, current_user=Depends(get_current_user)):
    claim, report, role = _load_claim_for(claim_id, current_user.id)

    out = {
        "claim": {**claim, "evidence_url": _signed_evidence_url(claim.get("evidence_path"))},
        "report": _summary(report),
        "role": role,
    }
    out["claim"].pop("evidence_path", None)

    if role in ("finder", "admin"):
        # the finder compares the claimant's answers with what only they know
        out["private_detail"] = report.get("private_detail")
    if claim["status"] == "approved":
        if role in ("finder", "admin"):
            out["contact"] = _contact(claim["claimant_id"])
        if role in ("claimant", "admin"):
            out["contact"] = _contact(report["reporter_id"])

    h = one("handovers", claim_id=claim["id"])
    if h:
        out["handover"] = {
            "id": h["id"],
            "expires_at": h["expires_at"],
            "used": h["used_at"] is not None,
            "expired": ho.is_expired(h["expires_at"]),
            "attempts_left": max(0, settings.handover_max_attempts - h["attempts"]),
        }
    return out


# ---------------------------------------------------------------- review


@router.patch("/claims/{claim_id}/status")
async def update_claim_status(
    claim_id: str, payload: ClaimStatusUpdate, current_user=Depends(get_current_user)
):
    claim, report, role = _load_claim_for(claim_id, current_user.id)
    new = payload.status

    if new == "withdrawn":
        if role != "claimant":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the claimant can withdraw a claim.")
    elif role not in ("finder", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the finder can review this claim.")

    if not can_transition(claim["status"], new):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"A {claim['status']} claim can't move to {new}.")

    if new == "approved" and report["status"] != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This item is no longer open for approval.")

    update = {"status": new}
    if new != "withdrawn":
        update.update(
            reviewed_by=current_user.id,
            reviewed_at=datetime.now(timezone.utc).isoformat(),
            review_note=payload.note,
        )
    res = supabase_admin.table("claims").update(update).eq("id", claim["id"]).execute()
    updated = res.data[0]

    link = f"/claim/{claim['id']}"
    code = report["report_code"]
    if new == "under_review":
        notify(claim["claimant_id"], "claim_update", f"Your claim on {code} is now under review.", link)
    elif new == "rejected":
        notify(claim["claimant_id"], "claim_update", f"Your claim on {code} was not approved.", link)
    elif new == "withdrawn":
        notify(report["reporter_id"], "claim_update", f"A claim on {code} was withdrawn.", link)
    elif new == "approved":
        supabase_admin.table("item_reports").update({"status": "claimed"}).eq("id", report["id"]).execute()
        # every other open claim on the same item is closed out
        others = (
            supabase_admin.table("claims").select("*")
            .eq("report_id", report["id"]).in_("status", ["submitted", "under_review"]).neq("id", claim["id"]).execute()
        ).data or []
        for o in others:
            supabase_admin.table("claims").update(
                {"status": "rejected", "review_note": "Another claim was approved for this item.", "reviewed_at": datetime.now(timezone.utc).isoformat()}
            ).eq("id", o["id"]).execute()
            notify(o["claimant_id"], "claim_update", f"Your claim on {code} was closed: another claim was approved.", f"/claim/{o['id']}")
        notify(claim["claimant_id"], "claim_approved", f"Your claim on {code} was approved! Generate your handover code to collect the item.", link)

    audit(current_user.id, f"claim.{new}", "claim", claim["id"], report=code, role=role)
    return {"claim": updated}


# ---------------------------------------------------------------- evidence (private bucket)


@router.post("/claims/{claim_id}/evidence")
async def upload_evidence(
    claim_id: str, file: UploadFile = File(...), current_user=Depends(get_current_user)
):
    claim, report, role = _load_claim_for(claim_id, current_user.id)
    if role != "claimant":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the claimant can attach evidence.")
    if claim["status"] not in ("submitted", "under_review"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Evidence can't be changed on a closed claim.")
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Evidence must be a JPG, PNG or WebP image.")

    data = await file.read(settings.max_evidence_bytes + 1)
    if len(data) > settings.max_evidence_bytes:
        raise HTTPException(status_code=413, detail="Evidence image must be 5 MB or smaller.")
    real_type = _sniff_image(data)
    if real_type != file.content_type:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="File contents don't match an allowed image type.")

    path = f"{claim['id']}/{uuid.uuid4().hex}{ALLOWED_IMAGE_TYPES[real_type]}"
    supabase_admin.storage.from_("claim-evidence").upload(path, data, {"content-type": real_type})
    supabase_admin.table("claims").update({"evidence_path": path}).eq("id", claim["id"]).execute()
    audit(current_user.id, "claim.evidence_uploaded", "claim", claim["id"], size=len(data))
    return {"ok": True}


# ---------------------------------------------------------------- handover


@router.post("/claims/{claim_id}/handover", status_code=status.HTTP_201_CREATED)
async def create_handover(claim_id: str, current_user=Depends(limit("handover_create", 5, 600))):
    """Claimant generates the one-time code. It is returned ONCE; only its hash is stored."""
    claim, report, role = _load_claim_for(claim_id, current_user.id)
    if role != "claimant":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the approved claimant can generate the handover code.")
    if claim["status"] != "approved" or report["status"] != "claimed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The claim must be approved before a handover code can be created.")

    old = one("handovers", claim_id=claim["id"])
    if old and old["used_at"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This handover has already been completed.")
    if old:  # regenerating invalidates the previous code
        supabase_admin.table("handovers").delete().eq("id", old["id"]).execute()

    handover_id = str(uuid.uuid4())
    code = ho.generate_code()
    expires = ho.expiry_from_now()
    supabase_admin.table("handovers").insert(
        {"id": handover_id, "claim_id": claim["id"], "code_hash": ho.hash_code(code, handover_id), "expires_at": expires.isoformat()}
    ).execute()

    notify(report["reporter_id"], "handover_ready", f"The claimant for {report['report_code']} is ready to collect. Ask them for their 6-digit code when you meet.", f"/claim/{claim['id']}")
    audit(current_user.id, "handover.created", "handover", handover_id, claim=claim["claim_code"])
    return {"handover_id": handover_id, "code": code, "expires_at": expires.isoformat()}


@router.post("/handovers/{handover_id}/confirm")
async def confirm_handover(
    handover_id: str, payload: HandoverConfirm, current_user=Depends(limit("handover_confirm", 10, 600))
):
    """Finder types the code the claimant shows in person. Success => report is 'returned'."""
    h = one("handovers", id=handover_id)
    if not h:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Handover not found.")
    claim = one("claims", id=h["claim_id"])
    report = one("item_reports", id=claim["report_id"])
    if report["reporter_id"] != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Handover not found.")

    if h["used_at"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This code has already been used.")
    if ho.is_expired(h["expires_at"]):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This code has expired. Ask the claimant to generate a new one.")
    if h["attempts"] >= settings.handover_max_attempts:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="Too many wrong attempts. Ask the claimant to generate a new code.")

    if not ho.verify_code(payload.code, h["id"], h["code_hash"]):
        supabase_admin.table("handovers").update({"attempts": h["attempts"] + 1}).eq("id", h["id"]).execute()
        audit(current_user.id, "handover.wrong_code", "handover", h["id"])
        left = settings.handover_max_attempts - h["attempts"] - 1
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Incorrect code. {max(left, 0)} attempt(s) left.")

    now = datetime.now(timezone.utc).isoformat()
    supabase_admin.table("handovers").update({"used_at": now, "confirmed_by": current_user.id}).eq("id", h["id"]).execute()
    supabase_admin.table("item_reports").update({"status": "returned"}).eq("id", report["id"]).execute()

    notify(claim["claimant_id"], "returned", f"Handover confirmed — {report['report_code']} is marked as returned. Glad you got it back!", f"/claim/{claim['id']}")
    audit(current_user.id, "handover.confirmed", "handover", h["id"], report=report["report_code"])
    return {"status": "returned", "report_code": report["report_code"]}
