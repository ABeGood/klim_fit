from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from database_manager import DatabaseManager
from models import User, Workout, ExerciseSet, Exercise
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

# Initialize database manager
db = DatabaseManager()

@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        try:
            # Try to authenticate as admin first
            admin = db.authenticate_admin(email, password)
            if admin:
                session['user'] = email
                session['user_id'] = admin.id
                session['name'] = admin.full_name
                session['user_type'] = 'admin'
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            
            # Try to authenticate as regular user
            user = db.authenticate_user(email, password)
            if user:
                session['user'] = email
                session['user_id'] = user.id
                session['name'] = user.full_name
                session['user_type'] = 'user'
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            
            flash('Invalid email or password!', 'error')
            
        except Exception as e:
            flash('Login error occurred. Please try again.', 'error')
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        surname = request.form['surname']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        age = request.form.get('age')
        weight_kg = request.form.get('weight_kg')
        
        # Validate form data
        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return render_template('signup.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long!', 'error')
            return render_template('signup.html')
        
        try:
            # Check if user already exists
            existing_user = db.get_user_by_email(email)
            existing_admin = db.get_admin_by_email(email)
            
            if existing_user or existing_admin:
                flash('Email already registered! Please use a different email.', 'error')
                return render_template('signup.html')
            
            # Create new user
            from models import User
            new_user = User(
                name=name.strip(),
                surname=surname.strip(),
                email=email.strip().lower(),
                age=int(age) if age else None,
                weight_kg=float(weight_kg) if weight_kg else None
            )
            
            created_user = db.create_user(new_user, password)
            
            # Auto-login after successful registration
            session['user'] = created_user.email
            session['user_id'] = created_user.id
            session['name'] = created_user.full_name
            session['user_type'] = 'user'
            
            flash('Account created successfully! Welcome to FitCoach!', 'success')
            return redirect(url_for('dashboard'))
            
        except ValueError as ve:
            flash(f'Invalid input: {str(ve)}', 'error')
        except Exception as e:
            flash('Registration failed. Please try again.', 'error')
    
    return render_template('signup.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', name=session.get('name'))

@app.route('/clients')
def clients():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('clients.html', name=session.get('name'))

@app.route('/workouts')
def workouts():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('workouts.html', name=session.get('name'))


@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        if new_password != confirm_password:
            flash('New passwords do not match!', 'error')
            return render_template('change_password.html')
        
        try:
            user_email = session['user']
            user_type = session.get('user_type', 'user')
            
            # Verify current password
            if user_type == 'admin':
                authenticated = db.authenticate_admin(user_email, current_password)
                if authenticated:
                    success = db.change_admin_password(session['user_id'], new_password)
            else:
                authenticated = db.authenticate_user(user_email, current_password)
                if authenticated:
                    success = db.change_user_password(session['user_id'], new_password)
            
            if not authenticated:
                flash('Current password is incorrect!', 'error')
            elif success:
                flash('Password changed successfully!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Failed to change password. Please try again.', 'error')
                
        except Exception as e:
            flash('Error changing password. Please try again.', 'error')
    
    return render_template('change_password.html')

# API Routes for Workout Management
@app.route('/api/users')
def api_users():
    if 'user' not in session or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        users = db.get_all_users()
        return jsonify([{
            'id': user.id,
            'name': user.name,
            'surname': user.surname,
            'email': user.email,
            'full_name': user.full_name,
            'age': user.age,
            'weight_kg': user.weight_kg
        } for user in users])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<int:user_id>/workouts')
def api_user_workouts(user_id):
    if 'user' not in session or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        workouts = db.get_workouts_by_user(user_id)
        return jsonify([{
            'id': workout.id,
            'name': workout.name,
            'description': workout.description,
            'workout_date': workout.workout_date.isoformat() if workout.workout_date else None,
            'duration_minutes': workout.duration_minutes,
            'completed': workout.completed,
            'created_at': workout.created_at.isoformat() if workout.created_at else None
        } for workout in workouts])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/workouts/<int:workout_id>/exercise-sets')
def api_workout_exercise_sets(workout_id):
    if 'user' not in session or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
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
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/exercises')
def api_exercises():
    if 'user' not in session or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        exercises = db.get_all_exercises()
        return jsonify([{
            'id': exercise.id,
            'name': exercise.name,
            'description': exercise.description,
            'has_reps': exercise.has_reps,
            'has_weight_kg': exercise.has_weight_kg,
            'has_duration_s': exercise.has_duration_s,
            'has_distance_m': exercise.has_distance_m,
            'parameter_types': exercise.parameter_types,
            'parameter_summary': exercise.parameter_summary
        } for exercise in exercises])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/workouts', methods=['POST'])
def api_create_workout():
    if 'user' not in session or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        user_id = data.get('user_id')
        name = data.get('name')
        description = data.get('description', '')
        
        if not user_id or not name:
            return jsonify({'error': 'user_id and name are required'}), 400
        
        workout = Workout(
            user_id=user_id,
            name=name,
            description=description,
            workout_date=datetime.now(),
            completed=False
        )
        
        created_workout = db.create_workout(workout)
        return jsonify({
            'id': created_workout.id,
            'name': created_workout.name,
            'description': created_workout.description,
            'workout_date': created_workout.workout_date.isoformat() if created_workout.workout_date else None,
            'completed': created_workout.completed
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/workouts/<int:workout_id>/exercise-sets', methods=['POST'])
def api_add_exercise_set(workout_id):
    if 'user' not in session or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        exercise_id = data.get('exercise_id')
        
        if not exercise_id:
            return jsonify({'error': 'exercise_id is required'}), 400
        
        # Get the highest set_order for this workout
        existing_sets = db.get_exercise_sets_by_workout(workout_id)
        next_order = max([s.set_order for s in existing_sets], default=0) + 1
        
        exercise_set = ExerciseSet(
            workout_id=workout_id,
            exercise_id=exercise_id,
            set_order=next_order,
            completed=False
        )
        
        created_set = db.create_exercise_set(exercise_set)
        exercise = db.get_exercise_by_id(exercise_id)
        
        return jsonify({
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
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/exercise-sets/<int:set_id>', methods=['PUT'])
def api_update_exercise_set(set_id):
    if 'user' not in session or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        exercise_set = db.get_exercise_set_by_id(set_id)
        
        if not exercise_set:
            return jsonify({'error': 'Exercise set not found'}), 404
        
        # Update fields if provided
        if 'reps' in data:
            exercise_set.reps = data['reps'] if data['reps'] else None
        if 'weight_kg' in data:
            exercise_set.weight_kg = data['weight_kg'] if data['weight_kg'] else None
        if 'duration_s' in data:
            exercise_set.duration_s = data['duration_s'] if data['duration_s'] else None
        if 'distance_m' in data:
            exercise_set.distance_m = data['distance_m'] if data['distance_m'] else None
        if 'rest_seconds' in data:
            exercise_set.rest_seconds = data['rest_seconds'] if data['rest_seconds'] else None
        if 'completed' in data:
            exercise_set.completed = data['completed']
        
        updated_set = db.update_exercise_set(exercise_set)
        exercise = db.get_exercise_by_id(updated_set.exercise_id)
        
        return jsonify({
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
            'completed': updated_set.completed
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/exercise-sets/<int:set_id>', methods=['DELETE'])
def api_delete_exercise_set(set_id):
    if 'user' not in session or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        success = db.delete_exercise_set(set_id)
        if success:
            return jsonify({'message': 'Exercise set deleted successfully'})
        else:
            return jsonify({'error': 'Exercise set not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)