from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import (DataRequired, Email, EqualTo, Length, ValidationError)
from app.models.user import User


def _validate_password_strength(form, field):
    password = field.data
    has_letter = any(char.isalpha() for char in password)
    has_digit = any(char.isdigit() for char in password)

    if not has_letter:
        raise ValidationError('Password must contain at least one letter.')
    if not has_digit:
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
    submit = SubmitField('Sign In')


class RegisterForm(FlaskForm):
    username = StringField(
        'Username',
        validators=[
            DataRequired(),
            Length(min=3, max=80),
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
        username = field.data
        for char in username:
            if not (char.isalnum() or char in '.-_'):
                raise ValidationError(
                    'Username may only contain letters, numbers, dots, hyphens, and underscores.'
                )

        if User.query.filter_by(username=username).first():
            raise ValidationError('That username is already taken.')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('That email address is already registered.')


class ForgotPasswordForm(FlaskForm):
    email = StringField(
        'Email',
        validators=[DataRequired(), Email(), Length(max=120)],
        render_kw={'placeholder': 'your@email.com', 'autofocus': True},
    )
    submit = SubmitField('Send Reset Link')


class ResetPasswordForm(FlaskForm):
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
    submit = SubmitField('Reset Password')


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
