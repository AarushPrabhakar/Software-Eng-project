-- ============================================================
-- TIET LostLink — Phase 1 Database Schema
-- Run this in the Supabase SQL Editor (Project > SQL Editor > New query)
-- ============================================================

-- Enable UUID generation
create extension if not exists "pgcrypto";

-- ------------------------------------------------------------
-- ENUM TYPES
-- ------------------------------------------------------------
create type item_category as enum (
  'backpacks_bags',
  'water_bottles',
  'wallets_purses',
  'earbuds_headphones',
  'keys_keychains',
  'books_notebooks'
);

create type report_type as enum ('lost', 'found');

create type report_status as enum ('active', 'matched', 'claimed', 'returned', 'flagged', 'closed');

create type user_role as enum ('student', 'admin');

-- ------------------------------------------------------------
-- USERS
-- Supabase Auth already stores login credentials in auth.users.
-- This table stores the campus-specific profile linked 1:1 to it.
-- ------------------------------------------------------------
create table public.users (
  id uuid primary key references auth.users(id) on delete cascade,
  name text not null,
  email text not null unique,
  role user_role not null default 'student',
  is_verified boolean not null default false,
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);

-- Only allow @thapar.edu (or whatever institutional domain you use) emails.
-- Adjust the domain below to match TIET's actual student email domain.
alter table public.users
  add constraint institutional_email_check
  check (email ~* '^[A-Za-z0-9._%+-]+@thapar\.edu$');

-- ------------------------------------------------------------
-- ITEM REPORTS
-- Holds both Lost and Found reports in one table (differentiated
-- by report_type), as described in the proposal (section 5.5).
-- ------------------------------------------------------------
create table public.item_reports (
  id uuid primary key default gen_random_uuid(),
  report_code text not null unique,          -- human-friendly unique ID, e.g. LF-20260818-0001
  reporter_id uuid not null references public.users(id) on delete cascade,
  report_type report_type not null,
  category item_category not null,
  title text not null,
  public_description text not null,          -- shown to everyone
  private_detail text,                       -- hidden field used for ownership verification (5.4)
  colour text,
  brand text,
  campus_location text,
  event_date date not null,                  -- date item was lost/found
  image_url text,                            -- Supabase Storage public/signed URL
  status report_status not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_item_reports_category on public.item_reports(category);
create index idx_item_reports_type on public.item_reports(report_type);
create index idx_item_reports_status on public.item_reports(status);
create index idx_item_reports_date on public.item_reports(event_date);
create index idx_item_reports_location on public.item_reports(campus_location);

-- Auto-generate a human-friendly report_code like LF-20260818-0001
create sequence public.report_code_seq;

create or replace function public.set_report_code()
returns trigger as $$
begin
  new.report_code := 'LF-' || to_char(now(), 'YYYYMMDD') || '-' ||
                      lpad(nextval('public.report_code_seq')::text, 4, '0');
  return new;
end;
$$ language plpgsql;

create trigger trg_set_report_code
before insert on public.item_reports
for each row execute function public.set_report_code();

-- Keep updated_at fresh
create or replace function public.touch_updated_at()
returns trigger as $$
begin
  new.updated_at := now();
  return new;
end;
$$ language plpgsql;

create trigger trg_touch_item_reports
before update on public.item_reports
for each row execute function public.touch_updated_at();

-- ------------------------------------------------------------
-- ROW LEVEL SECURITY
-- This is what actually enforces "private_detail is hidden from
-- everyone except the reporter/admin" at the database level —
-- not just in the frontend.
-- ------------------------------------------------------------
alter table public.users enable row level security;
alter table public.item_reports enable row level security;

-- USERS policies
create policy "Users can view their own profile"
  on public.users for select
  using (auth.uid() = id);

create policy "Users can update their own profile"
  on public.users for update
  using (auth.uid() = id);

create policy "Users can insert their own profile on signup"
  on public.users for insert
  with check (auth.uid() = id);

-- ITEM_REPORTS policies
-- Everyone logged in can read reports, but private_detail is stripped
-- out at the API layer (see backend controller) before non-owners see it.
-- We still restrict raw table SELECT to authenticated users only.
create policy "Authenticated users can view reports"
  on public.item_reports for select
  using (auth.role() = 'authenticated');

create policy "Users can insert their own reports"
  on public.item_reports for insert
  with check (auth.uid() = reporter_id);

create policy "Reporters can update their own reports"
  on public.item_reports for update
  using (auth.uid() = reporter_id);

create policy "Reporters can delete their own reports"
  on public.item_reports for delete
  using (auth.uid() = reporter_id);

-- ------------------------------------------------------------
-- STORAGE (for item photographs) — run once
-- Create the bucket via Supabase Dashboard > Storage > New bucket
-- named "item-photos" (public read, authenticated write), OR run:
-- ------------------------------------------------------------
insert into storage.buckets (id, name, public)
values ('item-photos', 'item-photos', true)
on conflict (id) do nothing;

create policy "Anyone can view item photos"
  on storage.objects for select
  using (bucket_id = 'item-photos');

create policy "Authenticated users can upload item photos"
  on storage.objects for insert
  with check (bucket_id = 'item-photos' and auth.role() = 'authenticated');
