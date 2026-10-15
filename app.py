from fastapi import FastAPI, Request, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from database_manager import DatabaseManager
from models import User, Workout, ExerciseSet, Exercise
from pydantic import BaseModel
from typing import Optional, List
import os
from datetime import datetime
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

# Pydantic models for API requests
class WorkoutCreate(BaseModel):
    user_id: Optional[int] = None  # None = unassigned template
    name: str
    description: str = ""
    duration_minutes: Optional[int] = None

class WorkoutUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = None

class WorkoutAssign(BaseModel):
    user_id: int

class WorkoutSetUpdate(BaseModel):
    rest_seconds: Optional[int] = None
    comment: Optional[str] = None

class ExerciseSetCreate(BaseModel):
    exercise_id: int

class ExerciseSetUpdate(BaseModel):
    reps: Optional[int] = None
    weight_kg: Optional[float] = None
    duration_s: Optional[int] = None
    distance_m: Optional[float] = None
    rest_seconds: Optional[int] = None
    completed: Optional[bool] = None
    comment: Optional[str] = None

# Helper functions for flash messages and auth
def get_flash_messages(request: Request):
    return request.session.pop('_flash_messages', [])

def add_flash_message(request: Request, message: str, category: str = 'info'):
    if '_flash_messages' not in request.session:
        request.session['_flash_messages'] = []
    request.session['_flash_messages'].append({'message': message, 'category': category})

def get_current_user(request: Request):
    if 'user' not in request.session:
        return None
    return request.session.get('user')

def require_auth(request: Request):
    if 'user' not in request.session:
        raise HTTPException(status_code=status.HTTP_302_FOUND, headers={'Location': '/login'})
    return request.session

def require_admin(request: Request):
    if 'user' not in request.session or request.session.get('user_type') != 'admin':
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized')

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
        # Try to authenticate as admin first
        admin = db.authenticate_admin(email, password)
        if admin:
            request.session['user'] = email
            request.session['user_id'] = admin.id
            request.session['name'] = admin.full_name
            request.session['user_type'] = 'admin'
            add_flash_message(request, 'Login successful!', 'success')
            return RedirectResponse(url='/dashboard', status_code=status.HTTP_302_FOUND)

        # Try to authenticate as regular user
        user = db.authenticate_user(email, password)
        if user:
            request.session['user'] = email
            request.session['user_id'] = user.id
            request.session['name'] = user.full_name
            request.session['user_type'] = 'user'
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
        # Check if user already exists
        existing_user = db.get_user_by_email(email)
        existing_admin = db.get_admin_by_email(email)

        if existing_user or existing_admin:
            add_flash_message(request, 'Email already registered! Please use a different email.', 'error')
            return RedirectResponse(url='/signup', status_code=status.HTTP_302_FOUND)

        # Create new user
        new_user = User(
            name=name.strip(),
            surname=surname.strip(),
            email=email.strip().lower(),
            age=int(age) if age else None,
            weight_kg=float(weight_kg) if weight_kg else None
        )

        created_user = db.create_user(new_user, password)

        # Auto-login after successful registration
        request.session['user'] = created_user.email
        request.session['user_id'] = created_user.id
        request.session['name'] = created_user.full_name
        request.session['user_type'] = 'user'

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
    """Handle Google OAuth callback"""
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get('userinfo')

        if not user_info:
            add_flash_message(request, 'Failed to get user information from Google', 'error')
            return RedirectResponse(url='/login', status_code=status.HTTP_302_FOUND)

        email = user_info.get('email')
        google_id = user_info.get('sub')
        given_name = user_info.get('given_name', '')
        family_name = user_info.get('family_name', '')
        picture = user_info.get('picture')

        # Try to find existing user or admin by Google ID or email
        user = db.get_user_by_google_id(google_id)
        admin = db.get_admin_by_google_id(google_id) if not user else None

        if not user and not admin:
            # Try by email
            user = db.get_user_by_email(email)
            admin = db.get_admin_by_email(email) if not user else None

        # If found, update Google ID and profile picture
        if user:
            if not user.google_id:
                db.update_user_google_info(user.id, google_id, picture)
            request.session['user'] = email
            request.session['user_id'] = user.id
            request.session['name'] = user.full_name
            request.session['user_type'] = 'user'
            request.session['profile_picture'] = picture
            add_flash_message(request, 'Login successful!', 'success')
            return RedirectResponse(url='/dashboard', status_code=status.HTTP_302_FOUND)

        elif admin:
            if not admin.google_id:
                db.update_admin_google_info(admin.id, google_id, picture)
            request.session['user'] = email
            request.session['user_id'] = admin.id
            request.session['name'] = admin.full_name
            request.session['user_type'] = 'admin'
            request.session['profile_picture'] = picture
            add_flash_message(request, 'Login successful!', 'success')
            return RedirectResponse(url='/dashboard', status_code=status.HTTP_302_FOUND)

        else:
            # Create new user account
            new_user = User(
                name=given_name,
                surname=family_name,
                email=email,
                google_id=google_id,
                profile_picture=picture
            )
            created_user = db.create_user_with_google(new_user)

            request.session['user'] = email
            request.session['user_id'] = created_user.id
            request.session['name'] = created_user.full_name
            request.session['user_type'] = 'user'
            request.session['profile_picture'] = picture
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
    user_type = request.session.get('user_type', 'user')
    if user_type == 'admin':
        return RedirectResponse(url='/admin/dashboard', status_code=status.HTTP_302_FOUND)
    else:
        return RedirectResponse(url='/user/dashboard', status_code=status.HTTP_302_FOUND)

