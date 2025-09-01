# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Application
```bash
python app.py
```
The application runs on `http://localhost:5000` in debug mode.

### Installing Dependencies
```bash
pip install -r requirements.txt
```

### Database Operations
The application uses PostgreSQL with connection details in `.ENV` file.

## Project Architecture

### Core Components
- **app.py**: Main Flask application with routes for authentication, dashboard, and user management
- **models.py**: Data models using dataclasses (User, Admin, Exercise, Workout, ExerciseSet)
- **database_manager.py**: PostgreSQL database operations with connection pooling and bcrypt password hashing
- **db_tests.py**: Database testing utilities with sample data seeding

### Data Models
- **User/Admin**: Authentication and user management with bcrypt password hashing
- **Exercise**: Exercise definitions with flexible parameter types (reps, weight, duration, distance)
- **Workout**: Workout sessions with comments and completion tracking
- **ExerciseSet**: Individual exercise sets within workouts with performance metrics

### Authentication System
- Dual authentication: regular users and admin users
- Session-based authentication with Flask sessions
- Password changing functionality
- User registration with validation

### Database Design
- PostgreSQL with psycopg2-binary driver
- JSONB fields for flexible exercise parameters and comments
- Proper connection management with context managers
- Railway PostgreSQL URL handling (postgres:// to postgresql:// conversion)

### Key Patterns
- All models use dataclasses with validation in `__post_init__`
- Database operations use context managers for connection handling
- Models have `from_dict()` and `to_dict()` methods for serialization
- Comment systems are implemented as JSONB arrays with author/message/timestamp
- Exercise parameters are stored as JSONB with boolean flags for parameter types

### Template Structure
- **base.html**: Base template with navigation and layout
- **login.html/signup.html**: Authentication pages
- **dashboard.html**: Main dashboard after login
- **clients.html/workouts.html**: Feature-specific pages

### Configuration
- Environment variables loaded via python-dotenv
- Database URL in `.ENV` file
- Flask secret key should be changed in production