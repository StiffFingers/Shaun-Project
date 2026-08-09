-- Run once in Supabase → SQL Editor (existing projects).
-- Adds Action / Follow up Items on journal entries.

ALTER TABLE entries
  ADD COLUMN IF NOT EXISTS action_follow_up TEXT NOT NULL DEFAULT '';
