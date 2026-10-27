# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This App Is

**FitCoach** — a fitness-coaching web app. **Admins** (coaches) build workout **templates** from an exercise library and assign copies to **clients**. Clients log in, open their workouts, log actual results per set, tick sets done, and chat with the coach. Single-package FastAPI app, server-rendered Jinja2 templates + vanilla JS fetch calls to a JSON API. PostgreSQL (hosted on Railway).

## Commands

```bash
python app.py                              # run on http://127.0.0.1:5000
uvicorn app:app --reload --port 5000       # run with autoreload
uv sync                                    # installs the exact pinned graph from uv.lock
python db_tests.py                         # NOT pytest — interactive menu: create/drop tables, seed sample data
python db_tests.py reset-seed              # drop everything, recreate schema, seed (asks to confirm, shows the DB host)
```

- **Deps**: `pyproject.toml` declares them, `uv.lock` pins the whole graph (35 packages), Docker builds with `uv sync --frozen`. Python 3.14. There is no `requirements.txt` — don't reintroduce one; an unpinned transitive `starlette` bump once broke prod, which is why the lock exists.
- **Deploy**: Railway autodeploys `main` from the `Dockerfile` (uvicorn on `$PORT`). Required service vars: `DATABASE_URL`, `SESSION_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`. Live at https://klimfit.up.railway.app
- VS Code: `.vscode/launch.json` has a "FastAPI (uvicorn)" debugpy config (no `--reload` — the reloader subprocess breaks breakpoints).
- API docs auto-generated at `/docs` (Swagger) and `/redoc`.
- There is **no test suite** and **no linter config**. `db_tests.py` is a manual schema/seeding tool. Seeded logins: admin `admin.smith@fitcoach.com` / `124578`; clients `john.doe@email.com` / `123`, `jane.smith@email.com` / `456`, `mike.johnson@email.com` / `789`.

## File Map (everything that matters)

