-- ============================================================
-- TIET LostLink — Phase 2 + 3 schema additions
-- Run ONCE in the Supabase SQL Editor, after the Phase 1 schema.sql.
--
-- Status mapping used by the app (report_status enum from Phase 1):
--   active   = Active (open, visible in feed)
--   claimed  = a claim was approved, handover pending
--   returned = handover code confirmed, item returned
--   flagged  = hidden by community flags, awaiting admin review
--   closed   = closed by owner / removed by admin
-- ============================================================

create type claim_status as enum ('submitted', 'under_review', 'approved', 'rejected', 'withdrawn');
create type flag_status  as enum ('open', 'dismissed', 'actioned');

-- ------------------------------------------------------------
-- MATCHES (cached output of the weighted matching algorithm)
-- ------------------------------------------------------------
create table public.matches (
  id uuid primary key default gen_random_uuid(),
  lost_report_id  uuid not null references public.item_reports(id) on delete cascade,
  found_report_id uuid not null references public.item_reports(id) on delete cascade,
  score integer not null check (score between 0 and 100),
  tier text not null check (tier in ('high', 'possible', 'weak')),
  breakdown jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (lost_report_id, found_report_id)
);
create index idx_matches_lost  on public.matches(lost_report_id);
create index idx_matches_found on public.matches(found_report_id);

-- ------------------------------------------------------------
-- CLAIMS
-- `answers` is written once at submission and never editable
-- (there is no update endpoint for it) -> acts as a locked,
-- timestamped record of what the claimant said.
-- ------------------------------------------------------------
create table public.claims (
  id uuid primary key default gen_random_uuid(),
  claim_code text not null unique,
  report_id    uuid not null references public.item_reports(id) on delete cascade,  -- the FOUND report
  claimant_id  uuid not null references public.users(id) on delete cascade,
  answers text not null,
  evidence_path text,                       -- path inside the PRIVATE claim-evidence bucket
  status claim_status not null default 'submitted',
  review_note text,
  reviewed_by uuid references public.users(id),
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index idx_claims_report   on public.claims(report_id);
create index idx_claims_claimant on public.claims(claimant_id);
-- A person may only have one *live* claim per report
create unique index uq_claims_one_live_per_user
  on public.claims(report_id, claimant_id)
  where status in ('submitted', 'under_review', 'approved');

create trigger trg_touch_claims
before update on public.claims
for each row execute function public.touch_updated_at();

-- ------------------------------------------------------------
-- HANDOVERS (one-time code; only the HASH is stored)
-- ------------------------------------------------------------
create table public.handovers (
  id uuid primary key,
  claim_id uuid not null unique references public.claims(id) on delete cascade,
  code_hash text not null,
  expires_at timestamptz not null,
  attempts integer not null default 0,
  used_at timestamptz,
  confirmed_by uuid references public.users(id),
  created_at timestamptz not null default now()
);

-- ------------------------------------------------------------
-- NOTIFICATIONS
-- ------------------------------------------------------------
create table public.notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  type text not null,
  message text not null,
  link text,
  is_read boolean not null default false,
  created_at timestamptz not null default now()
);
create index idx_notifications_user on public.notifications(user_id, is_read, created_at desc);

-- ------------------------------------------------------------
-- FLAGS (community moderation)
-- ------------------------------------------------------------
create table public.flags (
  id uuid primary key default gen_random_uuid(),
  report_id uuid not null references public.item_reports(id) on delete cascade,
  reporter_id uuid not null references public.users(id) on delete cascade,
  reason text not null,
  status flag_status not null default 'open',
  resolved_by uuid references public.users(id),
  resolved_at timestamptz,
  created_at timestamptz not null default now(),
  unique (report_id, reporter_id)
);
create index idx_flags_status on public.flags(status);

-- ------------------------------------------------------------
-- AUDIT LOG (claim / handover / moderation actions)
-- ------------------------------------------------------------
create table public.audit_log (
  id uuid primary key default gen_random_uuid(),
  actor_id uuid references public.users(id) on delete set null,
  action text not null,
  entity text not null,
  entity_id text not null,
  meta jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index idx_audit_created on public.audit_log(created_at desc);

-- ------------------------------------------------------------
-- ROW LEVEL SECURITY
-- The backend uses the service-role key (bypasses RLS) and does its own
-- ownership checks. These policies make sure that anyone talking to the
-- database DIRECTLY with the public anon key can see only their own rows.
-- handovers / audit_log / flags / matches get NO policies = fully locked.
-- ------------------------------------------------------------
alter table public.matches        enable row level security;
alter table public.claims         enable row level security;
alter table public.handovers      enable row level security;
alter table public.notifications  enable row level security;
alter table public.flags          enable row level security;
alter table public.audit_log      enable row level security;

create policy "Claimants can view their own claims"
  on public.claims for select using (auth.uid() = claimant_id);

create policy "Finders can view claims on their found reports"
  on public.claims for select using (
    exists (select 1 from public.item_reports r
            where r.id = claims.report_id and r.reporter_id = auth.uid())
  );

create policy "Users can view their own notifications"
  on public.notifications for select using (auth.uid() = user_id);

create policy "Users can mark their own notifications read"
  on public.notifications for update using (auth.uid() = user_id);

-- ------------------------------------------------------------
-- PRIVATE storage bucket for claim evidence (public = false!)
-- Files are only ever handed out through short-lived signed URLs
-- created by the backend after an ownership check.
-- ------------------------------------------------------------
insert into storage.buckets (id, name, public)
values ('claim-evidence', 'claim-evidence', false)
on conflict (id) do nothing;
-- (no storage.objects policies on purpose: only the service role can touch it)

-- ------------------------------------------------------------
-- To make yourself an admin for the demo (replace the email):
--   update public.users set role = 'admin' where email = 'you@thapar.edu';
-- ------------------------------------------------------------
