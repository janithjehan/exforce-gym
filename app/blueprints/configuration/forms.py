from flask import request
from flask_wtf import FlaskForm
from wtforms import TextAreaField, StringField, SubmitField
from wtforms.validators import DataRequired, Optional, Length, ValidationError

from app.models.configuration import AppConfiguration
from app.models.equipment_category import EquipmentCategory
from app.models.workout_category import WorkoutCategory
from app.models.trainer_category import TrainerCategory


class ConfigurationForm(FlaskForm):
    bank_transfer_details = TextAreaField(
        'Bank Transfer Details',
        validators=[Optional(), Length(max=2000)],
        render_kw={
            'rows': 6,
            'placeholder': 'Bank: ...\nAccount Name: ...\nAccount No: ...\nBranch: ...',
        },
    )
    submit = SubmitField('Save Configuration')


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

class TrainerCategoryForm(FlaskForm):
    name = StringField('Category Name', validators=[DataRequired(), Length(max=100)])
    submit = SubmitField('Save Category')

    def validate_name(self, field):
        """Reject names that collide (case-insensitively) with another category."""
        category_id = request.view_args.get('category_id')
        query = TrainerCategory.query.filter(TrainerCategory.name.ilike(field.data.strip()))
        if category_id:
            query = query.filter(TrainerCategory.id != category_id)
        if query.first():
            raise ValidationError('A category with this name already exists.')