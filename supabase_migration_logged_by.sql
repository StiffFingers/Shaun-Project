-- Run once in Supabase → SQL Editor if your project already has the entries table.
-- Adds "who filled out the form" for multi-person daily logs.

ALTER TABLE entries
  ADD COLUMN IF NOT EXISTS logged_by_worker_id BIGINT
  REFERENCES workers(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_entries_logged_by ON entries(logged_by_worker_id);