# ============ ADMIN ROUTES ============
@app.get('/admin/dashboard', response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    if 'user' not in request.session or request.session.get('user_type') != 'admin':
        return RedirectResponse(url='/login', status_code=status.HTTP_302_FOUND)

    try:
        # Get statistics
        total_users = len(db.get_all_users())
        total_workouts = db.get_workout_count()
        total_exercises = len(db.get_all_exercises())

        # Get recent users
        recent_users = db.get_all_users()[:5]

        # Get recent workouts
        recent_workouts = db.get_all_workouts()[:5]

        return templates.TemplateResponse(request, 'admin/dashboard.html', {
            'request': request,
            'name': request.session.get('name'),
            'profile_picture': request.session.get('profile_picture'),
            'total_users': total_users,
            'total_workouts': total_workouts,
            'total_exercises': total_exercises,
            'recent_users': recent_users,
            'recent_workouts': recent_workouts,
            'messages': get_flash_messages(request)
        })
    except Exception as e:
        add_flash_message(request, f'Error loading dashboard: {str(e)}', 'error')
        return templates.TemplateResponse(request, 'admin/dashboard.html', {
            'request': request,
            'name': request.session.get('name'),
            'messages': get_flash_messages(request)
        })

@app.get('/admin/users', response_class=HTMLResponse)
async def admin_users(request: Request):
    if 'user' not in request.session or request.session.get('user_type') != 'admin':
        return RedirectResponse(url='/login', status_code=status.HTTP_302_FOUND)

    try:
        users = db.get_all_users()
        return templates.TemplateResponse(request, 'admin/users.html', {
            'request': request,
            'name': request.session.get('name'),
            'profile_picture': request.session.get('profile_picture'),
            'users': users,
            'messages': get_flash_messages(request)
        })
    except Exception as e:
        add_flash_message(request, f'Error loading users: {str(e)}', 'error')
        return templates.TemplateResponse(request, 'admin/users.html', {
            'request': request,
            'name': request.session.get('name'),
            'messages': get_flash_messages(request)
        })

@app.get('/admin/workout-composer', response_class=HTMLResponse)
async def admin_workout_composer(request: Request):
    if 'user' not in request.session or request.session.get('user_type') != 'admin':
        return RedirectResponse(url='/login', status_code=status.HTTP_302_FOUND)

    try:
        exercises = db.get_all_exercises()
        composer_data = {
            'exercises': [{
                'id': e.id,
                'name': e.name,
                'description': e.description or '',
                'has_reps': e.has_reps,
                'has_weight_kg': e.has_weight_kg,
                'has_duration_s': e.has_duration_s,
                'has_distance_m': e.has_distance_m
            } for e in exercises]
        }
        return templates.TemplateResponse(request, 'admin/workout_composer.html', {
            'request': request,
            'name': request.session.get('name'),
            'profile_picture': request.session.get('profile_picture'),
            'composer_data': composer_data,
            'messages': get_flash_messages(request)
        })
    except Exception as e:
        add_flash_message(request, f'Error loading composer: {str(e)}', 'error')
        return templates.TemplateResponse(request, 'admin/workout_composer.html', {
            'request': request,
            'name': request.session.get('name'),
            'messages': get_flash_messages(request)
        })

# ============ USER ROUTES ============
@app.get('/user/dashboard', response_class=HTMLResponse)
async def user_dashboard(request: Request):
    if 'user' not in request.session or request.session.get('user_type') != 'user':
        return RedirectResponse(url='/login', status_code=status.HTTP_302_FOUND)

    try:
        user_id = request.session.get('user_id')
        # Get user's workouts
        workouts = db.get_workouts_by_user(user_id)

        # Calculate statistics
        total_workouts = len(workouts)
        completed_workouts = len([w for w in workouts if w.completed])
        pending_workouts = total_workouts - completed_workouts

        return templates.TemplateResponse(request, 'user/dashboard.html', {
            'request': request,
            'name': request.session.get('name'),
            'profile_picture': request.session.get('profile_picture'),
            'workouts': workouts,
            'total_workouts': total_workouts,
            'completed_workouts': completed_workouts,
            'pending_workouts': pending_workouts,
            'messages': get_flash_messages(request)
        })
    except Exception as e:
        add_flash_message(request, f'Error loading dashboard: {str(e)}', 'error')
        return templates.TemplateResponse(request, 'user/dashboard.html', {
            'request': request,
            'name': request.session.get('name'),
            'messages': get_flash_messages(request)
        })

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
        user_email = request.session['user']
        user_type = request.session.get('user_type', 'user')

        # Verify current password
        if user_type == 'admin':
            authenticated = db.authenticate_admin(user_email, current_password)
            if authenticated:
                success = db.change_admin_password(request.session['user_id'], new_password)
        else:
            authenticated = db.authenticate_user(user_email, current_password)
            if authenticated:
                success = db.change_user_password(request.session['user_id'], new_password)

        if not authenticated:
            add_flash_message(request, 'Current password is incorrect!', 'error')
        elif success:
            add_flash_message(request, 'Password changed successfully!', 'success')
            return RedirectResponse(url='/dashboard', status_code=status.HTTP_302_FOUND)
        else:
            add_flash_message(request, 'Failed to change password. Please try again.', 'error')

    except Exception as e:
        add_flash_message(request, 'Error changing password. Please try again.', 'error')

    return RedirectResponse(url='/change_password', status_code=status.HTTP_302_FOUND)

# API Routes for Workout Management
@app.get('/api/users')
async def api_users(request: Request):
    require_admin(request)

    try:
        users = db.get_all_users()
        return [{
            'id': user.id,
            'name': user.name,
            'surname': user.surname,
            'email': user.email,
            'full_name': user.full_name,
            'age': user.age,
            'weight_kg': user.weight_kg
        } for user in users]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/api/users/{user_id}/workouts')
async def api_user_workouts(request: Request, user_id: int):
    require_admin(request)

    try:
        workouts = db.get_workouts_by_user(user_id)
        return [{
            'id': workout.id,
            'name': workout.name,
            'description': workout.description,
            'workout_date': workout.workout_date.isoformat() if workout.workout_date else None,
            'duration_minutes': workout.duration_minutes,
            'completed': workout.completed,
            'created_at': workout.created_at.isoformat() if workout.created_at else None
        } for workout in workouts]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/api/workouts/{workout_id}/exercise-sets')
async def api_workout_exercise_sets(request: Request, workout_id: int):
    require_admin(request)

    try:
        exercise_sets = db.get_exercise_sets_by_workout(workout_id)
        result = []
        for ex_set in exercise_sets:
            exercise = db.get_exercise_by_id(ex_set.exercise_id)
            result.append({
                'id': ex_set.id,
                'exercise_id': ex_set.exercise_id,
                'exercise_name': exercise.name if exercise else 'Unknown',
                'exercise_description': exercise.description if exercise else '',
                'exercise_parameters': exercise.get_parameters_dict() if exercise else {},
                'set_order': ex_set.set_order,
                'reps': ex_set.reps,
                'weight_kg': ex_set.weight_kg,
                'duration_s': ex_set.duration_s,
                'distance_m': ex_set.distance_m,
                'rest_seconds': ex_set.rest_seconds,
                'completed': ex_set.completed
            })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/api/exercises')
async def api_exercises(request: Request):
    require_admin(request)

    try:
        exercises = db.get_all_exercises()
        return [{
            'id': exercise.id,
            'name': exercise.name,
            'description': exercise.description,
            'has_reps': exercise.has_reps,
            'has_weight_kg': exercise.has_weight_kg,
            'has_duration_s': exercise.has_duration_s,
            'has_distance_m': exercise.has_distance_m,
            'parameter_types': exercise.parameter_types,
            'parameter_summary': exercise.parameter_summary
        } for exercise in exercises]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/workouts')
async def api_create_workout(request: Request, workout_data: WorkoutCreate):
    require_admin(request)

    try:
        workout = Workout(
            user_id=workout_data.user_id,
            name=workout_data.name,
            description=workout_data.description,
            duration_minutes=workout_data.duration_minutes,
            workout_date=datetime.now(),
            completed=False
        )

        created_workout = db.create_workout(workout)
        return {
            'id': created_workout.id,
            'name': created_workout.name,
            'description': created_workout.description,
            'duration_minutes': created_workout.duration_minutes,
            'workout_date': created_workout.workout_date.isoformat() if created_workout.workout_date else None,
            'completed': created_workout.completed
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put('/api/workouts/{workout_id}')
async def api_update_workout(request: Request, workout_id: int, update_data: WorkoutUpdate):
    require_admin(request)

    try:
        workout = db.get_workout(workout_id)
        if not workout:
            raise HTTPException(status_code=404, detail='Workout not found')

        if update_data.name is not None:
            workout.name = update_data.name
        if update_data.description is not None:
            workout.description = update_data.description
        if update_data.duration_minutes is not None:
            workout.duration_minutes = update_data.duration_minutes

        db.update_workout(workout)
        return {
            'id': workout.id,
            'name': workout.name,
            'description': workout.description,
            'duration_minutes': workout.duration_minutes,
            'completed': workout.completed
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Workout sets (groups of exercises within a workout)
@app.get('/api/workouts/{workout_id}/sets')
async def api_get_workout_sets(request: Request, workout_id: int):
    require_admin(request)

    try:
        return db.get_workout_sets_with_exercises(workout_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/workouts/{workout_id}/sets')
async def api_create_workout_set(request: Request, workout_id: int):
    require_admin(request)

    try:
        workout_set = db.create_workout_set(workout_id)
        return {
            'id': workout_set.id,
            'workout_id': workout_set.workout_id,
            'set_order': workout_set.set_order,
            'exercises': []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/workouts/{workout_id}/assign')
async def api_assign_workout(request: Request, workout_id: int, assign_data: WorkoutAssign):
    require_admin(request)

    try:
        success = db.assign_workout_to_user(workout_id, assign_data.user_id)
        if not success:
            raise HTTPException(status_code=404, detail='Workout not found')
        return {'message': 'Workout assigned', 'workout_id': workout_id, 'user_id': assign_data.user_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put('/api/sets/{set_id}')
async def api_update_workout_set(request: Request, set_id: int, update_data: WorkoutSetUpdate):
    require_admin(request)

    try:
        workout_set = db.get_workout_set(set_id)
        if not workout_set:
            raise HTTPException(status_code=404, detail='Set not found')

        if update_data.rest_seconds is not None:
            workout_set.rest_seconds = update_data.rest_seconds
        if update_data.comment is not None:
            workout_set.comment = update_data.comment or None  # empty string clears the note

        db.update_workout_set(workout_set)
        return {
            'id': workout_set.id,
            'set_order': workout_set.set_order,
            'rest_seconds': workout_set.rest_seconds,
            'comment': workout_set.comment
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/sets/{set_id}/duplicate')
async def api_duplicate_workout_set(request: Request, set_id: int):
    require_admin(request)

    try:
        new_set = db.duplicate_workout_set(set_id)
        if not new_set:
            raise HTTPException(status_code=404, detail='Set not found')
        return new_set
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete('/api/sets/{set_id}')
async def api_delete_workout_set(request: Request, set_id: int):
    require_admin(request)

    try:
        success = db.delete_workout_set(set_id)
        if success:
            return {'message': 'Set deleted successfully'}
        else:
            raise HTTPException(status_code=404, detail='Set not found')
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/sets/{set_id}/exercises')
async def api_add_exercise_to_set(request: Request, set_id: int, set_data: ExerciseSetCreate):
    require_admin(request)

    try:
        entry = db.add_exercise_to_set(set_id, set_data.exercise_id)
        if not entry:
            raise HTTPException(status_code=404, detail='Set not found')
        return entry
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/exercise-sets/{set_id}/duplicate')
async def api_duplicate_exercise_entry(request: Request, set_id: int):
    require_admin(request)

    try:
        entry = db.duplicate_exercise_entry(set_id)
        if not entry:
            raise HTTPException(status_code=404, detail='Exercise entry not found')
        return entry
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/workouts/{workout_id}/exercise-sets')
async def api_add_exercise_set(request: Request, workout_id: int, set_data: ExerciseSetCreate):
    require_admin(request)

    try:
        # Get the highest set_order for this workout
        existing_sets = db.get_exercise_sets_by_workout(workout_id)
        next_order = max([s.set_order for s in existing_sets], default=0) + 1

        exercise_set = ExerciseSet(
            workout_id=workout_id,
            exercise_id=set_data.exercise_id,
            set_order=next_order,
            completed=False
        )

        created_set = db.create_exercise_set(exercise_set)
        exercise = db.get_exercise_by_id(set_data.exercise_id)

        return {
            'id': created_set.id,
            'exercise_id': created_set.exercise_id,
            'exercise_name': exercise.name if exercise else 'Unknown',
            'exercise_description': exercise.description if exercise else '',
            'exercise_parameters': exercise.get_parameters_dict() if exercise else {},
            'set_order': created_set.set_order,
            'reps': created_set.reps,
            'weight_kg': created_set.weight_kg,
            'duration_s': created_set.duration_s,
            'distance_m': created_set.distance_m,
            'rest_seconds': created_set.rest_seconds,
            'completed': created_set.completed
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put('/api/exercise-sets/{set_id}')
async def api_update_exercise_set(request: Request, set_id: int, update_data: ExerciseSetUpdate):
    require_admin(request)

    try:
        exercise_set = db.get_exercise_set_by_id(set_id)

        if not exercise_set:
            raise HTTPException(status_code=404, detail='Exercise set not found')

        # Update fields if provided
        if update_data.reps is not None:
            exercise_set.reps = update_data.reps
        if update_data.weight_kg is not None:
            exercise_set.weight_kg = update_data.weight_kg
        if update_data.duration_s is not None:
            exercise_set.duration_s = update_data.duration_s
        if update_data.distance_m is not None:
            exercise_set.distance_m = update_data.distance_m
        if update_data.rest_seconds is not None:
            exercise_set.rest_seconds = update_data.rest_seconds
        if update_data.completed is not None:
            exercise_set.completed = update_data.completed
        if update_data.comment is not None:
            exercise_set.comment = update_data.comment or None  # empty string clears the note

        updated_set = db.update_exercise_set(exercise_set)
        exercise = db.get_exercise_by_id(updated_set.exercise_id)

        return {
            'id': updated_set.id,
            'exercise_id': updated_set.exercise_id,
            'exercise_name': exercise.name if exercise else 'Unknown',
            'exercise_description': exercise.description if exercise else '',
            'exercise_parameters': exercise.get_parameters_dict() if exercise else {},
            'set_order': updated_set.set_order,
            'reps': updated_set.reps,
            'weight_kg': updated_set.weight_kg,
            'duration_s': updated_set.duration_s,
            'distance_m': updated_set.distance_m,
            'rest_seconds': updated_set.rest_seconds,
            'completed': updated_set.completed,
            'comment': updated_set.comment
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete('/api/exercise-sets/{set_id}')
async def api_delete_exercise_set(request: Request, set_id: int):
    require_admin(request)

    try:
        success = db.delete_exercise_set(set_id)
        if success:
            return {'message': 'Exercise set deleted successfully'}
        else:
            raise HTTPException(status_code=404, detail='Exercise set not found')
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete('/api/workouts/{workout_id}')
async def api_delete_workout(request: Request, workout_id: int):
    require_admin(request)

    try:
        success = db.delete_workout(workout_id)
        if success:
            return {'message': 'Workout deleted successfully'}
        else:
            raise HTTPException(status_code=404, detail='Workout not found')
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/logout', response_class=RedirectResponse)
async def logout(request: Request):
    request.session.clear()
    add_flash_message(request, 'You have been logged out.', 'info')
    return RedirectResponse(url='/login', status_code=status.HTTP_302_FOUND)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)