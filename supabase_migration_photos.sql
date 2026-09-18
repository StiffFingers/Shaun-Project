-- Run once in Supabase → SQL Editor.
-- Proof-of-work photos on journal entries (camera roll, 2–10 on NEW logs only).

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

COMMENT ON TABLE entry_photos IS 'Proof-of-work photos attached to a journal (entry_group_id)';
COMMENT ON COLUMN entries.photos_required IS 'True only for journals saved from New entry after photos launched; old logs stay false';

-- Private storage bucket. Safe to re-run.
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'journal-photos',
  'journal-photos',
  false,
  10485760,
  ARRAY['image/jpeg']::text[]
)
ON CONFLICT (id) DO NOTHING;
