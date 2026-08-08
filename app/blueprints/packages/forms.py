from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Length, NumberRange, ValidationError
from wtforms.fields import DecimalField, IntegerField
from app.models.package import Package


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
    installment_options = StringField(
        'Installment Counts Offered',
        validators=[Length(max=100)],
        render_kw={'placeholder': 'e.g. 2,3,4,6'},
    )
    submit = SubmitField('Save Package')

    def validate_installment_options(self, field):
        """Comma-separated whole numbers, 2 or more; required when installments are allowed."""
        raw = (field.data or '').strip()
        if self.allow_installments.data and not raw:
            raise ValidationError('Enter at least one installment count, or turn off "Allow installments".')
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
