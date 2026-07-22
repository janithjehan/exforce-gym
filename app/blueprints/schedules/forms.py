from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DateField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Optional, Length, ValidationError


class ScheduleForm(FlaskForm):
    """Header fields only — workout item rows are dynamic and parsed in the route."""
    member_id = SelectField('Member', coerce=int, validators=[DataRequired()])
    trainer_id = SelectField('Trainer', coerce=int, validators=[DataRequired()])
    title = StringField(
        'Plan Title', validators=[DataRequired(), Length(max=150)],
        render_kw={'placeholder': 'e.g. 4-Week Strength Foundation'},
    )
    start_date = DateField('Start Date', validators=[DataRequired()])
    end_date = DateField('End Date', validators=[DataRequired()])
    notes = TextAreaField(
        'Notes', validators=[Optional(), Length(max=1000)],
        render_kw={'rows': 2, 'placeholder': 'Goals, cautions, or general guidance for this plan...'},
    )
    submit = SubmitField('Save Schedule')

    def validate_end_date(self, field):
        if field.data and self.start_date.data and field.data < self.start_date.data:
            raise ValidationError('End date cannot be before the start date.')


def parse_item_rows(form_data):
    """Parse the dynamic workout item rows posted by the schedule form.

    Returns (items, errors) where items is a list of dicts ready for
    ScheduleItem(**item). FR-SCH-01: every row needs workout, sets, reps, rest.
    """
    workout_ids = form_data.getlist('item_workout_id')
    day_labels = form_data.getlist('item_day_label')
    sets_list = form_data.getlist('item_sets')
    reps_list = form_data.getlist('item_reps')
    rest_list = form_data.getlist('item_rest_seconds')
    notes_list = form_data.getlist('item_notes')

    items, errors = [], []
    row_no = 0
    for i, workout_id in enumerate(workout_ids):
        # Skip rows the user left fully empty
        if not any([
            workout_id.strip(),
            day_labels[i].strip() if i < len(day_labels) else '',
            sets_list[i].strip() if i < len(sets_list) else '',
            reps_list[i].strip() if i < len(reps_list) else '',
        ]):
            continue
        row_no += 1

        if not workout_id.strip():
            errors.append(f'Row {row_no}: select a workout.')
            continue

        day_label = (day_labels[i] if i < len(day_labels) else '').strip()
        if not day_label:
            errors.append(f'Row {row_no}: enter a day (e.g. Monday or Day 1).')
            continue

        try:
            sets = int(sets_list[i])
            if not 1 <= sets <= 20:
                raise ValueError
        except (ValueError, IndexError):
            errors.append(f'Row {row_no}: sets must be a number between 1 and 20.')
            continue

        reps = (reps_list[i] if i < len(reps_list) else '').strip()
        if not reps or len(reps) > 20:
            errors.append(f'Row {row_no}: enter reps (e.g. 12 or 8-12).')
            continue

        try:
            rest_seconds = int(rest_list[i])
            if not 0 <= rest_seconds <= 900:
                raise ValueError
        except (ValueError, IndexError):
            errors.append(f'Row {row_no}: rest must be 0-900 seconds.')
            continue

        notes = (notes_list[i] if i < len(notes_list) else '').strip()[:200] or None

        items.append({
            'workout_id': int(workout_id),
            'day_label': day_label[:30],
            'sets': sets,
            'reps': reps,
            'rest_seconds': rest_seconds,
            'notes': notes,
            'sort_order': len(items),
        })

    if not items and not errors:
        errors.append('Add at least one workout item to the schedule.')
    return items, errors