-- Run this once in Supabase: Project → SQL Editor → New query → Run
-- Creates tables for the In-Spec Team Work Journal

CREATE TABLE IF NOT EXISTS workers (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS projects (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS entries (
    id BIGSERIAL PRIMARY KEY,
    entry_date DATE NOT NULL,
    worker_id BIGINT NOT NULL REFERENCES workers(id) ON DELETE RESTRICT,
    project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    logged_by_worker_id BIGINT REFERENCES workers(id) ON DELETE SET NULL,
    weather TEXT NOT NULL DEFAULT '',
    hours_worked DOUBLE PRECISION NOT NULL DEFAULT 0,
    work_done TEXT NOT NULL DEFAULT '',
    crew_notes TEXT NOT NULL DEFAULT '',
    materials_notes TEXT NOT NULL DEFAULT '',
    issues_delays TEXT NOT NULL DEFAULT '',
    safety_notes TEXT NOT NULL DEFAULT '',
    action_follow_up TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_entries_date ON entries(entry_date);
CREATE INDEX IF NOT EXISTS idx_entries_worker ON entries(worker_id);
CREATE INDEX IF NOT EXISTS idx_entries_project ON entries(project_id);

-- App uses the service_role key server-side (Streamlit secrets).
-- Keep Row Level Security off for these tables, or add policies if you enable RLS.
ALTER TABLE workers ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE entries ENABLE ROW LEVEL SECURITY;

-- Allow full access for the service role (bypasses RLS automatically).
-- For the anon key (optional), block public access by not adding open policies.
-- Service role used by Streamlit ignores RLS.

COMMENT ON TABLE workers IS 'In-Spec journal crew members';
COMMENT ON TABLE projects IS 'In-Spec job sites / projects';
COMMENT ON TABLE entries IS 'Daily work journal entries';
