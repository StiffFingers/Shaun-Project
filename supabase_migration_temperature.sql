-- Run once in Supabase → SQL Editor (existing projects).
-- Adds temperature (°C) on journal entries.

ALTER TABLE entries
  ADD COLUMN IF NOT EXISTS temperature_c DOUBLE PRECISION;
