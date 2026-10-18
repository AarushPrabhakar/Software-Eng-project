from datetime import datetime, timedelta, timezone

from app import handover as ho
from app.routers.claims import can_transition, _sniff_image


def test_code_is_six_digits_and_hash_is_not_the_code():
    code = ho.generate_code()
    assert len(code) == 6 and code.isdigit()
    h = ho.hash_code(code, "id-1")
    assert code not in h and len(h) == 64


def test_verify_and_binding_to_handover_id():
    h = ho.hash_code("123456", "id-1")
    assert ho.verify_code("123456", "id-1", h)
    assert not ho.verify_code("123457", "id-1", h)
    assert not ho.verify_code("123456", "id-2", h)


def test_expiry():
    past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    assert ho.is_expired(past) and not ho.is_expired(future)


def test_claim_transitions():
    assert can_transition("submitted", "under_review")
    assert can_transition("under_review", "approved")
    assert not can_transition("rejected", "approved")
    assert not can_transition("approved", "rejected")
    assert not can_transition("submitted", "submitted")


def test_image_sniffing():
    assert _sniff_image(b"\xff\xd8\xff\xe0abc") == "image/jpeg"
    assert _sniff_image(b"\x89PNG\r\n\x1a\nxxxx") == "image/png"
    assert _sniff_image(b"MZ\x90\x00 this is an exe") is None
