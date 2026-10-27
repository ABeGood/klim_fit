from fastapi import FastAPI, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.encoders import jsonable_encoder
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from database_manager import DatabaseManager
from models import Account, Exercise, WorkoutTemplate, Comment
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import date
import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv('SESSION_SECRET', 'your-secret-key-change-this-in-production')
)

# Initialize OAuth
oauth = OAuth()
oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# Initialize database manager
db = DatabaseManager()

# Setup templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# ============ Dev live reload (DEV_RELOAD=1 only) ============
# Pages poll /__dev/version: a CSS change swaps stylesheets in place, a template/JS change reloads the page.
DEV_RELOAD = os.getenv('DEV_RELOAD') == '1'
templates.env.globals['dev_reload'] = DEV_RELOAD

def _latest_mtime(*dirs: str) -> float:
    return max((os.path.getmtime(os.path.join(root, f))
                for d in dirs for root, _, files in os.walk(d) for f in files), default=0)

if DEV_RELOAD:
    @app.get('/__dev/version', include_in_schema=False)
    async def dev_version():
        return {'css': _latest_mtime('static/css'), 'page': _latest_mtime('templates', 'static/js')}

    # Without this the browser may keep running a cached old JS file after a reload
    @app.middleware('http')
    async def dev_no_cache(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith('/static/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

# ============ API error mapping ============
# API routes don't wrap themselves in try/except: model validation errors (ValueError) become 400,
# constraint violations 409, anything else the default 500. Page routes still catch their own errors.
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={'detail': str(exc)})

@app.exception_handler(psycopg2.IntegrityError)
async def integrity_error_handler(request: Request, exc: psycopg2.IntegrityError):
    return JSONResponse(status_code=409, content={'detail': exc.pgerror or str(exc)})

# ============ Pydantic request models ============
# Update bodies are applied with model_dump(exclude_unset=True): a field that is absent is left alone,
# an explicit null clears it.
POSITIVE_INT = Field(None, gt=0)
POSITIVE_FLOAT = Field(None, gt=0)

class Kind(str, Enum):
    templates = 'templates'
    workouts = 'workouts'

class TemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    duration_minutes: Optional[int] = POSITIVE_INT
    note: Optional[str] = None

class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = POSITIVE_INT
    note: Optional[str] = None
    status: Optional[str] = None

class TemplateAssign(BaseModel):
    client_ids: List[int] = Field(min_length=1)  # each client gets their own copy
    scheduled_date: Optional[date] = None

class ExerciseCreate(BaseModel):
    name: str
    description: Optional[str] = None
    has_reps: bool = False
    has_weight_kg: bool = False
    has_duration_s: bool = False
    has_distance_m: bool = False

class WorkoutUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = POSITIVE_INT
    note: Optional[str] = None
    scheduled_date: Optional[date] = None

class GroupUpdate(BaseModel):
    name: Optional[str] = None
    note: Optional[str] = None

class SetCreate(BaseModel):
    exercise_id: int

class SetUpdate(BaseModel):
    target_reps: Optional[int] = POSITIVE_INT
    target_reps_max: Optional[bool] = None  # true = "max" reps (clears target_reps); a rep number turns it off
    target_weight_kg: Optional[float] = POSITIVE_FLOAT
    target_duration_s: Optional[int] = POSITIVE_INT
    target_distance_m: Optional[float] = POSITIVE_FLOAT
    rest_seconds: Optional[int] = Field(None, ge=0)
    note: Optional[str] = None

class SetResult(BaseModel):
    actual_reps: Optional[int] = POSITIVE_INT
    actual_weight_kg: Optional[float] = POSITIVE_FLOAT
    actual_duration_s: Optional[int] = POSITIVE_INT
    actual_distance_m: Optional[float] = POSITIVE_FLOAT
    completed: Optional[bool] = None

class OrderUpdate(BaseModel):
    ids: List[int]

class CommentCreate(BaseModel):
    body: str
    group_id: Optional[int] = None  # neither group_id nor set_id = comment on the whole workout
    set_id: Optional[int] = None

def changes_from(body: BaseModel, name_required: bool = False) -> dict:
    """Fields the caller actually sent; blank text clears the value. name_required: a blank `name`
    is rejected (templates, workouts, exercises) -- group names are optional and may be cleared."""
    changes = body.model_dump(exclude_unset=True)
    for key, value in changes.items():
        if isinstance(value, str):
            changes[key] = value.strip() or None
    if name_required and 'name' in changes and not changes['name']:
        raise HTTPException(status_code=400, detail='Name cannot be empty')
    return changes

# ============ Helpers: flash messages, session, auth ============
def get_flash_messages(request: Request):
    return request.session.pop('_flash_messages', [])

def add_flash_message(request: Request, message: str, category: str = 'info'):
    if '_flash_messages' not in request.session:
        request.session['_flash_messages'] = []
    request.session['_flash_messages'].append({'message': message, 'category': category})

def start_session(request: Request, account: Account, profile_picture: Optional[str] = None):
    """The one place the session is filled (password login, signup, Google OAuth)"""
    request.session['user'] = account.email
    request.session['user_id'] = account.id
    request.session['name'] = account.full_name
    request.session['user_type'] = 'admin' if account.is_admin else 'user'
    picture = profile_picture or account.profile_picture
    if picture:
        request.session['profile_picture'] = picture

def is_admin(request: Request) -> bool:
    return 'user' in request.session and request.session.get('user_type') == 'admin'

def require_admin(request: Request):
    if not is_admin(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized')

def require_login(request: Request):
    if 'user' not in request.session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized')

def page_context(request: Request, **extra):
    """Context every logged-in page template needs"""
    return dict(request=request, name=request.session.get('name'),
                profile_picture=request.session.get('profile_picture'),
                messages=get_flash_messages(request), **extra)

def get_accessible_workout(request: Request, workout_id: int):
    """The workout if the caller is an admin or the client who owns it; 404 otherwise
    (404 rather than 403 so ids of other clients' workouts aren't confirmed)"""
    require_login(request)
    workout = db.get_workout(workout_id)
    if not workout or (not is_admin(request) and workout.client_id != request.session.get('user_id')):
        raise HTTPException(status_code=404, detail='Workout not found')
    return workout

def check_editable(kind: Kind, owner_id: Optional[int]):
    """404 if the template/workout doesn't exist; 409 if it's a completed (frozen) workout"""
    if owner_id is None:
        raise HTTPException(status_code=404, detail='Not found')
    if kind == Kind.templates:
        if not db.get_template(owner_id):
            raise HTTPException(status_code=404, detail='Template not found')
    else:
        workout = db.get_workout(owner_id)
        if not workout:
            raise HTTPException(status_code=404, detail='Workout not found')
        if workout.completed:
            raise HTTPException(status_code=409, detail='Workout is completed and can no longer be edited')

def exercise_dict(exercise) -> dict:
    return {
        'id': exercise.id,
        'name': exercise.name,
        'description': exercise.description or '',
        'has_reps': exercise.has_reps,
        'has_weight_kg': exercise.has_weight_kg,
        'has_duration_s': exercise.has_duration_s,
        'has_distance_m': exercise.has_distance_m
    }

# ============ Auth pages ============
@app.get('/', response_class=RedirectResponse)
async def index(request: Request):
    if 'user' in request.session:
        return RedirectResponse(url='/dashboard', status_code=status.HTTP_302_FOUND)
    return RedirectResponse(url='/login', status_code=status.HTTP_302_FOUND)

@app.get('/login', response_class=HTMLResponse)
async def login_get(request: Request):
    return templates.TemplateResponse(request, 'login.html', {
        'request': request,
        'messages': get_flash_messages(request)
    })

@app.post('/login', response_class=RedirectResponse)
async def login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    try:
        account = db.authenticate(email, password)
        if account:
            start_session(request, account)
            add_flash_message(request, 'Login successful!', 'success')
            return RedirectResponse(url='/dashboard', status_code=status.HTTP_302_FOUND)

        add_flash_message(request, 'Invalid email or password!', 'error')

    except Exception as e:
        add_flash_message(request, 'Login error occurred. Please try again.', 'error')

    return RedirectResponse(url='/login', status_code=status.HTTP_302_FOUND)

@app.get('/signup', response_class=HTMLResponse)
async def signup_get(request: Request):
    return templates.TemplateResponse(request, 'signup.html', {
        'request': request,
        'messages': get_flash_messages(request)
    })

@app.post('/signup', response_class=RedirectResponse)
async def signup_post(
    request: Request,
    name: str = Form(...),
    surname: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    age: Optional[str] = Form(None),
    weight_kg: Optional[str] = Form(None)
):
    # Validate form data
    if password != confirm_password:
        add_flash_message(request, 'Passwords do not match!', 'error')
        return RedirectResponse(url='/signup', status_code=status.HTTP_302_FOUND)

    if len(password) < 6:
        add_flash_message(request, 'Password must be at least 6 characters long!', 'error')
        return RedirectResponse(url='/signup', status_code=status.HTTP_302_FOUND)

    try:
        if db.get_account_by_email(email):
            add_flash_message(request, 'Email already registered! Please use a different email.', 'error')
            return RedirectResponse(url='/signup', status_code=status.HTTP_302_FOUND)

        # Signup only ever creates clients; admins are created by seeding/DB
        account = db.create_account(Account(
            role='client',
            name=name.strip(),
            surname=surname.strip(),
            email=email.strip().lower(),
            age=int(age) if age else None,
            weight_kg=float(weight_kg) if weight_kg else None
        ), password)

        # Auto-login after successful registration
        start_session(request, account)
        add_flash_message(request, 'Account created successfully! Welcome to FitCoach!', 'success')
        return RedirectResponse(url='/dashboard', status_code=status.HTTP_302_FOUND)

    except ValueError as ve:
        add_flash_message(request, f'Invalid input: {str(ve)}', 'error')
    except Exception as e:
        add_flash_message(request, 'Registration failed. Please try again.', 'error')

    return RedirectResponse(url='/signup', status_code=status.HTTP_302_FOUND)

# Google OAuth Routes
@app.get('/auth/google/login')
async def google_login(request: Request):
    """Initiate Google OAuth login"""
    # Derived from the live request so it is correct on localhost and in prod alike;
    # a stale GOOGLE_REDIRECT_URI used to send production logins to 127.0.0.1.
    redirect_uri = str(request.url_for('google_callback'))
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get('/auth/google/callback')
async def google_callback(request: Request):
    """Handle Google OAuth callback: match by Google ID, then by email (linking), else create a client"""
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get('userinfo')

        if not user_info:
            add_flash_message(request, 'Failed to get user information from Google', 'error')
            return RedirectResponse(url='/login', status_code=status.HTTP_302_FOUND)

        email = user_info.get('email')
        google_id = user_info.get('sub')
        picture = user_info.get('picture')

        account = db.get_account_by_google_id(google_id)
        if not account:
            account = db.get_account_by_email(email)
            if account:
                db.update_account_google_info(account.id, google_id, picture)

        if account:
            start_session(request, account, picture)
            add_flash_message(request, 'Login successful!', 'success')
        else:
            account = db.create_account(Account(
                role='client',
                name=user_info.get('given_name', ''),
                surname=user_info.get('family_name', ''),
                email=email,
                google_id=google_id,
                profile_picture=picture
            ))
            start_session(request, account, picture)
            add_flash_message(request, 'Account created successfully! Welcome!', 'success')
        return RedirectResponse(url='/dashboard', status_code=status.HTTP_302_FOUND)

    except Exception as e:
        print(f"OAuth error: {str(e)}")
        add_flash_message(request, 'Google login failed. Please try again.', 'error')
        return RedirectResponse(url='/login', status_code=status.HTTP_302_FOUND)

@app.get('/dashboard', response_class=HTMLResponse)
async def dashboard(request: Request):
    if 'user' not in request.session:
        return RedirectResponse(url='/login', status_code=status.HTTP_302_FOUND)

    # Redirect based on user type
    if is_admin(request):
        return RedirectResponse(url='/admin/dashboard', status_code=status.HTTP_302_FOUND)
    return RedirectResponse(url='/user/dashboard', status_code=status.HTTP_302_FOUND)

@app.get('/change_password', response_class=HTMLResponse)
async def change_password_get(request: Request):
    if 'user' not in request.session:
        return RedirectResponse(url='/login', status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(request, 'change_password.html', {
        'request': request,
        'messages': get_flash_messages(request)
    })

@app.post('/change_password', response_class=RedirectResponse)
async def change_password_post(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...)
):
    if 'user' not in request.session:
        return RedirectResponse(url='/login', status_code=status.HTTP_302_FOUND)

    if new_password != confirm_password:
        add_flash_message(request, 'New passwords do not match!', 'error')
        return RedirectResponse(url='/change_password', status_code=status.HTTP_302_FOUND)

    try:
        if not db.authenticate(request.session['user'], current_password):
            add_flash_message(request, 'Current password is incorrect!', 'error')
        elif db.change_password(request.session['user_id'], new_password):
            add_flash_message(request, 'Password changed successfully!', 'success')
            return RedirectResponse(url='/dashboard', status_code=status.HTTP_302_FOUND)
        else:
            add_flash_message(request, 'Failed to change password. Please try again.', 'error')

    except Exception as e:
        add_flash_message(request, 'Error changing password. Please try again.', 'error')

    return RedirectResponse(url='/change_password', status_code=status.HTTP_302_FOUND)

@app.get('/logout', response_class=RedirectResponse)
async def logout(request: Request):
    request.session.clear()
    add_flash_message(request, 'You have been logged out.', 'info')
    return RedirectResponse(url='/login', status_code=status.HTTP_302_FOUND)

# ============ ADMIN PAGES ============
@app.get('/admin/dashboard', response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Coach home: what needs attention + every client's progress"""
    if not is_admin(request):
        return RedirectResponse(url='/login', status_code=status.HTTP_302_FOUND)

    try:
        return templates.TemplateResponse(request, 'admin/dashboard.html', page_context(
            request, nav='home', today=date.today(),
            attention=db.get_attention_items(),
            clients=db.get_clients_overview()
        ))
    except Exception as e:
        add_flash_message(request, f'Error loading dashboard: {str(e)}', 'error')
        return templates.TemplateResponse(request, 'admin/dashboard.html', page_context(request, nav='home'))

@app.get('/admin/users', response_class=HTMLResponse)
async def admin_users(request: Request):
    """Clients: the overview table plus each client's full workout history"""
    if not is_admin(request):
        return RedirectResponse(url='/login', status_code=status.HTTP_302_FOUND)

    try:
        clients = db.get_clients_overview()
        for client in clients:
            client['workouts'] = db.get_client_workouts(client['id'])
        return templates.TemplateResponse(request, 'admin/users.html', page_context(
            request, nav='clients', today=date.today(), clients=clients))
    except Exception as e:
        add_flash_message(request, f'Error loading clients: {str(e)}', 'error')
        return templates.TemplateResponse(request, 'admin/users.html', page_context(request, nav='clients'))

def workout_status(w: dict, today: date) -> str:
    """'completed' | 'overdue' | 'today' (due today or already started) | 'upcoming' | 'unscheduled'"""
    if w['completed']:
        return 'completed'
    d = w['scheduled_date']
    if d and d < today:
        return 'overdue'
    if (d and d == today) or w['completed_set_count']:
        return 'today'
    return 'upcoming' if d else 'unscheduled'

@app.get('/admin/workouts', response_class=HTMLResponse)
async def admin_workouts(request: Request):
    """Every assigned workout across clients, filterable by client and status"""
    if not is_admin(request):
        return RedirectResponse(url='/login', status_code=status.HTTP_302_FOUND)

    try:
        today = date.today()
        workouts = db.get_all_workouts()
        for w in workouts:
            w['status'] = workout_status(w, today)
        return templates.TemplateResponse(request, 'admin/workouts.html', page_context(
            request, nav='workouts', today=today, workouts=workouts, clients=db.get_clients()))
    except Exception as e:
        add_flash_message(request, f'Error loading workouts: {str(e)}', 'error')
        return templates.TemplateResponse(request, 'admin/workouts.html', page_context(request, nav='workouts'))

@app.get('/admin/exercises', response_class=HTMLResponse)
async def admin_exercises(request: Request):
    if not is_admin(request):
        return RedirectResponse(url='/login', status_code=status.HTTP_302_FOUND)

    try:
        return templates.TemplateResponse(request, 'admin/exercises.html', page_context(
            request, nav='exercises', exercises=db.get_exercises_with_usage()))
    except Exception as e:
        add_flash_message(request, f'Error loading exercises: {str(e)}', 'error')
        return templates.TemplateResponse(request, 'admin/exercises.html', page_context(request, nav='exercises'))

@app.get('/admin/templates', response_class=HTMLResponse)
async def admin_templates(request: Request):
    if not is_admin(request):
        return RedirectResponse(url='/login', status_code=status.HTTP_302_FOUND)

    try:
        return templates.TemplateResponse(request, 'admin/templates.html', page_context(
            request, nav='templates',
            workout_templates=db.get_templates(),
            template_problems={t['id']: db.validate_structure('templates', t['id'])
                               for t in db.get_templates() if t['status'] == 'draft'},
            clients=jsonable_encoder(db.get_clients_overview())
        ))
    except Exception as e:
        add_flash_message(request, f'Error loading templates: {str(e)}', 'error')
        return templates.TemplateResponse(request, 'admin/templates.html', page_context(request, nav='templates'))

@app.get('/admin/workout-composer', response_class=HTMLResponse)
async def admin_workout_composer(request: Request, template_id: Optional[int] = None,
                                 workout_id: Optional[int] = None):
    """Composer: no params = new template; ?template_id= edits a template; ?workout_id= edits a client's workout"""
    if not is_admin(request):
        return RedirectResponse(url='/login', status_code=status.HTTP_302_FOUND)

    try:
        target = None
        groups = []
        if template_id:
            template = db.get_template(template_id)
            if not template:
                add_flash_message(request, 'Template not found', 'error')
                return RedirectResponse(url='/admin/templates', status_code=status.HTTP_302_FOUND)
            target = dict(template.to_dict(), kind='templates')
            groups = db.get_structure('templates', template_id)
        elif workout_id:
            workout = db.get_workout(workout_id)
            if not workout:
                add_flash_message(request, 'Workout not found', 'error')
                return RedirectResponse(url='/admin/users', status_code=status.HTTP_302_FOUND)
            if workout.completed:
                add_flash_message(request, 'This workout is completed and can no longer be edited', 'info')
                return RedirectResponse(url=f'/workouts/{workout_id}', status_code=status.HTTP_302_FOUND)
            client = db.get_account(workout.client_id)
            target = dict(workout.to_dict(), kind='workouts', client_name=client.full_name if client else '')
            groups = db.get_structure('workouts', workout_id)

        composer_data = {
            'exercises': [exercise_dict(e) for e in db.get_exercises()],
            'target': target,
            'groups': groups
        }
        return templates.TemplateResponse(request, 'admin/workout_composer.html', page_context(
            request, nav='templates', composer_data=jsonable_encoder(composer_data)))
    except Exception as e:
        add_flash_message(request, f'Error loading composer: {str(e)}', 'error')
        return templates.TemplateResponse(request, 'admin/workout_composer.html', page_context(request, nav='templates'))

# ============ CLIENT PAGES ============
@app.get('/user/dashboard', response_class=HTMLResponse)
async def user_dashboard(request: Request):
    if 'user' not in request.session or request.session.get('user_type') != 'user':
        return RedirectResponse(url='/login', status_code=status.HTTP_302_FOUND)

    try:
        workouts = db.get_client_workouts(request.session.get('user_id'))
        today = date.today()
        # In progress = started or due; upcoming = scheduled later (or undated and untouched); done = completed
        open_ = [w for w in workouts if not w['completed']]
        in_progress = [w for w in open_ if w['completed_set_count'] or (w['scheduled_date'] and w['scheduled_date'] <= today)]
        upcoming = sorted([w for w in open_ if w not in in_progress],
                          key=lambda w: (w['scheduled_date'] is None, w['scheduled_date'] or today))
        done = sorted([w for w in workouts if w['completed']], key=lambda w: w['completed_at'], reverse=True)
        return templates.TemplateResponse(request, 'user/dashboard.html', page_context(
            request, today=today, in_progress=in_progress, upcoming=upcoming, done=done,
            first_name=(request.session.get('name') or '').split(' ')[0]
        ))
    except Exception as e:
        add_flash_message(request, f'Error loading dashboard: {str(e)}', 'error')
        return templates.TemplateResponse(request, 'user/dashboard.html', page_context(request))

@app.get('/workouts/{workout_id}', response_class=HTMLResponse)
async def workout_page(request: Request, workout_id: int):
    """Workout view shared by the owning client (log results) and the coach (review); both can chat"""
    if 'user' not in request.session:
        return RedirectResponse(url='/login', status_code=status.HTTP_302_FOUND)

    try:
        workout = get_accessible_workout(request, workout_id)
    except HTTPException:
        add_flash_message(request, 'Workout not found', 'error')
        return RedirectResponse(url='/dashboard', status_code=status.HTTP_302_FOUND)

    client = db.get_account(workout.client_id)
    viewer_is_admin = is_admin(request)
    workout_data = {
        'workout': dict(workout.to_dict(), completed=workout.completed,
                        client_name=client.full_name if client else ''),
        'groups': db.get_structure('workouts', workout_id),
        'comments': db.get_workout_comments(workout_id),
        'viewer': {'id': request.session.get('user_id'), 'is_admin': viewer_is_admin}
    }
    template = db.get_template(workout.template_id) if viewer_is_admin and workout.template_id else None
    # Same data, two screens: the client's workout log vs the coach's review
    return templates.TemplateResponse(request, 'admin/workout_review.html' if viewer_is_admin else 'user/workout.html',
                                      page_context(request, nav='clients', today=date.today(),
                                                   template_name=template.name if template else None,
                                                   workout=workout_data['workout'],
                                                   workout_data=jsonable_encoder(workout_data)))

# ============ API: library & clients (admin) ============
@app.get('/api/exercises')
async def api_exercises(request: Request):
    require_admin(request)
    return [exercise_dict(e) for e in db.get_exercises()]

@app.post('/api/exercises')
async def api_create_exercise(request: Request, body: ExerciseCreate):
    require_admin(request)
    changes = changes_from(body, name_required=True)
    exercise = db.create_exercise(Exercise(created_by=request.session.get('user_id'), **changes))
    return exercise_dict(exercise)

@app.post('/api/exercises/{exercise_id}/archive')
async def api_archive_exercise(request: Request, exercise_id: int):
    """Hide from the library; templates and workouts that use it keep it"""
    require_admin(request)
    if not db.archive_exercise(exercise_id):
        raise HTTPException(status_code=404, detail='Exercise not found')
    return {'message': 'Exercise archived'}

@app.post('/api/exercises/{exercise_id}/restore')
async def api_restore_exercise(request: Request, exercise_id: int):
    require_admin(request)
    if not db.restore_exercise(exercise_id):
        raise HTTPException(status_code=404, detail='Exercise not found')
    return {'message': 'Exercise restored'}

@app.delete('/api/exercises/{exercise_id}')
async def api_delete_exercise(request: Request, exercise_id: int):
    """Delete an exercise nothing uses; one in a template or workout is kept (409) -- archive it instead"""
    require_admin(request)
    if not db.get_exercise(exercise_id):
        raise HTTPException(status_code=404, detail='Exercise not found')
    used = db.get_exercise_usage(exercise_id)
    if used:
        raise HTTPException(status_code=409, detail=f'Used in {used} set{"s" if used != 1 else ""} of templates or '
                                                    'client workouts, so it can\'t be deleted -- archive it instead')
    db.delete_exercise(exercise_id)
    return {'message': 'Exercise deleted'}

@app.get('/api/clients')
async def api_clients(request: Request):
    require_admin(request)
    return [c.to_public_dict() for c in db.get_clients()]

@app.get('/api/clients/{client_id}/workouts')
async def api_client_workouts(request: Request, client_id: int):
    require_admin(request)
    return db.get_client_workouts(client_id)

# ============ API: templates (admin) ============
@app.get('/api/templates')
async def api_templates(request: Request):
    require_admin(request)
    return db.get_templates()

@app.post('/api/templates')
async def api_create_template(request: Request, body: TemplateCreate):
    require_admin(request)
    changes = changes_from(body, name_required=True)
    template = db.create_template(WorkoutTemplate(created_by=request.session.get('user_id'), **changes))
    return dict(template.to_dict(), groups=[])

@app.get('/api/templates/{template_id}')
async def api_get_template(request: Request, template_id: int):
    require_admin(request)
    template = db.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail='Template not found')
    return dict(template.to_dict(), groups=db.get_structure('templates', template_id))

@app.put('/api/templates/{template_id}')
async def api_update_template(request: Request, template_id: int, body: TemplateUpdate):
    """Partial update; setting status 'ready' validates the template first (400 listing the problems)"""
    require_admin(request)
    check_editable(Kind.templates, template_id)
    changes = changes_from(body, name_required=True)
    if changes.get('status') == 'ready':
        problems = db.validate_structure('templates', template_id)
        if problems:
            raise HTTPException(status_code=400, detail='Template is not ready: ' + '; '.join(problems))
    template = db.update_template(template_id, changes)
    WorkoutTemplate(**template.to_dict())  # re-run model validation on the stored result
    return template.to_dict()

@app.delete('/api/templates/{template_id}')
async def api_delete_template(request: Request, template_id: int):
    require_admin(request)
    if not db.delete_template(template_id):
        raise HTTPException(status_code=404, detail='Template not found')
    return {'message': 'Template deleted'}

@app.post('/api/templates/{template_id}/assign')
async def api_assign_template(request: Request, template_id: int, body: TemplateAssign):
    """Copy a ready template into a new workout for each listed client"""
    require_admin(request)
    template = db.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail='Template not found')
    if template.status != 'ready':
        raise HTTPException(status_code=400, detail='Only ready templates can be assigned -- open it and press Save')
    problems = db.validate_structure('templates', template_id)
    if problems:
        raise HTTPException(status_code=400, detail='Template is not ready: ' + '; '.join(problems))
    client_ids = list(dict.fromkeys(body.client_ids))
    for client_id in client_ids:  # validate all before copying any
        client = db.get_account(client_id)
        if not client or client.is_admin:
            raise HTTPException(status_code=404, detail=f'Client {client_id} not found')
    workout_ids = [db.assign_template(template_id, client_id, request.session.get('user_id'), body.scheduled_date)
                   for client_id in client_ids]
    return {'workout_ids': workout_ids, 'client_ids': client_ids, 'template_id': template_id}

# ============ API: client workouts ============
@app.get('/api/workouts/{workout_id}')
async def api_get_workout(request: Request, workout_id: int):
    """Admin, or the client who owns it"""
    workout = get_accessible_workout(request, workout_id)
    return dict(workout.to_dict(), completed=workout.completed,
                groups=db.get_structure('workouts', workout_id))

@app.put('/api/workouts/{workout_id}')
async def api_update_workout(request: Request, workout_id: int, body: WorkoutUpdate):
    require_admin(request)
    check_editable(Kind.workouts, workout_id)
    workout = db.update_workout(workout_id, changes_from(body, name_required=True))
    return dict(workout.to_dict(), completed=workout.completed)

@app.delete('/api/workouts/{workout_id}')
async def api_delete_workout(request: Request, workout_id: int):
    require_admin(request)
    if not db.delete_workout(workout_id):
        raise HTTPException(status_code=404, detail='Workout not found')
    return {'message': 'Workout deleted'}

@app.put('/api/workout-sets/{set_id}/result')
async def api_record_set_result(request: Request, set_id: int, body: SetResult):
    """Client (or coach) logs actual values and ticks/unticks a set; the workout completes when all sets are done"""
    owner_id = db.get_owner_id('workouts', set_id=set_id)
    if owner_id is None:
        raise HTTPException(status_code=404, detail='Set not found')
    get_accessible_workout(request, owner_id)
    changes = body.model_dump(exclude_unset=True)
    completed = changes.pop('completed', None)
    return db.record_set_result(set_id, changes, completed)

@app.get('/api/workouts/{workout_id}/comments')
async def api_workout_comments(request: Request, workout_id: int):
    get_accessible_workout(request, workout_id)
    return db.get_workout_comments(workout_id)

@app.post('/api/workouts/{workout_id}/comments')
async def api_add_comment(request: Request, workout_id: int, body: CommentCreate):
    """Chat message on the workout, or on one of its groups/sets (which must belong to this workout)"""
    get_accessible_workout(request, workout_id)
    if body.set_id is not None:
        target_owner = db.get_owner_id('workouts', set_id=body.set_id)
    elif body.group_id is not None:
        target_owner = db.get_owner_id('workouts', group_id=body.group_id)
    else:
        target_owner = workout_id
    if target_owner != workout_id:
        raise HTTPException(status_code=404, detail='Comment target not found in this workout')
    attach = ({'set_id': body.set_id} if body.set_id is not None else
              {'group_id': body.group_id} if body.group_id is not None else {'workout_id': workout_id})
    return db.add_comment(Comment(author_id=request.session.get('user_id'), body=body.body, **attach))

# ============ API: groups & sets (admin; same endpoints for templates and workouts) ============
@app.post('/api/{kind}/{owner_id}/groups')
async def api_create_group(request: Request, kind: Kind, owner_id: int):
    require_admin(request)
    check_editable(kind, owner_id)
    return db.create_group(kind.value, owner_id)

@app.put('/api/{kind}/{owner_id}/groups/order')
async def api_reorder_groups(request: Request, kind: Kind, owner_id: int, body: OrderUpdate):
    require_admin(request)
    check_editable(kind, owner_id)
    db.reorder_groups(kind.value, owner_id, body.ids)
    return {'message': 'Groups reordered'}

@app.put('/api/{kind}/groups/{group_id}')
async def api_update_group(request: Request, kind: Kind, group_id: int, body: GroupUpdate):
    require_admin(request)
    check_editable(kind, db.get_owner_id(kind.value, group_id=group_id))
    return db.update_group(kind.value, group_id, changes_from(body))

@app.delete('/api/{kind}/groups/{group_id}')
async def api_delete_group(request: Request, kind: Kind, group_id: int):
    require_admin(request)
    check_editable(kind, db.get_owner_id(kind.value, group_id=group_id))
    db.delete_group(kind.value, group_id)
    return {'message': 'Group deleted'}

@app.post('/api/{kind}/groups/{group_id}/duplicate')
async def api_duplicate_group(request: Request, kind: Kind, group_id: int):
    require_admin(request)
    check_editable(kind, db.get_owner_id(kind.value, group_id=group_id))
    return db.duplicate_group(kind.value, group_id)

@app.post('/api/{kind}/groups/{group_id}/sets')
async def api_add_set(request: Request, kind: Kind, group_id: int, body: SetCreate):
    require_admin(request)
    check_editable(kind, db.get_owner_id(kind.value, group_id=group_id))
    if not db.get_exercise(body.exercise_id):
        raise HTTPException(status_code=404, detail='Exercise not found')
    return db.add_set(kind.value, group_id, body.exercise_id)

@app.put('/api/{kind}/groups/{group_id}/sets/order')
async def api_reorder_sets(request: Request, kind: Kind, group_id: int, body: OrderUpdate):
    require_admin(request)
    check_editable(kind, db.get_owner_id(kind.value, group_id=group_id))
    db.reorder_sets(kind.value, group_id, body.ids)
    return {'message': 'Sets reordered'}

@app.put('/api/{kind}/sets/{set_id}')
async def api_update_set(request: Request, kind: Kind, set_id: int, body: SetUpdate):
    """Partial update of targets, rest and note; an explicit null clears a value"""
    require_admin(request)
    check_editable(kind, db.get_owner_id(kind.value, set_id=set_id))
    changes = changes_from(body)
    # Reps are either a number or "max", never both
    if 'target_reps_max' in changes:
        changes['target_reps_max'] = bool(changes['target_reps_max'])
        if changes['target_reps_max']:
            changes['target_reps'] = None
    elif changes.get('target_reps') is not None:
        changes['target_reps_max'] = False
    return db.update_set(kind.value, set_id, changes)

@app.delete('/api/{kind}/sets/{set_id}')
async def api_delete_set(request: Request, kind: Kind, set_id: int):
    require_admin(request)
    check_editable(kind, db.get_owner_id(kind.value, set_id=set_id))
    db.delete_set(kind.value, set_id)
    return {'message': 'Set deleted'}

@app.post('/api/{kind}/sets/{set_id}/duplicate')
async def api_duplicate_set(request: Request, kind: Kind, set_id: int):
    require_admin(request)
    check_editable(kind, db.get_owner_id(kind.value, set_id=set_id))
    return db.duplicate_set(kind.value, set_id)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)
