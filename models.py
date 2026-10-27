from dataclasses import dataclass, fields
from typing import Dict, Any, Optional, ClassVar, List
from datetime import datetime, date
from decimal import Decimal

# Measurable values a set can carry; an exercise's has_<name> flags say which ones it needs.
PARAMS = ('reps', 'weight_kg', 'duration_s', 'distance_m')


class RowModel:
    """Shared DB-row mapping: from_dict ignores unknown keys (e.g. joined columns),
    falls back to field defaults for missing/NULL values and turns Decimal into float."""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        kwargs = {}
        for f in fields(cls):
            if f.name in data and data[f.name] is not None:
                value = data[f.name]
                kwargs[f.name] = float(value) if isinstance(value, Decimal) else value
        return cls(**kwargs)

    def to_dict(self) -> Dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


def _check_positive(obj, names):
    for name in names:
        value = getattr(obj, name)
        if value is not None and value <= 0:
            raise ValueError(f"{name} must be greater than 0")


@dataclass
class Account(RowModel):
    """A login: role 'admin' (coach) or 'client'"""
    id: Optional[int] = None
    role: str = 'client'
    name: str = ""
    surname: str = ""
    email: str = ""
    password_hash: Optional[str] = None
    google_id: Optional[str] = None
    profile_picture: Optional[str] = None
    age: Optional[int] = None
    weight_kg: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    ROLES: ClassVar[tuple] = ('admin', 'client')

    def __post_init__(self):
        if self.role not in self.ROLES:
            raise ValueError(f"Role must be one of {self.ROLES}")
        if self.email and '@' not in self.email:
            raise ValueError("Invalid email format")
        if self.age is not None and (self.age <= 0 or self.age >= 150):
            raise ValueError("Age must be between 1 and 149")
        _check_positive(self, ['weight_kg'])

    @property
    def full_name(self) -> str:
        return f"{self.name} {self.surname}".strip()

    @property
    def is_admin(self) -> bool:
        return self.role == 'admin'

    def to_public_dict(self) -> Dict[str, Any]:
        """Account data safe to send to the browser (no password hash / google id)"""
        return {
            'id': self.id,
            'role': self.role,
            'name': self.name,
            'surname': self.surname,
            'full_name': self.full_name,
            'email': self.email,
            'profile_picture': self.profile_picture,
            'age': self.age,
            'weight_kg': self.weight_kg,
            'created_at': self.created_at
        }


@dataclass
class Exercise(RowModel):
    """Library exercise: the template for a set. has_* flags say which values a set needs."""
    id: Optional[int] = None
    name: str = ""
    description: Optional[str] = None
    has_reps: bool = False
    has_weight_kg: bool = False
    has_duration_s: bool = False
    has_distance_m: bool = False
    archived_at: Optional[datetime] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if not self.name.strip():
            raise ValueError("Exercise name cannot be empty")
        if not self.parameter_types:
            raise ValueError("Exercise must have at least one parameter type")

    @property
    def parameter_types(self) -> List[str]:
        return [p for p in PARAMS if getattr(self, 'has_' + p)]

    @property
    def parameter_summary(self) -> str:
        return ", ".join(self.parameter_types) or "No parameters"


@dataclass
class WorkoutTemplate(RowModel):
    """A coach's reusable plan; only 'ready' templates can be assigned"""
    id: Optional[int] = None
    created_by: Optional[int] = None
    name: str = ""
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    note: Optional[str] = None
    status: str = 'draft'
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    STATUSES: ClassVar[tuple] = ('draft', 'ready')

    def __post_init__(self):
        if not self.name.strip():
            raise ValueError("Template name cannot be empty")
        if self.status not in self.STATUSES:
            raise ValueError(f"Status must be one of {self.STATUSES}")
        _check_positive(self, ['duration_minutes'])


@dataclass
class Workout(RowModel):
    """A client's workout, copied from a template on assignment"""
    id: Optional[int] = None
    client_id: int = 0
    template_id: Optional[int] = None
    assigned_by: Optional[int] = None
    name: str = ""
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    note: Optional[str] = None
    scheduled_date: Optional[date] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if not self.name.strip():
            raise ValueError("Workout name cannot be empty")
        if self.client_id <= 0:
            raise ValueError("Valid client_id is required")
        _check_positive(self, ['duration_minutes'])

    @property
    def completed(self) -> bool:
        return self.completed_at is not None


@dataclass
class Group(RowModel):
    """An ordered group of sets (may mix exercises). Shared by template_groups and workout_groups;
    parent_id is template_id or workout_id respectively."""
    id: Optional[int] = None
    parent_id: int = 0
    position: int = 1
    name: Optional[str] = None
    note: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        _check_positive(self, ['position'])


@dataclass
class Set(RowModel):
    """One performance of an exercise inside a group. Shared by template_sets and workout_sets;
    actual_* and completed_at only exist (and are only filled) on workout sets."""
    id: Optional[int] = None
    group_id: int = 0
    position: int = 1
    exercise_id: int = 0
    target_reps: Optional[int] = None
    target_weight_kg: Optional[float] = None
    target_duration_s: Optional[int] = None
    target_distance_m: Optional[float] = None
    actual_reps: Optional[int] = None
    actual_weight_kg: Optional[float] = None
    actual_duration_s: Optional[int] = None
    actual_distance_m: Optional[float] = None
    rest_seconds: Optional[int] = None
    note: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        _check_positive(self, ['position'] + ['target_' + p for p in PARAMS] + ['actual_' + p for p in PARAMS])
        if self.rest_seconds is not None and self.rest_seconds < 0:
            raise ValueError("Rest seconds cannot be negative")


@dataclass
class Comment(RowModel):
    """Coach <-> client chat message attached to exactly one of: workout, group, set"""
    id: Optional[int] = None
    author_id: int = 0
    workout_id: Optional[int] = None
    group_id: Optional[int] = None
    set_id: Optional[int] = None
    body: str = ""
    created_at: Optional[datetime] = None
    edited_at: Optional[datetime] = None

    def __post_init__(self):
        if not self.body.strip():
            raise ValueError("Comment cannot be empty")
        if sum(x is not None for x in (self.workout_id, self.group_id, self.set_id)) != 1:
            raise ValueError("A comment must be attached to exactly one workout, group or set")
