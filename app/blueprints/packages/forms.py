from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, ValidationError
from wtforms.fields import DecimalField
from app.models.package import Package


class PackageForm(FlaskForm):
    name = StringField('Package Name', validators=[DataRequired(), Length(max=100)])
    duration_months = SelectField(
        'Duration',
        choices=[(str(m), label) for m, label in Package.DURATION_CHOICES],
        validators=[DataRequired()],
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
    submit = SubmitField('Save Package')

    def validate_name(self, field):
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
