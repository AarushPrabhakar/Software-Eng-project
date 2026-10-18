"""One-time handover codes. Only an HMAC hash of the code is ever stored."""
import hmac
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from app.config import settings


def _key() -> bytes:
    return (settings.handover_code_secret or settings.supabase_service_role_key or "dev-only-secret").encode()


def generate_code() -> str:
    """6 digits from a cryptographically secure RNG."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_code(code: str, handover_id: str) -> str:
    # Bind the hash to the handover id so equal codes never produce equal hashes.
    return hmac.new(_key(), f"{handover_id}:{code}".encode(), hashlib.sha256).hexdigest()


def verify_code(code: str, handover_id: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_code(code.strip(), handover_id), stored_hash)


def expiry_from_now() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=settings.handover_ttl_hours)


def is_expired(expires_at) -> bool:
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= expires_at
