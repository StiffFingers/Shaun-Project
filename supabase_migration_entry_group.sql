-- Run once in Supabase → SQL Editor.
-- Groups person-hour rows from one New Entry save into a single journal.

ALTER TABLE entries
  ADD COLUMN IF NOT EXISTS entry_group_id TEXT;

CREATE INDEX IF NOT EXISTS idx_entries_group ON entries(entry_group_id);
