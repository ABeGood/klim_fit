# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This App Is

**FitCoach** — a fitness-coaching web app. **Admins** (coaches) create workouts from an exercise library and assign them to **users** (clients). Users log in and see their assigned workouts, view exercise sets, and (eventually) mark them complete. Single-package FastAPI app, server-rendered Jinja2 templates + vanilla JS fetch calls to a JSON API. PostgreSQL (hosted on Railway).

## Commands

```bash
python app.py                              # run on http://127.0.0.1:5000
uvicorn app:app --reload --port 5000       # run with autoreload
uv sync                                    # installs the exact pinned graph from uv.lock
python db_tests.py                         # NOT pytest — seeds sample data into the DB
```

- **Deps**: `pyproject.toml` declares them, `uv.lock` pins the whole graph (35 packages), Docker builds with `uv sync --frozen`. Python 3.14. There is no `requirements.txt` — don't reintroduce one; an unpinned transitive `starlette` bump once broke prod, which is why the lock exists.
- **Deploy**: Railway autodeploys `main` from the `Dockerfile` (uvicorn on `$PORT`). Required service vars: `DATABASE_URL`, `SESSION_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`. Live at https://klimfit.up.railway.app
- VS Code: `.vscode/launch.json` has a "FastAPI (uvicorn)" debugpy config (no `--reload` — the reloader subprocess breaks breakpoints).
- API docs auto-generated at `/docs` (Swagger) and `/redoc`.
- There is **no test suite** and **no linter config**. `db_tests.py` is a manual seeding/smoke script.

## File Map (everything that matters)

| File | Role |
|------|------|
| `app.py` | ALL routes: pages, auth, Google OAuth, JSON API. ~700 lines. |
| `models.py` | Plain dataclasses: `User`, `Admin`, `Exercise`, `Workout`, `ExerciseSet`. Validation in `__post_init__`, `from_dict`/`to_dict` for DB row mapping. |
| `database_manager.py` | `DatabaseManager` class — raw SQL via psycopg2, one method per operation. Also holds `create_tables()` (the canonical schema) and bcrypt hash/verify. Module-level `db` instance at bottom. |
| `db_tests.py` | Sample-data seeder (`seed_sample_data()`, `init_database()`). |
| `migrations/*.sql` | Hand-written SQL migrations, applied **manually** (no runner, no tracking table). |
| `templates/admin/` | Admin UI: `base.html` (nav), `dashboard.html`, `users.html`, `workout_composer.html`. |
| `templates/user/` | User UI: `base.html`, `dashboard.html`. |
| `templates/` (root) | `base.html` + the auth pages: `login.html`, `signup.html`, `change_password.html`. `base.html` is only for these pre-role pages (its nav is role-aware via `session['user_type']`); role-specific pages extend `admin/base.html` or `user/base.html` instead. |
| `static/js/main.js` | Generic UI helpers (hamburger menu, flash-message close, `togglePassword`, `Utils` exported as `window.FitCoachUtils`). Feature-specific JS lives in each template's `{% block scripts %}` — except the composer. |
| `static/js/composer.js` | The workout composer app: local state + render, pointer-event drag-and-drop (mouse and touch), and a sequential background sync queue with retry. Reads `window.COMPOSER_DATA` injected by the template. |
| `static/css/style.css` | Single stylesheet, CSS variables at top (`--primary-color` etc.). |
| `todo` | Owner's known-issues/wishlist — check it before "discovering" a bug. |
| `README.md` | **Outdated** (describes the old Flask version) — do not trust it. |

## Architecture & Data Flow

```
Browser
  ├─ GET page routes  → app.py → templates/*.html (Jinja2, server-rendered)
  └─ fetch() JSON     → app.py /api/* → DatabaseManager → PostgreSQL
                                 ↑ dataclass models (models.py) in both directions
```

