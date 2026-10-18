-- ============================================================
-- Visibility patch — run ONCE in the Supabase SQL Editor.
-- Phase 1 let ANY logged-in user read every row of item_reports straight from the
-- database (including private_detail) using the public key. Now only the reporter
-- can read their own rows directly; everyone else goes through the backend, which
-- applies the "title only unless your lost report matches" rule.
-- ============================================================
drop policy if exists "Authenticated users can view reports" on public.item_reports;

create policy "Reporters can view their own reports"
  on public.item_reports for select
  using (auth.uid() = reporter_id);
