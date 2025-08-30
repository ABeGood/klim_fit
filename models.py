from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from datetime import datetime
import json

@dataclass
class User:
    """User data model"""
    id: Optional[int] = None
    name: str = ""
    surname: str = ""
    email: str = ""
    password_hash: Optional[str] = None
    age: Optional[int] = None
    weight_kg: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Validate user data after initialization"""
        if self.age is not None and (self.age <= 0 or self.age >= 150):
            raise ValueError("Age must be between 1 and 149")
        if self.weight_kg is not None and self.weight_kg <= 0:
            raise ValueError("Weight must be greater than 0")
        if self.email and '@' not in self.email:
            raise ValueError("Invalid email format")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """Create User instance from dictionary"""
        return cls(
            id=data.get('id'),
            name=data.get('name', ''),
            surname=data.get('surname', ''),
            email=data.get('email', ''),
            password_hash=data.get('password_hash'),
            age=data.get('age'),
            weight_kg=data.get('weight_kg'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert User instance to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'surname': self.surname,
            'email': self.email,
            'password_hash': self.password_hash,
            'age': self.age,
            'weight_kg': self.weight_kg,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @property
    def full_name(self) -> str:
        """Get full name"""
        return f"{self.name} {self.surname}".strip()

@dataclass
class Admin:
    """Admin data model"""
    id: Optional[int] = None
    name: str = ""
    surname: str = ""
    email: str = ""
    password_hash: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Validate admin data after initialization"""
        if self.email and '@' not in self.email:
            raise ValueError("Invalid email format")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Admin':
        """Create Admin instance from dictionary"""
        return cls(
            id=data.get('id'),
            name=data.get('name', ''),
            surname=data.get('surname', ''),
            email=data.get('email', ''),
            password_hash=data.get('password_hash'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Admin instance to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'surname': self.surname,
            'email': self.email,
            'password_hash': self.password_hash,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @property
    def full_name(self) -> str:
        """Get full name"""
        return f"{self.name} {self.surname}".strip()

@dataclass
class Exercise:
    """Exercise data model"""
    id: Optional[int] = None
    name: str = ""
    description: Optional[str] = None
    has_reps: bool = False
    has_weight_kg: bool = False
    has_duration_s: bool = False
    has_distance_m: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Validate exercise data after initialization"""
        if not self.name.strip():
            raise ValueError("Exercise name cannot be empty")
        if not any([self.has_reps, self.has_weight_kg, self.has_duration_s, self.has_distance_m]):
            raise ValueError("Exercise must have at least one parameter type")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Exercise':
        """Create Exercise instance from dictionary"""
        # Handle parameters from JSONB field
        params = data.get('parameters', {})
        if isinstance(params, str):
            import json
            params = json.loads(params)
        
        return cls(
            id=data.get('id'),
            name=data.get('name', ''),
            description=data.get('description'),
            has_reps=params.get('has_reps', False),
            has_weight_kg=params.get('has_weight_kg', False),
            has_duration_s=params.get('has_duration_s', False),
            has_distance_m=params.get('has_distance_m', False),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Exercise instance to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'has_reps': self.has_reps,
            'has_weight_kg': self.has_weight_kg,
            'has_duration_s': self.has_duration_s,
            'has_distance_m': self.has_distance_m,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def get_parameters_dict(self) -> Dict[str, bool]:
        """Get parameters as dictionary for database storage"""
        return {
            'has_reps': self.has_reps,
            'has_weight_kg': self.has_weight_kg,
            'has_duration_s': self.has_duration_s,
            'has_distance_m': self.has_distance_m
        }
    
    @property
    def parameter_types(self) -> list[str]:
        """Get list of active parameter types"""
        types = []
        if self.has_reps:
            types.append('reps')
        if self.has_weight_kg:
            types.append('weight_kg')
        if self.has_duration_s:
            types.append('duration_s')
        if self.has_distance_m:
            types.append('distance_m')
        return types
    
    @property
    def requires_reps(self) -> bool:
        """Check if exercise requires repetitions"""
        return self.has_reps
    
    @property
    def requires_weight(self) -> bool:
        """Check if exercise requires weight"""
        return self.has_weight_kg
    
    @property
    def requires_duration(self) -> bool:
        """Check if exercise requires duration"""
        return self.has_duration_s
    
    @property
    def requires_distance(self) -> bool:
        """Check if exercise requires distance"""
        return self.has_distance_m
    
    @property
    def parameter_summary(self) -> str:
        """Get human-readable summary of parameters"""
        types = self.parameter_types
        if not types:
            return "No parameters"
        return ", ".join(types)

# Utility functions for model conversion
def dict_to_user(data: Dict[str, Any]) -> User:
    """Convert dictionary to User model"""
    return User.from_dict(data)

def dict_to_admin(data: Dict[str, Any]) -> Admin:
    """Convert dictionary to Admin model"""
    return Admin.from_dict(data)

def dict_to_exercise(data: Dict[str, Any]) -> Exercise:
    """Convert dictionary to Exercise model"""
    return Exercise.from_dict(data)

def users_from_list(data_list: list[Dict[str, Any]]) -> list[User]:
    """Convert list of dictionaries to list of User models"""
    return [User.from_dict(item) for item in data_list]

def admins_from_list(data_list: list[Dict[str, Any]]) -> list[Admin]:
    """Convert list of dictionaries to list of Admin models"""
    return [Admin.from_dict(item) for item in data_list]

def exercises_from_list(data_list: list[Dict[str, Any]]) -> list[Exercise]:
    """Convert list of dictionaries to list of Exercise models"""
    return [Exercise.from_dict(item) for item in data_list]

@dataclass
class Workout:
    """Workout session data model"""
    id: Optional[int] = None
    user_id: int = 0
    name: str = ""
    description: Optional[str] = None
    workout_date: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    completed: bool = False
    comments: Optional[List[Dict[str, str]]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Validate workout data after initialization"""
        if not self.name.strip():
            raise ValueError("Workout name cannot be empty")
        if self.user_id <= 0:
            raise ValueError("Valid user_id is required")
        if self.duration_minutes is not None and self.duration_minutes <= 0:
            raise ValueError("Duration must be greater than 0")
        if self.comments is None:
            self.comments = []
        elif not isinstance(self.comments, list):
            raise ValueError("Comments must be a list of dictionaries")
        else:
            # Validate comment structure
            for comment in self.comments:
                if not isinstance(comment, dict):
                    raise ValueError("Each comment must be a dictionary")
                if not all(key in comment for key in ['author', 'message', 'timestamp']):
                    raise ValueError("Each comment must have 'author', 'message', and 'timestamp' fields")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Workout':
        """Create Workout instance from dictionary"""
        # Handle comments - can be JSON string, list, or None
        comments_data = data.get('comments')
        if comments_data is None:
            comments = []
        elif isinstance(comments_data, str):
            try:
                comments = json.loads(comments_data) if comments_data else []
            except json.JSONDecodeError:
                comments = []
        elif isinstance(comments_data, list):
            comments = comments_data
        else:
            comments = []
            
        return cls(
            id=data.get('id'),
            user_id=data.get('user_id', 0),
            name=data.get('name', ''),
            description=data.get('description'),
            workout_date=data.get('workout_date'),
            duration_minutes=data.get('duration_minutes'),
            completed=data.get('completed', False),
            comments=comments,
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Workout instance to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'description': self.description,
            'workout_date': self.workout_date,
            'duration_minutes': self.duration_minutes,
            'completed': self.completed,
            'comments': self.comments or [],
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def add_comment(self, author: str, message: str) -> None:
        """Add a new comment to the workout"""
        if self.comments is None:
            self.comments = []
        
        new_comment = {
            'author': author,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        self.comments.append(new_comment)
    
    def get_comments(self) -> List[Dict[str, str]]:
        """Get all comments for the workout"""
        return self.comments or []
    
    def get_latest_comment(self) -> Optional[Dict[str, str]]:
        """Get the most recent comment"""
        if not self.comments:
            return None
        return self.comments[-1]
    
    def comment_count(self) -> int:
        """Get the total number of comments"""
        return len(self.comments or [])

@dataclass
class ExerciseSet:
    """Exercise set within a workout data model"""
    id: Optional[int] = None
    workout_id: int = 0
    exercise_id: int = 0
    set_order: int = 1
    reps: Optional[int] = None
    weight_kg: Optional[float] = None
    duration_s: Optional[int] = None
    distance_m: Optional[float] = None
    rest_seconds: Optional[int] = None
    completed: bool = False
    comments: Optional[List[Dict[str, str]]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Validate exercise set data after initialization"""
        if self.workout_id <= 0:
            raise ValueError("Valid workout_id is required")
        if self.exercise_id <= 0:
            raise ValueError("Valid exercise_id is required")
        if self.set_order <= 0:
            raise ValueError("Set order must be greater than 0")
        if self.reps is not None and self.reps <= 0:
            raise ValueError("Reps must be greater than 0")
        if self.weight_kg is not None and self.weight_kg <= 0:
            raise ValueError("Weight must be greater than 0")
        if self.duration_s is not None and self.duration_s <= 0:
            raise ValueError("Duration must be greater than 0")
        if self.distance_m is not None and self.distance_m <= 0:
            raise ValueError("Distance must be greater than 0")
        if self.comments is None:
            self.comments = []
        elif not isinstance(self.comments, list):
            raise ValueError("Comments must be a list of dictionaries")
        else:
            # Validate comment structure
            for comment in self.comments:
                if not isinstance(comment, dict):
                    raise ValueError("Each comment must be a dictionary")
                if not all(key in comment for key in ['author', 'message', 'timestamp']):
                    raise ValueError("Each comment must have 'author', 'message', and 'timestamp' fields")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExerciseSet':
        """Create ExerciseSet instance from dictionary"""
        # Handle comments - can be JSON string, list, or None
        comments_data = data.get('comments')
        if comments_data is None:
            comments = []
        elif isinstance(comments_data, str):
            try:
                comments = json.loads(comments_data) if comments_data else []
            except json.JSONDecodeError:
                comments = []
        elif isinstance(comments_data, list):
            comments = comments_data
        else:
            comments = []
            
        return cls(
            id=data.get('id'),
            workout_id=data.get('workout_id', 0),
            exercise_id=data.get('exercise_id', 0),
            set_order=data.get('set_order', 1),
            reps=data.get('reps'),
            weight_kg=data.get('weight_kg'),
            duration_s=data.get('duration_s'),
            distance_m=data.get('distance_m'),
            rest_seconds=data.get('rest_seconds'),
            completed=data.get('completed', False),
            comments=comments,
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert ExerciseSet instance to dictionary"""
        return {
            'id': self.id,
            'workout_id': self.workout_id,
            'exercise_id': self.exercise_id,
            'set_order': self.set_order,
            'reps': self.reps,
            'weight_kg': self.weight_kg,
            'duration_s': self.duration_s,
            'distance_m': self.distance_m,
            'rest_seconds': self.rest_seconds,
            'completed': self.completed,
            'comments': self.comments or [],
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @property
    def has_data(self) -> bool:
        """Check if the set has any performance data"""
        return any([
            self.reps is not None,
            self.weight_kg is not None,
            self.duration_s is not None,
            self.distance_m is not None
        ])
    
    def add_comment(self, author: str, message: str) -> None:
        """Add a new comment to the exercise set"""
        if self.comments is None:
            self.comments = []
        
        new_comment = {
            'author': author,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        self.comments.append(new_comment)
    
    def get_comments(self) -> List[Dict[str, str]]:
        """Get all comments for the exercise set"""
        return self.comments or []
    
    def get_latest_comment(self) -> Optional[Dict[str, str]]:
        """Get the most recent comment"""
        if not self.comments:
            return None
        return self.comments[-1]
    
    def comment_count(self) -> int:
        """Get the total number of comments"""
        return len(self.comments or [])

# Utility functions for new models
def dict_to_workout(data: Dict[str, Any]) -> Workout:
    """Convert dictionary to Workout model"""
    return Workout.from_dict(data)

def dict_to_exercise_set(data: Dict[str, Any]) -> ExerciseSet:
    """Convert dictionary to ExerciseSet model"""
    return ExerciseSet.from_dict(data)

def workouts_from_list(data_list: list[Dict[str, Any]]) -> list[Workout]:
    """Convert list of dictionaries to list of Workout models"""
    return [Workout.from_dict(item) for item in data_list]

def exercise_sets_from_list(data_list: list[Dict[str, Any]]) -> list[ExerciseSet]:
    """Convert list of dictionaries to list of ExerciseSet models"""
    return [ExerciseSet.from_dict(item) for item in data_list]