| File | Role |
|------|------|
| `app.py` | ALL routes: pages, auth, Google OAuth, JSON API. Pydantic request models + auth helpers at the top. |
| `models.py` | Plain dataclasses: `Account`, `Exercise`, `WorkoutTemplate`, `Workout`, `Group`, `Set`, `Comment`. Validation in `__post_init__`; shared `RowModel.from_dict`/`to_dict` (ignores unknown keys, Decimal → float). `PARAMS` = the four measurable values. |
| `database_manager.py` | `DatabaseManager` — raw SQL via psycopg2. Holds `create_tables()` (the canonical schema), `drop_tables()`, bcrypt hash/verify, and the `KINDS` table map. Module-level `db` instance at bottom. |
| `db_tests.py` | Schema/seed tool (`seed_sample_data()`, `reset_database()`, `reset-seed` CLI). |
| `migrations/` | Hand-written SQL migrations, applied **manually** (no runner, no tracking table). `archive/` holds the obsolete pre-v2 ones; v2 migrations start at `004_*.sql`. |
| `DATA_MODEL.md` | The v2 data model: concepts, tables, rules. |
| `templates/admin/` | Coach UI (side-nav shell `base.html`, active item via `nav`): `dashboard.html` (home: needs-attention cards + clients table), `users.html` (clients + workout history), `workouts.html` (every assigned workout; client/status filters kept in the URL: `?client_id=&status=todo|overdue|completed`), `_clients_table.html` (shared include), `templates.html` (list + multi-client assign panel; `?client_id=` pre-ticks a client), `exercises.html` (library: add/archive/restore), `workout_composer.html`, `workout_review.html` (a client's workout: targets vs actuals + chat panel). |
| `templates/user/` | Client UI (phone-width shell `base.html`, no nav): `dashboard.html` (In progress / Upcoming / Done), `workout.html` (the workout log). |
| `templates/_macros.html` | Jinja macros: `day()` (Today/Yesterday/…), `progress()`, `percent()`, icons. Import per template (`{% import "_macros.html" as m %}`) — includes don't see the parent's imports. |
| `templates/` (root) | `base.html` + the auth pages: `login.html`, `signup.html`, `change_password.html` — still on the old `style.css`/`main.js`. |
| `static/css/app.css` | The app stylesheet (coach + client screens): tokens on `:root` (`--accent` #2B59FF, Manrope), `ui-btn*`, `card`, `badge*`, `input`, set/log/chat/composer styles. |
| `static/js/ui.js` | Shared helpers for app screens, `window.FitCoach = {api, h, ICONS, notify, targetText, timeLabel}`; also `window.FitCoachUtils.showNotification`. Toasts go in `.flash-messages`. |
| `static/js/composer.js` | The composer app: local state + render, pointer-event drag-and-drop (mouse and touch) plus tap-to-add, group up/down reorder, live validation (Save disabled while required targets are missing), sequential background sync queue with retry. **Keyboard-first**: every field has a `data-fkey` (`s:<set lid>:<field>`, `g:<group lid>:name|note|add`, `newGroupAdd`) and `render()` restores focus by key (`focusAfterRender(key)` to move it); Enter/Shift+Enter step through fields; type-ahead `exercisePicker` boxes ("3x bench"); shortcuts ⌘/Ctrl+D (same set again), ⌘/Ctrl+Shift+X (remove), Alt+Shift+↑/↓ (move group), ⌘/Ctrl+Enter or ⌘S (save). Icon buttons are `tabindex=-1` (shortcuts cover them). Reads `window.COMPOSER_DATA`. |
| `static/js/workout.js` | Client workout log: actual-value inputs + Done tick per set (Enter → next value; Enter on a set's last value ticks it and jumps to the next unfinished set), rest timer after a ticked set, full-screen chat per set/group/workout (history.pushState, so the phone's back button closes it). Reads `window.WORKOUT_DATA`. |
| `static/js/review.js` | Coach review: groups as target-vs-done tables with targets/rest/note editable in place (each field saves on change) plus duplicate/remove per set — read-only once the workout is completed; chat panel filtered to a thread by clicking its button. Reads `window.WORKOUT_DATA`. |
| `static/js/main.js`, `static/css/style.css` | Legacy UI kit, now only used by the auth pages. `main.js` auto-adds "Loading…" spinners to every `.btn` and freezes submit buttons — never load it on app screens. |
| `todo` | Owner's known-issues/wishlist — check it before "discovering" a bug. |
| `README.md` | **Outdated** (describes the old Flask version) — do not trust it. |

## Architecture & Data Flow

```
Browser
  ├─ GET page routes  → app.py → templates/*.html (Jinja2, server-rendered)
  └─ fetch() JSON     → app.py /api/* → DatabaseManager → PostgreSQL
                                 ↑ dataclass models (models.py) in both directions
```

- No ORM. SQL lives in `DatabaseManager` methods. Simple queries go through the helpers `_fetchone` / `_fetchall` / `_execute` / `_count` (one connection + commit per call); multi-statement transactions (assign, duplicate, reorder, record result) open `self.get_connection()` themselves. Map rows through `Model.from_dict()`. Values always go through `%s` parameters; only fixed table/column names (from `KINDS` and the `*_FIELDS` whitelists) are formatted into SQL.
- **Templates and client workouts share one structure in parallel tables** (`template_groups/template_sets` vs `workout_groups/workout_sets`). Methods taking `kind` (`'templates' | 'workouts'`) pick tables from `KINDS`; the API exposes the same via `/api/{kind}/...`.
- Partial updates: `_update_sql(table, changes, allowed)` builds an UPDATE from only the keys present. API bodies are applied with `model_dump(exclude_unset=True)` (see `changes_from()`), so an absent field is untouched and an explicit `null` clears it; blank strings become NULL.
- Each call opens a fresh connection (no pooling). `get_connection` rolls back on psycopg2 errors and always closes.

## Auth & Session Contract

One `accounts` table with `role` = `'admin'` (coach) | `'client'`. Email is unique case-insensitively (`UNIQUE` index on `lower(email)`). Signup and first-time Google login create clients only; admins are created by seeding/DB.

Session (Starlette signed-cookie `SessionMiddleware`) keys — filled only by `start_session()` (password login, signup auto-login, OAuth callback):

```python
request.session['user']       # email (presence == logged in)
request.session['user_id']    # accounts.id
request.session['name']       # full name for display
request.session['user_type']  # 'admin' | 'user'   (role 'client' maps to 'user'; templates check this)
request.session['profile_picture']  # if known (Google OAuth or stored on the account)
```

Route protection:
- Page routes: inline `if not is_admin(request): RedirectResponse('/login')` (client pages check `user_type == 'user'`).
- Admin API routes: `require_admin(request)` first line (401).
- Client-accessible API routes: `get_accessible_workout(request, id)` — returns the workout for an admin or its owning client, **404** for anyone else (so other clients' ids aren't confirmed).
- Structural edits on client workouts go through `check_editable()`: 404 if missing, **409 if the workout is completed** (frozen).

Google OAuth (`authlib`): `/auth/google/login` → Google → `/auth/google/callback`. Callback matches an account by `google_id`, then by email (linking it), else creates a new client with no password. Config from `.env`: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`. The redirect URI is **derived from the live request** via `request.url_for('google_callback')` — there is no `GOOGLE_REDIRECT_URI` var (a stale one once sent production logins to `127.0.0.1`). Every host you serve from must be registered in Google Cloud Console, and uvicorn needs `--forwarded-allow-ips='*'` (set in the Dockerfile) so the derived scheme is `https` behind Railway's proxy.

Passwords: bcrypt via `DatabaseManager.hash_password/verify_password`; `db.authenticate(email, password)`. `password_hash` is nullable (OAuth-only accounts).

## Database Schema (source of truth: `create_tables()` in database_manager.py; full description in DATA_MODEL.md)

```
accounts           id, role admin|client, name, surname, email (unique lower()), password_hash NULL,
                   google_id UNIQUE NULL, profile_picture, age, weight_kg
exercises          id, name UNIQUE, description, has_reps/has_weight_kg/has_duration_s/has_distance_m BOOL
                   (CHECK ≥1 true), archived_at NULL, created_by → accounts SET NULL
workout_templates  id, created_by → accounts SET NULL, name, description, duration_minutes, note,
                   status draft|ready
template_groups    id, template_id → CASCADE, position, name NULL, note
template_sets      id, group_id → CASCADE, position, exercise_id → exercises RESTRICT,
                   target_reps/target_weight_kg/target_duration_s/target_distance_m, target_reps_max BOOL
                   ("max" reps = AMRAP; target_reps is then NULL), rest_seconds, note
workouts           id, client_id → accounts CASCADE, template_id → SET NULL, assigned_by → SET NULL,
                   name, description, duration_minutes, note, scheduled_date DATE, completed_at
workout_groups     id, workout_id → CASCADE, position, name NULL, note
workout_sets       template_sets columns + actual_reps/actual_weight_kg/actual_duration_s/actual_distance_m,
                   completed_at
comments           id, author_id → accounts CASCADE, exactly one of workout_id/group_id/set_id
                   (CHECK num_nonnulls = 1, all CASCADE), body, created_at, edited_at
```

- **Concepts**: an exercise is the template for a **set** (one performance, e.g. bench 60 kg × 10, with its own rest *after* it). A **group** is an ordered list of sets and may mix exercises (supersets); groups have no rest. Templates are never shown to clients.
- **Assign = deep copy** (`assign_template`): template + groups + sets → a new workout for a client, in one transaction. Only `ready` templates can be assigned; Save in the composer sets `ready` after `validate_structure()` passes (≥1 group, no empty group, every required `target_*` filled). Copies are snapshots — editing a template never changes assigned workouts; the coach can still edit a client's copy until it's completed.
- **Completion is per set** (`workout_sets.completed_at`). `record_set_result` refreshes `workouts.completed_at`: set when every set is done, cleared if one is unticked. A completed workout is frozen for structural edits (409); results and chat stay open.
- **Ordering**: `position > 0` with `UNIQUE (parent, position) DEFERRABLE INITIALLY DEFERRED` — shifting/swapping positions inside one transaction is fine; the check runs at commit. Deletes leave gaps (order is by position, gaps are harmless).
- **Exercises can't be deleted while used** (RESTRICT) — `archive_exercise()` hides them from the library instead; sets keep their exercise.
- **Notes vs chat**: `note` columns are the coach's fixed instructions (copied on assign). `comments` is the coach↔client chat, client side only.
- `updated_at` is maintained by a trigger on every table (`update_updated_at_column()`).
- Model `__post_init__` mirrors the CHECK constraints, so bad values raise `ValueError` (→ 400 in the API) before the DB is hit.

**Schema changes**: edit `create_tables()` (fresh installs) AND add a numbered `migrations/00X_*.sql` (004 onwards) for the live Railway DB, then run it manually against `DATABASE_URL`. Use `IF NOT EXISTS` guards.

## API Endpoints (all in app.py)

`{kind}` = `templates` | `workouts`. Admin-only unless marked.

| Method & Path | Purpose |
|---|---|
| `GET /api/exercises` | Exercise library (non-archived) |
| `GET /api/clients` | List clients |
| `GET /api/clients/{id}/workouts` | A client's workouts with set progress counts |
| `GET/POST /api/templates` | List (with counts) / create a template (`TemplateCreate`) |
| `GET/PUT/DELETE /api/templates/{id}` | Template + groups / partial update (`TemplateUpdate`; `status: 'ready'` validates first) / delete |
| `POST /api/templates/{id}/assign` | Copy a ready template to each of `client_ids` (`TemplateAssign`; all validated before any copy) → `{workout_ids}` |
| `POST /api/exercises` | Add a library exercise (`ExerciseCreate`; ≥1 `has_*`, unique name → 409) |
| `POST /api/exercises/{id}/archive` / `restore` | Hide from / return to the library |
| `DELETE /api/exercises/{id}` | Delete an exercise no set uses; in use → 409 (archive instead) |
| `GET /api/workouts/{id}` | Workout + groups — **admin or owning client** |
| `PUT/DELETE /api/workouts/{id}` | Partial update (`WorkoutUpdate`, 409 if completed) / delete |
| `PUT /api/workout-sets/{set_id}/result` | Log `actual_*` and/or `completed` — **admin or owning client** |
| `GET/POST /api/workouts/{id}/comments` | Chat: all comments in a workout / post one (`CommentCreate`; `group_id`/`set_id` optional) — **admin or owning client** |
| `POST /api/{kind}/{owner_id}/groups` | Append empty group |
| `PUT /api/{kind}/{owner_id}/groups/order` | Reorder groups (`OrderUpdate`: every id exactly once) |
| `PUT/DELETE /api/{kind}/groups/{id}` | Update name/note (`GroupUpdate`) / delete (cascades to sets) |
| `POST /api/{kind}/groups/{id}/duplicate` | Copy group + sets right after the original |
| `POST /api/{kind}/groups/{id}/sets` | Append a set of an exercise (`SetCreate`) |
| `PUT /api/{kind}/groups/{id}/sets/order` | Reorder sets within a group |
| `PUT/DELETE /api/{kind}/sets/{id}` | Partial update of targets/rest/note (`SetUpdate`; `null` clears; `target_reps_max: true` clears `target_reps`, a rep number turns max off) / delete |
| `POST /api/{kind}/sets/{id}/duplicate` | Copy set right after the original (targets, never results) |

Errors: API routes don't wrap themselves in try/except — app-level handlers map `ValueError` → 400 and `psycopg2.IntegrityError` → 409; raise `HTTPException` for 401/404/409. Responses are plain dicts (model `to_dict()` plus extras), encoded by FastAPI.

Page routes: `/` `/login` `/signup` `/dashboard` (redirects by role) `/admin/dashboard` `/admin/users` `/admin/workouts` `/admin/templates` `/admin/exercises` `/admin/workout-composer` (`?template_id=` / `?workout_id=` to edit; none = new template) `/workouts/{id}` (coach or owning client) `/user/dashboard` `/change_password` `/logout`, plus the OAuth pair.

## Frontend Conventions

- Templates extend `templates/admin/base.html` or `templates/user/base.html` (nav + flash messages + `main.js` include). Blocks: `{% block title %}`, `{% block content %}`, `{% block scripts %}`.
- Every logged-in page handler builds its context with `page_context(request, **extra)` (request, session `name`/`profile_picture`, flash `messages`). Flash messages: `add_flash_message(request, msg, category)` where category ∈ `success|error|info`.
- Data handed to page JS (`COMPOSER_DATA`, `WORKOUT_DATA`) must go through `jsonable_encoder()` before `| tojson` — Jinja's `tojson` can't serialise dates.
- Interactivity = `FitCoach.api()` against `/api/*`; build DOM with `FitCoach.h()` (text children are text nodes, so user content is never parsed as HTML; `html:` is only for the static `ICONS`). Icons are inline stroke SVGs (no icon font on app screens). Buttons/links use `ui-btn` classes, not `.btn`.
- **Composer** (`composer.js`): no target = builds a **new template**, created as soon as a name is typed; `?template_id=` / `?workout_id=` loads an existing template / client workout (`target.kind` picks the API). Every action is queued and synced in the background (strictly sequential ops; a failure keeps the op and its tail queued, retried on the next action or by clicking the status chip). **Save** validates required params, flushes the queue, and (templates) marks the template `ready`; **Cancel** deletes a template created in this session, or is **Back** when editing an existing one. Desktop: library left / workout right, each column scrolling independently; mobile: library docks to the bottom.
- **`/workouts/{id}`** renders two different screens from the same data: `user/workout.html` (client log) or `admin/workout_review.html` (coach review). Ticking a set with empty inputs logs the targets ("done as planned").
- HTML5 drag events don't fire on touch devices — the composer uses Pointer Events (long-press to lift on touch, `elementFromPoint` for drop targets). Reuse that pattern for any new drag-and-drop.

## Gotchas & Known Broken Things (verify before building on top)

1. **Reordering**: groups move with up/down buttons in the composer; sets within a group can't be reordered in the UI yet (the endpoint exists). Duplicates insert right after the original.
2. **"Needs attention" has no read tracking**: a thread counts as unanswered while its latest message is from the client; overdue = unfinished with a past `scheduled_date`; "no plan" = no unfinished workout.
3. **Session secret** comes from `SESSION_SECRET`, falling back to the in-repo dev literal if unset — any deployed environment MUST set it or session cookies are forgeable. No CSRF protection on forms or the JSON API. Known debt, not accidental.
4. **Editing a ready template doesn't re-validate until Save** — a coach can leave a ready template half-edited; `assign` re-validates server-side, so a broken template can't be assigned.
5. Broad `except Exception` → flash-message-and-redirect is the standard error pattern in page routes. API routes rely on the app-level exception handlers instead.
6. `.env` (repo root, gitignored) needs `DATABASE_URL` + `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` (and optionally `SESSION_SECRET`). `DatabaseManager` raises at import time if `DATABASE_URL` is missing, and rewrites `postgres://` → `postgresql://` (Railway quirk).

## How to Add a Feature (recipes)

**New API endpoint**: define a Pydantic request model near the top of `app.py` (if it has a body) → `async def` route starting with `require_admin(request)` or `get_accessible_workout(...)` → call/add a `DatabaseManager` method → return a plain dict. For partial updates use `changes_from(body)` and a `*_FIELDS` whitelist.

**New DB operation**: add a method to `DatabaseManager`; use the `_fetchone/_fetchall/_execute` helpers for single statements, an explicit `get_connection()` block for transactions. Parameterize every value. If it works on groups/sets, take `kind` and use `KINDS[kind]`.

**New model field**: add to the dataclass (+ `__post_init__` validation) → `create_tables()` + a migration → the INSERT/UPDATE SQL and any `*_FIELDS` whitelist → the Pydantic request model if editable.

**New page**: template extending the right base (`admin/` or `user/`) → route in `app.py` using `page_context(request, ...)` → nav link in that base template.