- No ORM. Every DB operation is a hand-written parameterized SQL string in a `DatabaseManager` method following the same template: `sql` string → `with self.get_connection() as conn` → `with conn.cursor(cursor_factory=RealDictCursor)` (for reads) → map rows through `Model.from_dict()` → log + re-raise on error. **Copy an adjacent method when adding one.**
- Each call opens a fresh connection (no pooling, despite older docs saying otherwise). `get_connection` is a contextmanager that rolls back on psycopg2 errors and always closes.
- API endpoints hand-serialize models to dicts inline (see `api_exercises`, `api_workout_exercise_sets`) — there's repeated boilerplate for exercise-set JSON in 3 places in `app.py` (GET sets, POST set, PUT set). Keep the shapes identical if you touch one.

## Auth & Session Contract

Two principal types stored in **separate tables**: `users` (clients) and `admins` (coaches). Login tries admin first, then user. Signup only creates users; admins are created via seeding/DB.

Session (Starlette signed-cookie `SessionMiddleware`) keys — set identically in password login, signup auto-login, and OAuth callback:

```python
request.session['user']       # email (presence == logged in)
request.session['user_id']    # int id in users OR admins table (per user_type)
request.session['name']       # full name for display
request.session['user_type']  # 'admin' | 'user'
request.session['profile_picture']  # only set by Google OAuth path
```

Route protection is **inconsistent by design of history** — follow the pattern of the route group you're editing:
- Page routes: inline `if 'user' not in request.session ... RedirectResponse('/login')` (admin pages also check `user_type != 'admin'`).
- API routes: call `require_admin(request)` first line (raises 401). `require_auth()` exists (raises 302-with-Location) but is barely used.
- **There is no `require_user` and no per-user ownership check on API data** — every `/api/*` endpoint is admin-only right now (see Gotchas).

Google OAuth (`authlib`): `/auth/google/login` → Google → `/auth/google/callback`. Callback matches by `google_id`, then by email (linking accounts), else creates a new user with no password. Config from `.env`: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`. The redirect URI is **derived from the live request** via `request.url_for('google_callback')` — there is no `GOOGLE_REDIRECT_URI` var (a stale one once sent production logins to `127.0.0.1`). Every host you serve from must be registered in Google Cloud Console, and uvicorn needs `--forwarded-allow-ips='*'` (set in the Dockerfile) so the derived scheme is `https` behind Railway's proxy.

Passwords: bcrypt via `DatabaseManager.hash_password/verify_password`. `password_hash` is nullable (OAuth-only accounts).

## Database Schema (source of truth: `create_tables()` in database_manager.py + migrations/)

```
users         id, name, surname, email UNIQUE, password_hash NULL, age, weight_kg,
              google_id UNIQUE NULL, profile_picture, created_at, updated_at
admins        id, name, surname, email UNIQUE, password_hash NULL,
              google_id UNIQUE NULL, profile_picture, created_at, updated_at
exercises     id, name UNIQUE, description, parameters JSONB, created_at, updated_at
workouts      id, user_id NULLABLE → users ON DELETE CASCADE (NULL = unassigned template),
              name, description, workout_date, duration_minutes, completed BOOL,
              comments JSONB '[]', created_at, updated_at
