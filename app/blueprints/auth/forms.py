import re
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import (DataRequired, Email, EqualTo, Length, Regexp, ValidationError)
from app.models.user import User


def _validate_password_strength(form, field):
    password = field.data
    if not re.search(r'[A-Za-z]', password):
        raise ValidationError('Password must contain at least one letter.')
    if not re.search(r'\d', password):
        raise ValidationError('Password must contain at least one number.')


class LoginForm(FlaskForm):
    username = StringField(
        'Username or Email',
        validators=[DataRequired(), Length(max=120)],
        render_kw={'placeholder': 'Username or email', 'autofocus': True},
    )
    password = PasswordField(
        'Password',
        validators=[DataRequired()],
        render_kw={'placeholder': 'Password'},
    )
    remember_me = BooleanField('Keep me signed in')
    submit = SubmitField('Sign In')


class RegisterForm(FlaskForm):
    username = StringField(
        'Username',
        validators=[
            DataRequired(),
            Length(min=3, max=80),
            Regexp(
                r'^[\w.-]+$',
                message='Username may only contain letters, numbers, dots, hyphens, and underscores.',
            ),
        ],
        render_kw={'placeholder': 'Choose a username'},
    )
    email = StringField(
        'Email',
        validators=[DataRequired(), Email(), Length(max=120)],
        render_kw={'placeholder': 'your@email.com'},
    )
    first_name = StringField(
        'First Name',
        validators=[DataRequired(), Length(max=80)],
        render_kw={'placeholder': 'First name'},
    )
    last_name = StringField(
        'Last Name',
        validators=[DataRequired(), Length(max=80)],
        render_kw={'placeholder': 'Last name'},
    )
    phone = StringField(
        'Phone (optional)',
        validators=[Length(max=20)],
        render_kw={'placeholder': '+94 xx xxx xxxx'},
    )
    password = PasswordField(
        'Password',
        validators=[
            DataRequired(),
            Length(min=8, message='Password must be at least 8 characters.'),
            _validate_password_strength,
        ],
        render_kw={'placeholder': 'Min. 8 characters'},
    )
    confirm_password = PasswordField(
        'Confirm Password',
        validators=[DataRequired(), EqualTo('password', message='Passwords must match.')],
        render_kw={'placeholder': 'Repeat password'},
    )
    submit = SubmitField('Create Account')

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('That username is already taken.')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('That email address is already registered.')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField(
        'Current Password',
        validators=[DataRequired()],
        render_kw={'placeholder': 'Current password'},
    )
    new_password = PasswordField(
        'New Password',
        validators=[
            DataRequired(),
            Length(min=8, message='Password must be at least 8 characters.'),
            _validate_password_strength,
        ],
        render_kw={'placeholder': 'New password'},
    )
    confirm_password = PasswordField(
        'Confirm New Password',
        validators=[DataRequired(), EqualTo('new_password', message='Passwords must match.')],
        render_kw={'placeholder': 'Repeat new password'},
    )
    submit = SubmitField('Update Password')
