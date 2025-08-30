import os
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from contextlib import contextmanager
import logging
import json
import bcrypt
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
from models import User, Admin, Exercise

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError('DATABASE_URL not defined.')
        
        # Railway PostgreSQL often provides URLs starting with postgres://
        # but psycopg2 requires postgresql://
        if self.database_url.startswith('postgres://'):
            self.database_url = self.database_url.replace('postgres://', 'postgresql://', 1)
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = None
        try:
            conn = psycopg2.connect(self.database_url)
            yield conn
        except psycopg2.Error as e:
            logger.error(f"Database connection error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify a password against its hash"""
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    
    def create_tables(self):
        """Create all required tables"""
        create_tables_sql = """
        -- Create Users table
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            surname VARCHAR(100) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255),
            age INTEGER CHECK (age > 0 AND age < 150),
            weight_kg DECIMAL(5,2) CHECK (weight_kg > 0),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Create Exercises table
        CREATE TABLE IF NOT EXISTS exercises (
            id SERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL UNIQUE,
            description TEXT,
            parameters JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Create Admins table
        CREATE TABLE IF NOT EXISTS admins (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            surname VARCHAR(100) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Create indexes for better performance
        CREATE INDEX IF NOT EXISTS idx_users_name ON users(name, surname);
        CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
        CREATE INDEX IF NOT EXISTS idx_exercises_name ON exercises(name);
        CREATE INDEX IF NOT EXISTS idx_exercises_parameters ON exercises USING GIN (parameters);
        CREATE INDEX IF NOT EXISTS idx_admins_name ON admins(name, surname);
        CREATE INDEX IF NOT EXISTS idx_admins_email ON admins(email);
        
        -- Create trigger for updating updated_at timestamp
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        
        DROP TRIGGER IF EXISTS update_users_updated_at ON users;
        CREATE TRIGGER update_users_updated_at
            BEFORE UPDATE ON users
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        
        DROP TRIGGER IF EXISTS update_exercises_updated_at ON exercises;
        CREATE TRIGGER update_exercises_updated_at
            BEFORE UPDATE ON exercises
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        
        DROP TRIGGER IF EXISTS update_admins_updated_at ON admins;
        CREATE TRIGGER update_admins_updated_at
            BEFORE UPDATE ON admins
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(create_tables_sql)
                    conn.commit()
                    logger.info("Tables created successfully")
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            raise
    
    def drop_tables(self):
        """Drop all tables (use with caution)"""
        drop_sql = """
        DROP TABLE IF EXISTS users CASCADE;
        DROP TABLE IF EXISTS exercises CASCADE;
        DROP TABLE IF EXISTS admins CASCADE;
        DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(drop_sql)
                    conn.commit()
                    logger.info("Tables dropped successfully")
        except Exception as e:
            logger.error(f"Error dropping tables: {e}")
            raise
    
    # Users CRUD Operations
    def create_user(self, user: User, password: Optional[str] = None) -> User:
        """Create a new user from User model"""
        password_hash = None
        if password:
            password_hash = self.hash_password(password)
        
        sql = """
        INSERT INTO users (name, surname, email, password_hash, age, weight_kg)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, created_at, updated_at;
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, (user.name, user.surname, user.email, password_hash, user.age, user.weight_kg))
                    result = cursor.fetchone()
                    user.id = result[0]
                    user.password_hash = password_hash
                    user.created_at = result[1]
                    user.updated_at = result[2]
                    conn.commit()
                    logger.info(f"User created with ID: {user.id}")
                    return user
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise
    
    def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        sql = "SELECT * FROM users WHERE id = %s;"
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(sql, (user_id,))
                    result = cursor.fetchone()
                    return User.from_dict(dict(result)) if result else None
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            raise
    
    def get_all_users(self) -> List[User]:
        """Get all users"""
        sql = "SELECT * FROM users ORDER BY surname, name;"
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(sql)
                    results = cursor.fetchall()
                    return [User.from_dict(dict(row)) for row in results]
        except Exception as e:
            logger.error(f"Error getting users: {e}")
            raise
    
    def update_user(self, user: User) -> User:
        """Update user information"""
        sql = """
        UPDATE users SET name = %s, surname = %s, email = %s, age = %s, weight_kg = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING updated_at;
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, (user.name, user.surname, user.email, user.age, user.weight_kg, user.id))
                    result = cursor.fetchone()
                    if result:
                        user.updated_at = result[0]
                        conn.commit()
                        logger.info(f"Updated user {user.id}")
                        return user
                    else:
                        raise ValueError(f"User with ID {user.id} not found")
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            raise
    
    def delete_user(self, user_id: int) -> bool:
        """Delete user by ID"""
        sql = "DELETE FROM users WHERE id = %s;"
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, (user_id,))
                    affected_rows = cursor.rowcount
                    conn.commit()
                    logger.info(f"Deleted user {user_id}, affected rows: {affected_rows}")
                    return affected_rows > 0
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            raise
    
    # Exercises CRUD Operations
    def create_exercise(self, exercise: Exercise) -> Exercise:
        """Create a new exercise from Exercise model"""
        sql = """
        INSERT INTO exercises (name, description, parameters)
        VALUES (%s, %s, %s)
        RETURNING id, created_at, updated_at;
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    params_dict = exercise.get_parameters_dict()
                    cursor.execute(sql, (exercise.name, exercise.description, Json(params_dict)))
                    result = cursor.fetchone()
                    exercise.id = result[0]
                    exercise.created_at = result[1]
                    exercise.updated_at = result[2]
                    conn.commit()
                    logger.info(f"Exercise created with ID: {exercise.id}")
                    return exercise
        except Exception as e:
            logger.error(f"Error creating exercise: {e}")
            raise
    
    def get_exercise(self, exercise_id: int) -> Optional[Exercise]:
        """Get exercise by ID"""
        sql = "SELECT * FROM exercises WHERE id = %s;"
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(sql, (exercise_id,))
                    result = cursor.fetchone()
                    return Exercise.from_dict(dict(result)) if result else None
        except Exception as e:
            logger.error(f"Error getting exercise: {e}")
            raise
    
    def get_all_exercises(self) -> List[Exercise]:
        """Get all exercises"""
        sql = "SELECT * FROM exercises ORDER BY name;"
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(sql)
                    results = cursor.fetchall()
                    return [Exercise.from_dict(dict(row)) for row in results]
        except Exception as e:
            logger.error(f"Error getting exercises: {e}")
            raise
    
    def update_exercise(self, exercise: Exercise) -> Exercise:
        """Update exercise information"""
        sql = """
        UPDATE exercises SET name = %s, description = %s, parameters = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING updated_at;
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    params_dict = exercise.get_parameters_dict()
                    cursor.execute(sql, (exercise.name, exercise.description, Json(params_dict), exercise.id))
                    result = cursor.fetchone()
                    if result:
                        exercise.updated_at = result[0]
                        conn.commit()
                        logger.info(f"Updated exercise {exercise.id}")
                        return exercise
                    else:
                        raise ValueError(f"Exercise with ID {exercise.id} not found")
        except Exception as e:
            logger.error(f"Error updating exercise: {e}")
            raise
    
    def delete_exercise(self, exercise_id: int) -> bool:
        """Delete exercise by ID"""
        sql = "DELETE FROM exercises WHERE id = %s;"
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, (exercise_id,))
                    affected_rows = cursor.rowcount
                    conn.commit()
                    logger.info(f"Deleted exercise {exercise_id}, affected rows: {affected_rows}")
                    return affected_rows > 0
        except Exception as e:
            logger.error(f"Error deleting exercise: {e}")
            raise
    
    def search_exercises(self, search_term: str) -> List[Exercise]:
        """Search exercises by name or description"""
        sql = """
        SELECT * FROM exercises 
        WHERE name ILIKE %s OR description ILIKE %s
        ORDER BY name;
        """
        search_pattern = f"%{search_term}%"
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(sql, (search_pattern, search_pattern))
                    results = cursor.fetchall()
                    return [Exercise.from_dict(dict(row)) for row in results]
        except Exception as e:
            logger.error(f"Error searching exercises: {e}")
            raise
    
    def search_exercises_by_parameters(self, parameter_filters: Dict[str, Any]) -> List[Exercise]:
        """Search exercises by parameter requirements"""
        conditions = []
        params = []
        
        for key, value in parameter_filters.items():
            if isinstance(value, bool):
                conditions.append("parameters->%s = %s")
                params.extend([key, json.dumps(value)])
            else:
                conditions.append("parameters->>%s = %s")
                params.extend([key, str(value)])
        
        if not conditions:
            return self.get_all_exercises()
        
        sql = f"""
        SELECT * FROM exercises 
        WHERE {' AND '.join(conditions)}
        ORDER BY name;
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(sql, params)
                    results = cursor.fetchall()
                    return [Exercise.from_dict(dict(row)) for row in results]
        except Exception as e:
            logger.error(f"Error searching exercises by parameters: {e}")
            raise
    
    def get_exercises_with_parameter(self, parameter_name: str) -> List[Exercise]:
        """Get all exercises that have a specific parameter defined"""
        sql = """
        SELECT * FROM exercises 
        WHERE parameters ? %s
        ORDER BY name;
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(sql, (parameter_name,))
                    results = cursor.fetchall()
                    return [Exercise.from_dict(dict(row)) for row in results]
        except Exception as e:
            logger.error(f"Error getting exercises with parameter: {e}")
            raise
    
    def validate_exercise_model(self, exercise: Exercise) -> List[str]:
        """Validate exercise model and return validation errors"""
        errors = []
        
        try:
            # The Exercise dataclass __post_init__ will validate the model
            Exercise(
                name=exercise.name,
                description=exercise.description,
                has_reps=exercise.has_reps,
                has_weight_kg=exercise.has_weight_kg,
                has_duration_s=exercise.has_duration_s,
                has_distance_m=exercise.has_distance_m
            )
        except ValueError as e:
            errors.append(str(e))
        
        return errors
    
    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate a user by email and password"""
        user = self.get_user_by_email(email)
        if user and user.password_hash and self.verify_password(password, user.password_hash):
            return user
        return None
    
    def change_user_password(self, user_id: int, new_password: str) -> bool:
        """Change user password"""
        password_hash = self.hash_password(new_password)
        sql = """
        UPDATE users 
        SET password_hash = %s, updated_at = CURRENT_TIMESTAMP 
        WHERE id = %s;
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, (password_hash, user_id))
                    conn.commit()
                    logger.info(f"Password changed for user ID: {user_id}")
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error changing user password: {e}")
            raise
    
    # Admins CRUD Operations
    def create_admin(self, admin: Admin, password: Optional[str] = None) -> Admin:
        """Create a new admin from Admin model"""
        password_hash = None
        if password:
            password_hash = self.hash_password(password)
        
        sql = """
        INSERT INTO admins (name, surname, email, password_hash)
        VALUES (%s, %s, %s, %s)
        RETURNING id, created_at, updated_at;
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, (admin.name, admin.surname, admin.email, password_hash))
                    result = cursor.fetchone()
                    admin.id = result[0]
                    admin.password_hash = password_hash
                    admin.created_at = result[1]
                    admin.updated_at = result[2]
                    conn.commit()
                    logger.info(f"Admin created with ID: {admin.id}")
                    return admin
        except Exception as e:
            logger.error(f"Error creating admin: {e}")
            raise
    
    def get_admin(self, admin_id: int) -> Optional[Admin]:
        """Get admin by ID"""
        sql = "SELECT * FROM admins WHERE id = %s;"
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(sql, (admin_id,))
                    result = cursor.fetchone()
                    return Admin.from_dict(dict(result)) if result else None
        except Exception as e:
            logger.error(f"Error getting admin: {e}")
            raise
    
    def get_all_admins(self) -> List[Admin]:
        """Get all admins"""
        sql = "SELECT * FROM admins ORDER BY surname, name;"
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(sql)
                    results = cursor.fetchall()
                    return [Admin.from_dict(dict(row)) for row in results]
        except Exception as e:
            logger.error(f"Error getting admins: {e}")
            raise
    
    def update_admin(self, admin: Admin) -> Admin:
        """Update admin information"""
        sql = """
        UPDATE admins SET name = %s, surname = %s, email = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING updated_at;
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, (admin.name, admin.surname, admin.email, admin.id))
                    result = cursor.fetchone()
                    if result:
                        admin.updated_at = result[0]
                        conn.commit()
                        logger.info(f"Updated admin {admin.id}")
                        return admin
                    else:
                        raise ValueError(f"Admin with ID {admin.id} not found")
        except Exception as e:
            logger.error(f"Error updating admin: {e}")
            raise
    
    def delete_admin(self, admin_id: int) -> bool:
        """Delete admin by ID"""
        sql = "DELETE FROM admins WHERE id = %s;"
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, (admin_id,))
                    affected_rows = cursor.rowcount
                    conn.commit()
                    logger.info(f"Deleted admin {admin_id}, affected rows: {affected_rows}")
                    return affected_rows > 0
        except Exception as e:
            logger.error(f"Error deleting admin: {e}")
            raise
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        sql = "SELECT * FROM users WHERE email = %s;"
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(sql, (email,))
                    result = cursor.fetchone()
                    return User.from_dict(dict(result)) if result else None
        except Exception as e:
            logger.error(f"Error getting user by email: {e}")
            raise
    
    def get_admin_by_email(self, email: str) -> Optional[Admin]:
        """Get admin by email"""
        sql = "SELECT * FROM admins WHERE email = %s;"
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(sql, (email,))
                    result = cursor.fetchone()
                    return Admin.from_dict(dict(result)) if result else None
        except Exception as e:
            logger.error(f"Error getting admin by email: {e}")
            raise
    
    def get_user_count(self) -> int:
        """Get total number of users"""
        sql = "SELECT COUNT(*) FROM users;"
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql)
                    return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error getting user count: {e}")
            raise
    
    def get_exercise_count(self) -> int:
        """Get total number of exercises"""
        sql = "SELECT COUNT(*) FROM exercises;"
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql)
                    return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error getting exercise count: {e}")
            raise
    
    def get_admin_count(self) -> int:
        """Get total number of admins"""
        sql = "SELECT COUNT(*) FROM admins;"
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql)
                    return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error getting admin count: {e}")
            raise
    
    def authenticate_admin(self, email: str, password: str) -> Optional[Admin]:
        """Authenticate an admin by email and password"""
        admin = self.get_admin_by_email(email)
        if admin and admin.password_hash and self.verify_password(password, admin.password_hash):
            return admin
        return None
    
    def change_admin_password(self, admin_id: int, new_password: str) -> bool:
        """Change admin password"""
        password_hash = self.hash_password(new_password)
        sql = """
        UPDATE admins 
        SET password_hash = %s, updated_at = CURRENT_TIMESTAMP 
        WHERE id = %s;
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, (password_hash, admin_id))
                    conn.commit()
                    logger.info(f"Password changed for admin ID: {admin_id}")
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error changing admin password: {e}")
            raise

# Initialize database manager
db = DatabaseManager()

# Convenience functions for easy import
def init_database():
    """Initialize database tables"""
    db.create_tables()

def drop_all_tables():
    """Drop all tables (use with caution)"""
    db.drop_tables()