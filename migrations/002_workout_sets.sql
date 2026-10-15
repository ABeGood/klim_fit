-- Migration: Introduce workout_sets (groups of exercises within a workout)
-- Date: 2026-07-14
--
-- Before: exercise_sets.set_order ordered single-exercise sets within a workout.
-- After:  workout_sets orders sets within a workout (workout_sets.set_order),
--         exercise_sets belong to a workout_set (workout_set_id) and
--         exercise_sets.set_order becomes the exercise's position WITHIN its set.

-- 1. New grouping table
CREATE TABLE IF NOT EXISTS workout_sets (
    id SERIAL PRIMARY KEY,
    workout_id INTEGER NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
    set_order INTEGER NOT NULL CHECK (set_order > 0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_workout_sets_workout_id ON workout_sets(workout_id);
CREATE INDEX IF NOT EXISTS idx_workout_sets_order ON workout_sets(workout_id, set_order);

DROP TRIGGER IF EXISTS update_workout_sets_updated_at ON workout_sets;
CREATE TRIGGER update_workout_sets_updated_at
    BEFORE UPDATE ON workout_sets
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 2. Link exercise entries to their set
ALTER TABLE exercise_sets
ADD COLUMN IF NOT EXISTS workout_set_id INTEGER REFERENCES workout_sets(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_exercise_sets_workout_set_id ON exercise_sets(workout_set_id);

-- 3. Backfill: each pre-existing exercise_set becomes its own single-exercise set,
--    preserving the old ordering.
ALTER TABLE workout_sets ADD COLUMN IF NOT EXISTS legacy_exercise_set_id INTEGER;

INSERT INTO workout_sets (workout_id, set_order, legacy_exercise_set_id)
SELECT workout_id, set_order, id
FROM exercise_sets
WHERE workout_set_id IS NULL;

UPDATE exercise_sets es
SET workout_set_id = ws.id, set_order = 1
FROM workout_sets ws
WHERE ws.legacy_exercise_set_id = es.id;

ALTER TABLE workout_sets DROP COLUMN IF EXISTS legacy_exercise_set_id;
