-- Migration: Workout templates + set-level rest/comment + entry comment
-- Date: 2026-07-15
--
-- 1. Workouts are no longer bound to a client at creation: user_id becomes
--    nullable. A workout with user_id IS NULL is a template awaiting assignment.
-- 2. workout_sets gets rest_seconds (rest after the set) and comment (note to client).
-- 3. exercise_sets gets comment (note to client for that exercise).

ALTER TABLE workouts ALTER COLUMN user_id DROP NOT NULL;

ALTER TABLE workout_sets
ADD COLUMN IF NOT EXISTS rest_seconds INTEGER CHECK (rest_seconds >= 0),
ADD COLUMN IF NOT EXISTS comment TEXT;

ALTER TABLE exercise_sets
ADD COLUMN IF NOT EXISTS comment TEXT;