workout_sets  id, workout_id → workouts CASCADE, set_order (>0) = position of the SET
              within the workout, rest_seconds (>=0, rest AFTER the set),
              comment TEXT (coach's note to client), created_at, updated_at
exercise_sets id, workout_id → workouts CASCADE, workout_set_id → workout_sets CASCADE (nullable),
              exercise_id → exercises CASCADE, set_order (>0) = position of the exercise
              WITHIN its parent set, reps, weight_kg, duration_s, distance_m, rest_seconds,
              completed BOOL, comment TEXT (coach's note), comments JSONB '[]',
              created_at, updated_at
```

- **Workout templates (since migration 003)**: the composer creates workouts with `user_id = NULL`; `POST /api/workouts/{id}/assign` sets the client later. `get_workouts_by_user` naturally excludes templates. There's no assignment UI yet — only the endpoint.

- **Set semantics (since migration 002)**: a "set" (`workout_sets`) is an ordered *group of exercises* (superset/circuit style). An `exercise_sets` row is one exercise entry inside a set. `exercise_sets.set_order` used to order sets within a workout; it now orders entries within a set — migration 002 backfilled every pre-existing entry into its own single-exercise set.

- `updated_at` is maintained by a Postgres trigger on every table (`update_updated_at_column()`).
- **exercises.parameters JSONB** holds `{has_reps, has_weight_kg, has_duration_s, has_distance_m}` booleans. The `Exercise` dataclass flattens these to top-level fields (`from_dict` reads the JSONB, `get_parameters_dict()` packs them back for writes). An exercise must have ≥1 parameter type (validated in `__post_init__`).
- **comments JSONB** on workouts and exercise_sets: array of `{author, message, timestamp(iso)}`. Models expose `add_comment()/get_comments()`. Stored/loaded via `psycopg2.extras.Json(...)`. No UI for comments yet.
- All CHECK constraints require positive values (reps > 0 etc.) — model `__post_init__` mirrors these, so constructing a model with bad data raises `ValueError` *before* the DB is hit.

**Schema changes**: edit `create_tables()` (for fresh installs) AND add a numbered `migrations/00X_*.sql` (for the live Railway DB), then run the migration manually against `DATABASE_URL`. Follow `001_add_google_oauth.sql` style (`IF NOT EXISTS` guards).

## API Endpoints (all in app.py, all currently admin-only)

| Method & Path | Purpose |
|---|---|
| `GET /api/users` | List users (for composer dropdown) |
| `GET /api/users/{user_id}/workouts` | User's workouts (admin modal) |
| `GET /api/workouts/{workout_id}/exercise-sets` | Sets + joined exercise info |
| `GET /api/exercises` | Exercise library |
| `POST /api/workouts` | Create workout (`WorkoutCreate`; `user_id` optional → template) |
| `PUT /api/workouts/{id}` | Partial update of name/description/duration (`WorkoutUpdate`) |
| `POST /api/workouts/{id}/assign` | Assign a template to a client (`WorkoutAssign`) |
| `PUT /api/sets/{set_id}` | Update set's `rest_seconds`/`comment` (`WorkoutSetUpdate`; empty-string comment clears it) |
| `GET /api/workouts/{id}/sets` | Sets with nested `exercises` arrays (composer's read model) |
| `POST /api/workouts/{id}/sets` | Append empty set (auto `set_order`) |
| `POST /api/sets/{set_id}/duplicate` | Copy set + entries, inserted right after original (orders shifted) |
| `DELETE /api/sets/{set_id}` | Delete set (cascades to its entries) |
| `POST /api/sets/{set_id}/exercises` | Append exercise entry to a set (`ExerciseSetCreate`) |
| `POST /api/exercise-sets/{id}/duplicate` | Copy entry within its set, right after original |
| `POST /api/workouts/{id}/exercise-sets` | Legacy: append single-exercise entry (no set grouping) |
| `PUT /api/exercise-sets/{set_id}` | Partial update (`ExerciseSetUpdate`, all-optional fields; `None` = "not provided", so values can't be cleared) |
| `DELETE /api/exercise-sets/{set_id}` | Delete exercise entry |
| `DELETE /api/workouts/{workout_id}` | Delete workout (cascades to sets) |

Request bodies use the Pydantic models at the top of `app.py` (`WorkoutCreate`, `ExerciseSetCreate`, `ExerciseSetUpdate`). Responses are hand-built dicts, not Pydantic.

Page routes: `/` `/login` `/signup` `/dashboard` (redirects by user_type) `/admin/dashboard` `/admin/users` `/admin/workout-composer` `/user/dashboard` `/change_password` `/logout`, plus the OAuth pair.

## Frontend Conventions

- Templates extend `templates/admin/base.html` or `templates/user/base.html` (nav + flash messages + `main.js` include). Blocks: `{% block title %}`, `{% block content %}`, `{% block scripts %}`.
- Every page handler passes `request`, `messages: get_flash_messages(request)`, and usually `name`/`profile_picture` from session. Flash messages: `add_flash_message(request, msg, category)` where category ∈ `success|error|info` (renders as `.alert-{category}`).
- Interactivity = inline `<script>` in the template's `scripts` block using `fetch()` against `/api/*`. Icons: Font Awesome 6 (CDN). Modals: hand-rolled `.modal` divs with display toggling (see `admin/users.html`, `user/dashboard.html`).
- The composer is the exception to inline JS: `admin/workout_composer.html` injects `window.COMPOSER_DATA` (built as plain dicts in the route, rendered with `| tojson`) and loads `static/js/composer.js`. The composer builds an **unassigned template**, created as soon as a name is typed; every action is queued and synced in the background (strictly sequential ops; a failure keeps the op and its tail queued, retried on the next action or by clicking the status chip; failure toasts name the unsaved ops). **Save** validates required params (per exercise `has_*` flags), flushes the queue, and redirects; **Cancel** deletes the draft workout. Desktop layout: library left / workout right, each column scrolling independently; mobile: library docks to the bottom.
- HTML5 drag events don't fire on touch devices — the composer uses Pointer Events (long-press to lift on touch, `elementFromPoint` for drop targets). Reuse that pattern for any new drag-and-drop.

## Gotchas & Known Broken Things (verify before building on top)

1. **User workout-details modal is broken by auth**: `templates/user/dashboard.html` `viewWorkoutDetails()` fetches `/api/workouts/{id}/exercise-sets`, which calls `require_admin` → 401 for regular users. Fixing this properly means a user-accessible endpoint that also checks the workout belongs to `session['user_id']`.
2. **`markWorkoutComplete()` in user/dashboard.html is a stub** — it alerts "(API endpoint needed)". `db.mark_workout_complete(workout_id)` already exists; only the route is missing.
3. **Composer can't clear a saved numeric param**: `ExerciseSetUpdate` treats `None` as "not provided", so once reps/weight/etc. is saved it can be changed but not emptied. (Text `comment` fields CAN be cleared — an empty string is mapped to NULL.) Per-exercise `rest_seconds` still exists in the DB but is no longer shown in the composer; rest is edited at set level (`workout_sets.rest_seconds`).
4. **No reordering yet**: sets and entries can be added/duplicated/removed but not dragged to reorder; duplicates insert right after the original (server shifts `set_order` transactionally).
5. **Session secret** comes from `SESSION_SECRET` env var, falling back to the in-repo dev literal if unset — so any deployed environment MUST set it or session cookies are forgeable. No CSRF protection on forms. Known debt, not accidental.
6. **`get_workout_exercise_sets` bolts `exercise_name`/`exercise_parameters` onto `ExerciseSet` instances dynamically** (not dataclass fields) — don't rely on them existing elsewhere.
7. Duplicate alias methods exist (`get_exercise_by_id`→`get_exercise`, `get_workouts_by_user`→`get_user_workouts`, `get_exercise_sets_by_workout`→`get_workout_exercise_sets`) — kept for compatibility; prefer the alias already used in `app.py` for consistency.
8. Broad `except Exception` → flash-message-and-redirect is the standard error pattern in page routes; API routes convert to `HTTPException(500, str(e))`. Don't let `HTTPException` get swallowed — re-raise it first (existing endpoints do `except HTTPException: raise`).
9. `.env` (note: lowercase, in repo root, gitignored) needs `DATABASE_URL` + `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` (and optionally `SESSION_SECRET`). `DatabaseManager` raises at import time if `DATABASE_URL` is missing, and rewrites `postgres://` → `postgresql://` (Railway quirk).

## How to Add a Feature (recipes)

**New API endpoint**: define Pydantic request model near top of `app.py` (if it has a body) → write `async def` route calling `require_admin(request)` (or the appropriate check) → call/add a `DatabaseManager` method → return a plain dict matching sibling endpoints' shapes.

**New DB operation**: add a method to `DatabaseManager` copying the closest existing one (parameterized SQL, context managers, `RealDictCursor` + `Model.from_dict` for reads, `logger` + re-raise on error). Never interpolate values into SQL strings.

**New model field**: add to the dataclass (+ `from_dict`, `to_dict`, `__post_init__` validation) → update every `DatabaseManager` SQL touching that table (INSERT column lists, UPDATE sets) → update `create_tables()` → write a migration → update the hand-built JSON dicts in `app.py` endpoints that expose it.

**New page**: template extending the right base (`admin/` or `user/`) → route in `app.py` passing `request`, session `name`/`profile_picture`, `messages` → nav link in that base template.
