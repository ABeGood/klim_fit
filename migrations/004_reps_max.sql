-- Migration: "max" reps (AMRAP) on sets
-- Date: 2026-10-27
--
-- A set's reps target can be "max" instead of a number. When target_reps_max is true,
-- target_reps is NULL; the client logs the reps they actually did in actual_reps.

ALTER TABLE template_sets ADD COLUMN IF NOT EXISTS target_reps_max BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE workout_sets  ADD COLUMN IF NOT EXISTS target_reps_max BOOLEAN NOT NULL DEFAULT FALSE;
