-- Run this once in Supabase → SQL Editor → New query → Run
-- Safe to re-run (IF NOT EXISTS). Brings an older entries table up to date.

-- Who filled out the multi-person log form
ALTER TABLE entries
  ADD COLUMN IF NOT EXISTS logged_by_worker_id BIGINT
  REFERENCES workers(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_entries_logged_by ON entries(logged_by_worker_id);

-- Action / Follow up Items
ALTER TABLE entries
  ADD COLUMN IF NOT EXISTS action_follow_up TEXT NOT NULL DEFAULT '';

-- Temperature in °C
ALTER TABLE entries
  ADD COLUMN IF NOT EXISTS temperature_c DOUBLE PRECISION;

-- One journal id shared by all person-rows from a single New Entry save
ALTER TABLE entries
  ADD COLUMN IF NOT EXISTS entry_group_id TEXT;

CREATE INDEX IF NOT EXISTS idx_entries_group ON entries(entry_group_id);
