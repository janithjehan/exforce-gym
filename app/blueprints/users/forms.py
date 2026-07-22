import re
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, BooleanField, SubmitField
from wtforms.validators import (DataRequired, Email, EqualTo, Length, Optional, Regexp, ValidationError)
from app.extensions import db
from app.models.user import User, UserRole
from app.utils.validators import validate_nic_format


def _validate_password_strength(form, field):
    if not field.data:
        return
    password = field.data
    if not re.search(r'[A-Za-z]', password):
        raise ValidationError('Password must contain at least one letter.')
    if not re.search(r'\d', password):
        raise ValidationError('Password must contain at least one number.')


def _require_contact_fields(form):
    """Mobile number and NIC are mandatory for every role except Admin."""
    ok = True
    if form.role.data != UserRole.ADMIN.value:
        label = UserRole(form.role.data).label if form.role.data in [r.value for r in UserRole] else 'this'
        if not (form.phone.data or '').strip():
            form.phone.errors.append(f'Mobile number is required for {label} accounts.')
            ok = False
        if not (form.nic_no.data or '').strip():
            form.nic_no.errors.append(f'NIC number is required for {label} accounts.')
            ok = False
    return ok


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
    phone = StringField('Mobile Number', validators=[Optional(), Length(max=20)])
    nic_no = StringField('NIC Number', validators=[Optional(), Length(max=20), validate_nic_format])
    role = SelectField(
        'Role',
        choices=[(r.value, r.label) for r in UserRole],
        validators=[DataRequired()],
    )
    is_active = BooleanField('Active', default=True)
    # No password fields — the initial password is the NIC number
    submit = SubmitField('Create User')

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('That username is already taken.')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower()).first():
            raise ValidationError('That email address is already registered.')

    def validate_nic_no(self, field):
        if field.data and field.data.strip():
            nic = field.data.strip().upper()
            if User.query.filter(db.func.upper(User.nic_no) == nic).first():
                raise ValidationError('That NIC number is already registered.')

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators) & _require_contact_fields(self)
        # NIC doubles as the initial password, so it's required even for Admins
        if not (self.nic_no.data or '').strip() and not self.nic_no.errors:
            self.nic_no.errors.append('NIC number is required - it is used as the initial password.')
            ok = False
        return ok


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
    phone = StringField('Mobile Number', validators=[Optional(), Length(max=20)])
    nic_no = StringField('NIC Number', validators=[Optional(), Length(max=20), validate_nic_format])
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

    def validate_nic_no(self, field):
        if field.data and field.data.strip():
            nic = field.data.strip().upper()
            existing = User.query.filter(db.func.upper(User.nic_no) == nic).first()
            if existing and existing.id != self._user_id:
                raise ValidationError('That NIC number is already registered.')

    def validate(self, extra_validators=None):
        return super().validate(extra_validators) & _require_contact_fields(self)


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
