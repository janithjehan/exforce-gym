from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, BooleanField, SelectMultipleField
from wtforms.validators import DataRequired, Length, NumberRange, ValidationError
from wtforms.fields import DecimalField, IntegerField
from app.models.package import Package
from app.models.configuration import AppConfiguration


class PackageForm(FlaskForm):
    name = StringField('Package Name', validators=[DataRequired(), Length(max=100)])
    duration_months = IntegerField(
        'Duration (Months)',
        validators=[DataRequired(), NumberRange(min=1, message='Duration must be at least 1 month.')],
    )
    price = DecimalField(
        'Price (LKR)',
        places=2,
        validators=[DataRequired(), NumberRange(min=0, message='Price must be a positive value.')],
    )
    description = TextAreaField(
        'Benefits / Description',
        validators=[Length(max=1000)],
        render_kw={'rows': 3, 'placeholder': 'List what this package includes...'},
    )
    allow_installments = BooleanField('Allow members to pay in installments')
    installment_options = SelectMultipleField(
        'Installment Counts Offered', coerce=int, validators=[],
    )
    submit = SubmitField('Save Package')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        global_options = AppConfiguration.get().installment_options_list
        self.installment_options.choices = [(n, f'{n} installments') for n in global_options]

    def validate_installment_options(self, field):
        if self.allow_installments.data and not field.data:
            raise ValidationError('Select at least one installment count, or turn off "Allow installments".')

    def validate_name(self, field):
        """Reject names that collide (case-insensitively) with another non-archived package."""
        from flask import request
        pkg_id = request.view_args.get('package_id')
        query = Package.query.filter(
            Package.name.ilike(field.data.strip()),
            Package.is_archived == False,
        )
        if pkg_id:
            query = query.filter(Package.id != pkg_id)
        if query.first():
            raise ValidationError('A package with this name already exists.')
