from flask import request
from flask_wtf import FlaskForm
from wtforms import TextAreaField, StringField, SubmitField
from wtforms.validators import DataRequired, Optional, Length, ValidationError

from app.models.configuration import AppConfiguration
from app.models.equipment_category import EquipmentCategory
from app.models.workout_category import WorkoutCategory


class ConfigurationForm(FlaskForm):
    bank_transfer_details = TextAreaField(
        'Bank Transfer Details',
        validators=[Optional(), Length(max=2000)],
        render_kw={
            'rows': 6,
            'placeholder': 'Bank: ...\nAccount Name: ...\nAccount No: ...\nBranch: ...',
        },
    )
    installment_options = StringField(
        'Available Installment Counts',
        validators=[Optional(), Length(max=100)],
        render_kw={'placeholder': 'e.g. 2,3,4,6,12'},
    )
    submit = SubmitField('Save Configuration')

    def validate_installment_options(self, field):
        """Every comma-separated token must parse as an integer >= 2."""
        raw = (field.data or '').strip()
        if not raw:
            return
        for token in raw.split(','):
            token = token.strip()
            if not token:
                continue
            try:
                n = int(token)
            except ValueError:
                raise ValidationError(f'"{token}" is not a whole number.')
            if n < 2:
                raise ValidationError('Installment counts must be 2 or more (1 installment is just paying in full).')


class EquipmentCategoryForm(FlaskForm):
    name = StringField('Category Name', validators=[DataRequired(), Length(max=100)])
    submit = SubmitField('Save Category')

    def validate_name(self, field):
        """Reject names that collide (case-insensitively) with another category."""
        category_id = request.view_args.get('category_id')
        query = EquipmentCategory.query.filter(EquipmentCategory.name.ilike(field.data.strip()))
        if category_id:
            query = query.filter(EquipmentCategory.id != category_id)
        if query.first():
            raise ValidationError('A category with this name already exists.')

class WorkoutCategoryForm(FlaskForm):
    name = StringField('Category Name', validators=[DataRequired(), Length(max=100)])
    submit = SubmitField('Save Category')

    def validate_name(self, field):
        """Reject names that collide (case-insensitively) with another category."""
        category_id = request.view_args.get('category_id')
        query = WorkoutCategory.query.filter(WorkoutCategory.name.ilike(field.data.strip()))
        if category_id:
            query = query.filter(WorkoutCategory.id != category_id)
        if query.first():
            raise ValidationError('A category with this name already exists.')