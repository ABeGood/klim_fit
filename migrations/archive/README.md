Pre-v2 migrations (users/admins, workouts with `user_id NULL` templates, `exercise_sets`).
They no longer apply: schema v2 replaced the whole data model and the live DB was wiped and
recreated from `create_tables()`. Kept for history only — do not run them.

New migrations for the v2 schema start at `migrations/004_*.sql`.
