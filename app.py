from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

# Simple in-memory user storage (use database in production)
users = {
    'coach@fitness.com': {
        'password': generate_password_hash('password123'),
        'name': 'John Coach'
    }
}

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
        
        if email in users and check_password_hash(users[email]['password'], password):
            session['user'] = email
            session['name'] = users[email]['name']
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password!', 'error')
    
    return render_template('login.html')

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

@app.route('/nutrition')
def nutrition():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('nutrition.html', name=session.get('name'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)