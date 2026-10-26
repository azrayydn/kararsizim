-- Run this in the Supabase SQL Editor of the PRODUCTION project (and again after any new migration
-- that creates tables).
--
-- Why: Django's tables live in Supabase's `public` schema, which Supabase also exposes through its
-- public Data API. Turning on Row Level Security (with no policies) blocks that route completely,
-- so nobody can read e.g. the user table (e-mails, password hashes) with the public API key.
-- Django itself is NOT affected: it connects as the table owner (`postgres`), which bypasses RLS.

DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', r.tablename);
  END LOOP;
END $$;

-- Check: every row should show rowsecurity = true
SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;
