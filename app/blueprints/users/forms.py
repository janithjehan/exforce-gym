import re
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, BooleanField, SubmitField
from wtforms.validators import (DataRequired, Email, EqualTo, Length, Optional, Regexp, ValidationError)
from app.models.user import User, UserRole


def _validate_password_strength(form, field):
    if not field.data:
        return
    password = field.data
    if not re.search(r'[A-Za-z]', password):
        raise ValidationError('Password must contain at least one letter.')
    if not re.search(r'\d', password):
        raise ValidationError('Password must contain at least one number.')


class UserCreateForm(FlaskForm):
    username = StringField(
        'Username',
        validators=[
            DataRequired(), Length(min=3, max=80),
            Regexp(r'^[\w.-]+$', message='Username may only contain letters, numbers, dots, hyphens, and underscores.'),
        ],
    )
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=80)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=80)])
    phone = StringField('Phone', validators=[Optional(), Length(max=20)])
    role = SelectField(
        'Role',
        choices=[(r.value, r.label) for r in UserRole],
        validators=[DataRequired()],
    )
    is_active = BooleanField('Active', default=True)
    password = PasswordField(
        'Password',
        validators=[
            DataRequired(),
            Length(min=8, message='Password must be at least 8 characters.'),
            _validate_password_strength,
        ],
    )
    confirm_password = PasswordField(
        'Confirm Password',
        validators=[DataRequired(), EqualTo('password', message='Passwords must match.')],
    )
    submit = SubmitField('Create User')

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('That username is already taken.')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower()).first():
            raise ValidationError('That email address is already registered.')


class UserEditForm(FlaskForm):
    username = StringField(
        'Username',
        validators=[
            DataRequired(), Length(min=3, max=80),
            Regexp(r'^[\w.-]+$', message='Username may only contain letters, numbers, dots, hyphens, and underscores.'),
        ],
    )
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=80)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=80)])
    phone = StringField('Phone', validators=[Optional(), Length(max=20)])
    role = SelectField(
        'Role',
        choices=[(r.value, r.label) for r in UserRole],
        validators=[DataRequired()],
    )
    is_active = BooleanField('Active')
    # Password optional on edit — blank = no change
    password = PasswordField(
        'New Password (leave blank to keep current)',
        validators=[
            Optional(),
            Length(min=8, message='Password must be at least 8 characters.'),
            _validate_password_strength,
        ],
    )
    confirm_password = PasswordField(
        'Confirm New Password',
        validators=[Optional(), EqualTo('password', message='Passwords must match.')],
    )
    submit = SubmitField('Save Changes')

    def __init__(self, user_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._user_id = user_id

    def validate_username(self, field):
        existing = User.query.filter_by(username=field.data).first()
        if existing and existing.id != self._user_id:
            raise ValidationError('That username is already taken.')

    def validate_email(self, field):
        existing = User.query.filter_by(email=field.data.lower()).first()
        if existing and existing.id != self._user_id:
            raise ValidationError('That email address is already registered.')


class AdminResetPasswordForm(FlaskForm):
    new_password = PasswordField(
        'New Password',
        validators=[
            DataRequired(),
            Length(min=8, message='Password must be at least 8 characters.'),
            _validate_password_strength,
        ],
    )
    confirm_password = PasswordField(
        'Confirm Password',
        validators=[DataRequired(), EqualTo('new_password', message='Passwords must match.')],
    )
    submit = SubmitField('Reset Password')
