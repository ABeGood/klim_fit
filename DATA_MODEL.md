# FitCoach: Data Model v2 (proposal for review)

Status: **implemented** (`create_tables()` in `database_manager.py` is the source of truth). It replaced the pre-v2 schema; the live Railway DB is wiped and reseeded (`python db_tests.py reset-seed`), with no data migration.

## 1. Concepts

| Term | Meaning | Example |
|---|---|---|
| **Exercise** | Library item: the template for a set. It defines which values a set needs. | "Bench press" (reps + weight) |
| **Set** | One performance of an exercise, with targets, plus actual results on client workouts. Rest is stored per set (rest *after* the set). | press 60 kg × 10, rest 90 s |
| **Group** | An ordered group of sets that may mix exercises (straight sets, supersets, circuits). Groups have no rest of their own. | "Press × 3", or "Press + Pull-up × 3" |
| **Template** | A coach's reusable workout plan (groups → sets). It's never shown to clients and can be assigned only when `ready`. | "Upper body A" |
| **Workout** | A client's copy of a template, made on assignment. The coach can still edit it afterwards, and the client records results on it. | "Upper body A" for Anna, 2026-11-02 |

```
TEMPLATE SIDE                         CLIENT SIDE
workout_templates                     workouts ──────────── comments (chat)
 └─ template_groups      ── assign →   └─ workout_groups ── comments
     └─ template_sets      (deep copy)     └─ workout_sets ─ comments
           │                                     │
           └──────────── exercises ──────────────┘   (library, shared)
accounts: one table, role = admin | client
```

## 2. Tables

### `accounts`: replaces `users` + `admins`
| Column | Type | Notes |
|---|---|---|
| id | SERIAL PK | |
| role | TEXT NOT NULL CHECK IN ('admin','client') | |
| name, surname | VARCHAR(100) NOT NULL | |
| email | VARCHAR(255) NOT NULL | UNIQUE on `lower(email)` |
| password_hash | VARCHAR(255) NULL | NULL = Google-only account |
| google_id | VARCHAR(255) UNIQUE NULL | |
| profile_picture | TEXT | |
| age, weight_kg | INT / DECIMAL(5,2) NULL | client data; same CHECKs as today |

### `exercises`: the library
| Column | Type | Notes |
|---|---|---|
| id | SERIAL PK | |
| name | VARCHAR(200) NOT NULL UNIQUE | |
| description | TEXT | |
| has_reps, has_weight_kg, has_duration_s, has_distance_m | BOOL NOT NULL DEFAULT false | plain columns instead of JSONB; CHECK that at least one is true |
| archived_at | TIMESTAMP NULL | archived = hidden from the composer, still shown in old workouts |
| created_by | → accounts ON DELETE SET NULL | |

### Template side
**`workout_templates`**: id, `created_by` → accounts SET NULL, name NOT NULL, description, duration_minutes, note, **status** `'draft' | 'ready'` DEFAULT 'draft'

**`template_groups`**: id, `template_id` → workout_templates CASCADE, position, name NULL (an optional label like "Press"), note

**`template_sets`**: id, `group_id` → template_groups CASCADE, position, `exercise_id` → exercises **RESTRICT**, target_reps, target_weight_kg, target_duration_s, target_distance_m, **target_reps_max** ("max" reps / AMRAP; target_reps then NULL), rest_seconds, note

### Client side
**`workouts`**: id, `client_id` → accounts CASCADE, `template_id` → workout_templates SET NULL, `assigned_by` → accounts SET NULL, name NOT NULL, description, duration_minutes, note, scheduled_date DATE NULL, completed_at NULL

**`workout_groups`**: id, `workout_id` → workouts CASCADE, position, name NULL, note

**`workout_sets`**: id, `group_id` → workout_groups CASCADE, position, `exercise_id` → exercises **RESTRICT**, target_reps / target_weight_kg / target_duration_s / target_distance_m, **actual_reps / actual_weight_kg / actual_duration_s / actual_distance_m**, rest_seconds, note, **completed_at** NULL

### `comments`: coach ↔ client chat (client side only)
| Column | Type | Notes |
|---|---|---|
| id | SERIAL PK | |
| author_id | → accounts CASCADE | |
| workout_id / group_id / set_id | 3 nullable FKs (→ workouts / workout_groups / workout_sets, CASCADE) | `CHECK (num_nonnulls(workout_id, group_id, set_id) = 1)`: each comment is attached to exactly one thing |
| body | TEXT NOT NULL | |
| created_at, edited_at | TIMESTAMP | |

### Common to all tables
- `created_at`, plus `updated_at` maintained by the existing trigger.
- `position INT NOT NULL CHECK (position > 0)` with `UNIQUE (parent_id, position) DEFERRABLE INITIALLY DEFERRED`. The deferral lets a reorder swap positions inside one transaction without a temporary collision.
- Target and actual numbers are all nullable with `CHECK (> 0)`, and `rest_seconds` has `CHECK (>= 0)`.
- A set never stores a workout or template id directly; that's reached through its group.

## 3. Rules (enforced by the app/API)

1. **Composer** edits templates **and** client workouts through the same UI, using an "edit target" of `template | workout`.
2. **Assign** = one transaction that copies the template, its groups and sets into `workouts`, `workout_groups` and `workout_sets` for one client. It's allowed only if the template is `ready`, and the copy is a snapshot: later template edits don't change it.
3. **Template status**: a template starts as `draft` and becomes `ready` when you press Save, after required parameters are validated. Editing a ready template affects only future assignments.
4. **Completion is per set.** The client fills in the actual values and ticks the set, which sets `completed_at`. The workout's `completed_at` is set when its last set is completed.
5. **Freeze**: once a workout has `completed_at`, targets and structure are read-only. Comments stay open.
6. **What a client can do**: read only their own workouts; write only `actual_*` and `completed_at` on their own sets, plus comments on their own workouts.
7. **Exercises**: delete is blocked while any set uses the exercise (RESTRICT); archive it instead.
8. **Notes vs comments**: a `note` is the coach's fixed instruction. It exists on both sides and is copied on assign. `comments` are the chat, on the client side only.

## 4. What changes in the code

| Area | Change |
|---|---|
| `database_manager.py` | New `create_tables()`; all CRUD rewritten for the new tables; `assign_template()` deep copy; reorder methods |
| `models.py` | `Account`, `Exercise`, `WorkoutTemplate`, `TemplateGroup`, `TemplateSet`, `Workout`, `WorkoutGroup`, `WorkoutSet`, `Comment` |
| `app.py` | Login, signup and OAuth on `accounts` (session keys unchanged); `/api/templates/...` and `/api/workouts/...` (shared handlers); client endpoints (my workouts, complete a set, comments); `require_client` + ownership checks |
| `composer.js` + template | Edit target `template | workout`; group/set terminology; per-set rest |
| User dashboard | Workout → groups → sets view, actual-values input, per-set completion, chat |
| `db_tests.py` | Reseed: one admin, a few clients, the exercise library, sample templates and an assigned workout |
| `migrations/` | 001–003 become obsolete after the wipe. Archive them; `create_tables()` becomes the baseline and future migrations start at 004. |
| `CLAUDE.md` | Update the schema, API and auth sections |

**Rollout** (directly on `main`, which autodeploys): one commit with the schema and code together → wipe the Railway DB → run `create_tables()` + seed → verify the live app.
