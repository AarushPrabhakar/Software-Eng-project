from supabase import create_client, Client
from app.config import settings

# Used for operations that should respect the requesting user's own
# Row Level Security permissions (e.g. sign up, sign in).
supabase_anon: Client = create_client(settings.supabase_url, settings.supabase_anon_key)

# Used only inside trusted backend code — bypasses Row Level Security.
# Never send its raw results straight to the frontend without stripping
# sensitive fields yourself (see routers/reports.py, private_detail).
supabase_admin: Client = create_client(settings.supabase_url, settings.supabase_service_role_key)
