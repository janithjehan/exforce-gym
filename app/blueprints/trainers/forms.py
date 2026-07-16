import re
from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, TextAreaField, IntegerField, SubmitField
)
from wtforms.validators import (
    DataRequired, Email, EqualTo, Length, Optional, Regexp,
    NumberRange, ValidationError,
)
from app.models.user import User


def _validate_password_strength(form, field):
    if not field.data:
        return
    if not re.search(r'[A-Za-z]', field.data):
        raise ValidationError('Password must contain at least one letter.')
    if not re.search(r'\d', field.data):
        raise ValidationError('Password must contain at least one number.')


class TrainerCreateForm(FlaskForm):
    # User account section
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=80)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=80)])
    username = StringField(
        'Username',
        validators=[
            DataRequired(), Length(min=3, max=80),
            Regexp(r'^[\w.-]+$', message='Letters, numbers, dots, hyphens, underscores only.'),
        ],
    )
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField('Phone', validators=[Optional(), Length(max=20)])
    password = PasswordField(
        'Password',
        validators=[
            DataRequired(),
            Length(min=8, message='Minimum 8 characters.'),
            _validate_password_strength,
        ],
    )
    confirm_password = PasswordField(
        'Confirm Password',
        validators=[DataRequired(), EqualTo('password', message='Passwords must match.')],
    )

    # Trainer profile section
    specialization = StringField(
        'Specialization',
        validators=[Optional(), Length(max=200)],
        render_kw={'placeholder': 'e.g., Weight Training, Yoga, HIIT'},
    )
    bio = TextAreaField('Bio / About', validators=[Optional(), Length(max=1000)],
                        render_kw={'rows': 3, 'placeholder': 'Brief description of the trainer...'})
    experience_years = IntegerField(
        'Years of Experience',
        validators=[Optional(), NumberRange(min=0, max=60)],
    )
    certifications = TextAreaField(
        'Certifications',
        validators=[Optional(), Length(max=500)],
        render_kw={'rows': 2, 'placeholder': 'e.g., ACE-CPT, NASM, CrossFit Level 2'},
    )
    contact_no = StringField(
        'Contact No',
        validators=[DataRequired(), Length(max=20)],
        render_kw={'placeholder': '+94 xx xxx xxxx'},
    )

    submit = SubmitField('Create Trainer')

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('Username already taken.')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower()).first():
            raise ValidationError('Email already registered.')


class TrainerEditForm(FlaskForm):
    # User fields
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=80)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=80)])
    phone = StringField('Phone (User Account)', validators=[Optional(), Length(max=20)])

    # Trainer profile fields
    specialization = StringField(
        'Specialization',
        validators=[Optional(), Length(max=200)],
        render_kw={'placeholder': 'e.g., Weight Training, Yoga, HIIT'},
    )
    bio = TextAreaField('Bio / About', validators=[Optional(), Length(max=1000)],
                        render_kw={'rows': 3})
    experience_years = IntegerField(
        'Years of Experience',
        validators=[Optional(), NumberRange(min=0, max=60)],
    )
    certifications = TextAreaField(
        'Certifications',
        validators=[Optional(), Length(max=500)],
        render_kw={'rows': 2},
    )
    contact_no = StringField(
        'Contact No',
        validators=[Optional(), Length(max=20)],
        render_kw={'placeholder': '+94 xx xxx xxxx'},
    )

    submit = SubmitField('Save Changes')
