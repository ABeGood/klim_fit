from dataclasses import dataclass
from typing import Dict, Any, Optional
from datetime import datetime

@dataclass
class User:
    """User data model"""
    id: Optional[int] = None
    name: str = ""
    surname: str = ""
    email: str = ""
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