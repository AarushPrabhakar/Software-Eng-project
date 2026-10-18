from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Reads SUPABASE_URL, SUPABASE_ANON_KEY, etc. from environment variables
    (or a .env file in the server/ directory). See .env.example.
    """
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    port: int = 5000
    client_url: str = "http://localhost:5173"

    # Phase 3
    handover_code_secret: str = ""      # HMAC key for hashing handover codes
    handover_ttl_hours: int = 48        # how long a handover code stays valid
    handover_max_attempts: int = 5      # wrong guesses before the code is locked
    flag_auto_hide_threshold: int = 3   # open flags before a report is auto-hidden
    max_evidence_bytes: int = 5 * 1024 * 1024

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()

if not settings.supabase_url or not settings.supabase_anon_key or not settings.supabase_service_role_key:
    print(
        "[config] Warning: one or more SUPABASE_* environment variables are missing. "
        "Copy .env.example to .env and fill in your project credentials."
    )

if not settings.handover_code_secret:
    print(
        "[config] Warning: HANDOVER_CODE_SECRET is not set; falling back to a key derived "
        "from the service-role key. Set a long random value in .env."
    )
