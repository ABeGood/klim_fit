from flask import Flask, render_template, request, redirect, url_for, session, flash
from database_manager import DatabaseManager
import os

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

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)