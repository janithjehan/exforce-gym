import enum
from datetime import datetime
from app.extensions import db


class WorkoutType(enum.Enum):
    STRENGTH = 'strength'
    CARDIO = 'cardio'
    FLEXIBILITY = 'flexibility'
    BALANCE = 'balance'
    ENDURANCE = 'endurance'

    @property
    def label(self):
        return {
            'strength': 'Strength',
            'cardio': 'Cardio',
            'flexibility': 'Flexibility',
            'balance': 'Balance',
            'endurance': 'Endurance',
        }[self.value]


class MuscleGroup(enum.Enum):
    CHEST = 'chest'
    BACK = 'back'
    SHOULDERS = 'shoulders'
    BICEPS = 'biceps'
    TRICEPS = 'triceps'
    LEGS = 'legs'
    GLUTES = 'glutes'
    CORE = 'core'
    FULL_BODY = 'full_body'

    @property
    def label(self):
        return {
            'chest': 'Chest',
            'back': 'Back',
            'shoulders': 'Shoulders',
            'biceps': 'Biceps',
            'triceps': 'Triceps',
            'legs': 'Legs',
            'glutes': 'Glutes',
            'core': 'Core',
            'full_body': 'Full Body',
        }[self.value]


class DifficultyLevel(enum.Enum):
    BEGINNER = 'beginner'
    INTERMEDIATE = 'intermediate'
    ADVANCED = 'advanced'

    @property
    def label(self):
        return self.value.capitalize()

    @property
    def badge_class(self):
        return {
            'beginner': 'success',
            'intermediate': 'warning',
            'advanced': 'danger',
        }[self.value]


class Workout(db.Model):
    """Exercise library entry used when building member schedules (SRS 3.8)."""
    __tablename__ = 'workouts'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    workout_type = db.Column(db.Enum(WorkoutType), nullable=False)
    muscle_group = db.Column(db.Enum(MuscleGroup), nullable=False)

    # FR-WRK-01: required metadata
    difficulty = db.Column(
        db.Enum(DifficultyLevel), nullable=False,
        default=DifficultyLevel.BEGINNER,
    )
    equipment_needed = db.Column(db.String(200), nullable=True)  # empty = bodyweight

    instructions = db.Column(db.Text, nullable=True)

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_archived = db.Column(db.Boolean, nullable=False, default=False)

    # Audit
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    created_by = db.relationship('User', foreign_keys=[created_by_id])
    updated_by = db.relationship('User', foreign_keys=[updated_by_id])

    @property
    def equipment_label(self):
        return self.equipment_needed or 'None (bodyweight)'

    @property
    def status_label(self):
        if self.is_archived:
            return 'Archived'
        return 'Active' if self.is_active else 'Inactive'

    @property
    def status_badge_class(self):
        if self.is_archived:
            return 'secondary'
        return 'success' if self.is_active else 'warning'

    def __repr__(self):
        return f'<Workout {self.name} ({self.muscle_group.value}/{self.difficulty.value})>'