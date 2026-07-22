from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length, ValidationError

from app.models.workout import Workout, WorkoutType, MuscleGroup, DifficultyLevel


class WorkoutForm(FlaskForm):
    name = StringField('Workout Name', validators=[DataRequired(), Length(max=100)])
    workout_type = SelectField(
        'Type',
        choices=[(t.value, t.label) for t in WorkoutType],
        validators=[DataRequired()],
    )
    muscle_group = SelectField(
        'Muscle Group',
        choices=[(m.value, m.label) for m in MuscleGroup],
        validators=[DataRequired()],
    )
    difficulty = SelectField(
        'Difficulty Level',
        choices=[(d.value, d.label) for d in DifficultyLevel],
        validators=[DataRequired()],
    )
    equipment_needed = StringField(
        'Equipment Needed',
        validators=[Length(max=200)],
        render_kw={'placeholder': 'e.g. Barbell, Bench — leave empty for bodyweight'},
    )
    instructions = TextAreaField(
        'Instructions',
        validators=[Length(max=3000)],
        render_kw={'rows': 5, 'placeholder': 'Step-by-step execution notes, form cues, sets/reps guidance...'},
    )
    submit = SubmitField('Save Workout')

    def validate_name(self, field):
        from flask import request
        workout_id = request.view_args.get('workout_id')
        query = Workout.query.filter(
            Workout.name.ilike(field.data.strip()),
            Workout.is_archived == False,
        )
        if workout_id:
            query = query.filter(Workout.id != workout_id)
        if query.first():
            raise ValidationError('A workout with this name already exists.')