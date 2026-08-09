-- Run once in Supabase → SQL Editor.
-- Start / finish / break for calculated total hours per person.

ALTER TABLE entries
  ADD COLUMN IF NOT EXISTS start_time TEXT NOT NULL DEFAULT '';

ALTER TABLE entries
  ADD COLUMN IF NOT EXISTS finish_time TEXT NOT NULL DEFAULT '';

ALTER TABLE entries
  ADD COLUMN IF NOT EXISTS break_minutes INTEGER NOT NULL DEFAULT 0;
