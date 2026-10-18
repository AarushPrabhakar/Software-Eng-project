from fastapi import APIRouter, Depends, HTTPException, status
from app.database import supabase_anon, supabase_admin
from app.dependencies import get_current_user
from app.schemas import RegisterRequest, LoginRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest):
    """
    Creates the Supabase Auth user, then creates the matching row in
    public.users. If the profile insert fails, we surface that clearly
    rather than leaving an orphaned auth user behind silently.
    """
    try:
        signup_result = supabase_anon.auth.sign_up(
            {"email": payload.email, "password": payload.password}
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    auth_user = signup_result.user
    if auth_user is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Account creation did not return a user record.",
        )

    try:
        supabase_admin.table("users").insert(
            {"id": auth_user.id, "name": payload.name, "email": payload.email}
        ).execute()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Account was created but profile setup failed. Please contact support. ({exc})",
        )

    return {
        "message": "Registration successful. Check your institutional email to confirm your account before logging in.",
        "userId": auth_user.id,
    }


@router.post("/login")
async def login(payload: LoginRequest):
    """
    Returns the Supabase session (access_token) the frontend stores and
    sends back as a Bearer token on subsequent requests.
    """
    try:
        result = supabase_anon.auth.sign_in_with_password(
            {"email": payload.email, "password": payload.password}
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password."
        )

    return {
        "session": {
            "access_token": result.session.access_token,
            "refresh_token": result.session.refresh_token,
            "expires_at": result.session.expires_at,
        },
        "user": {"id": result.user.id, "email": result.user.email},
    }


@router.post("/logout")
async def logout():
    # Stateless from the backend's point of view — Supabase sessions are
    # managed client-side — but exposed for symmetry / future server-side
    # session revocation.
    return {"message": "Logged out. Discard the session token client-side."}


@router.get("/me")
async def get_profile(current_user=Depends(get_current_user)):
    result = (
        supabase_admin.table("users")
        .select("id, name, email, role, is_verified, is_active, created_at")
        .eq("id", current_user.id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")

    return {"user": result.data[0]}
