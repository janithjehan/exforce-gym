from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, ValidationError

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
    equipment_needed = SelectField(
        'Equipment Needed',
        choices=[],
        validators=[Optional()],
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

    def load_equipment_choices(self, current=None):
        """Populate the equipment dropdown from the active inventory.

        `current` keeps a legacy free-text value (not in the inventory) as a
        selectable option so editing an old workout never silently drops it.
        """
        from app.models.equipment import Equipment
        items = Equipment.query.filter_by(is_archived=False).order_by(Equipment.name.asc()).all()
        choices = [('', 'None (bodyweight)')]
        choices += [(e.name, e.name) for e in items]
        names = {e.name for e in items}
        if current and current not in names:
            choices.append((current, f'{current} (not in inventory)'))
        self.equipment_needed.choices = choices