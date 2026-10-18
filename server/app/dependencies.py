from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database import supabase_admin

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    """
    FastAPI dependency that verifies the Supabase-issued JWT sent from the
    frontend as `Authorization: Bearer <token>`, and returns the resolved
    Supabase user object. Attach this with `Depends(get_current_user)` on
    any route that should require login.

    The frontend gets this token automatically from Supabase Auth after
    login (supabase.auth.getSession()).
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
        )

    token = credentials.credentials
    try:
        response = supabase_admin.auth.get_user(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please log in again.",
        )

    if response is None or response.user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please log in again.",
        )

    return response.user  # has .id, .email, etc.


async def require_admin(current_user=Depends(get_current_user)):
    """
    Gate for admin-only routes (moderation, audit log).
    """
    result = (
        supabase_admin.table("users")
        .select("role")
        .eq("id", current_user.id)
        .limit(1)
        .execute()
    )
    if not result.data or result.data[0].get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )
    return current_user
