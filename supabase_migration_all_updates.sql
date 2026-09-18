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

-- Start / finish / break (15-min steps); hours_worked is calculated total
ALTER TABLE entries
  ADD COLUMN IF NOT EXISTS start_time TEXT NOT NULL DEFAULT '';

ALTER TABLE entries
  ADD COLUMN IF NOT EXISTS finish_time TEXT NOT NULL DEFAULT '';

ALTER TABLE entries
  ADD COLUMN IF NOT EXISTS break_minutes INTEGER NOT NULL DEFAULT 0;

-- Proof-of-work photos (2–10 required on NEW journals only)
ALTER TABLE entries
  ADD COLUMN IF NOT EXISTS photos_required BOOLEAN NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS entry_photos (
    id BIGSERIAL PRIMARY KEY,
    entry_group_id TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    original_name TEXT NOT NULL DEFAULT '',
    caption TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_entry_photos_group ON entry_photos(entry_group_id);

ALTER TABLE entry_photos ENABLE ROW LEVEL SECURITY;

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'journal-photos',
  'journal-photos',
  false,
  10485760,
  ARRAY['image/jpeg']::text[]
)
ON CONFLICT (id) DO NOTHING;
