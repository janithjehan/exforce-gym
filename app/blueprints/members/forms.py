import re
from datetime import date
from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, SelectField, TextAreaField,
    DateField, SubmitField
)
from wtforms.validators import (
    DataRequired, Email, EqualTo, Length, Optional, Regexp, ValidationError
)
from app.models.user import User
from app.models.member import Gender


def _validate_password_strength(form, field):
    if not field.data:
        return
    if not re.search(r'[A-Za-z]', field.data):
        raise ValidationError('Password must contain at least one letter.')
    if not re.search(r'\d', field.data):
        raise ValidationError('Password must contain at least one number.')


# ------------------------------------------------------------------ #
#  Admin: Create a brand-new member (User account + Member profile)   #
# ------------------------------------------------------------------ #

class MemberCreateForm(FlaskForm):
    # --- User account section ---
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

    # --- Member profile section ---
    contact_no = StringField(
        'Contact No',
        validators=[DataRequired(), Length(max=20)],
        render_kw={'placeholder': '+94 xx xxx xxxx'},
    )
    address = TextAreaField('Address', validators=[Optional(), Length(max=500)],
                            render_kw={'rows': 2})
    join_date = DateField('Join Date', validators=[DataRequired()], default=date.today)
    date_of_birth = DateField('Date of Birth', validators=[Optional()])
    gender = SelectField(
        'Gender',
        choices=[('', '— Select —')] + [(g.value, g.label) for g in Gender],
        validators=[Optional()],
    )
    emergency_contact_name = StringField(
        'Emergency Contact Name', validators=[Optional(), Length(max=100)]
    )
    emergency_contact_no = StringField(
        'Emergency Contact No', validators=[Optional(), Length(max=20)]
    )
    notes = TextAreaField('Admin Notes', validators=[Optional(), Length(max=1000)],
                          render_kw={'rows': 2})

    submit = SubmitField('Create Member')

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('Username already taken.')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower()).first():
            raise ValidationError('Email already registered.')

    def validate_join_date(self, field):
        if field.data and field.data > date.today():
            raise ValidationError('Join date cannot be in the future.')

    def validate_date_of_birth(self, field):
        if field.data and field.data > date.today():
            raise ValidationError('Date of birth cannot be in the future.')


# ------------------------------------------------------------------ #
#  Admin: Edit Member profile                                         #
# ------------------------------------------------------------------ #

class MemberEditForm(FlaskForm):
    # User fields (convenience — name and phone)
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=80)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=80)])
    phone = StringField('Phone (User Account)', validators=[Optional(), Length(max=20)])

    # Member profile fields
    contact_no = StringField(
        'Contact No',
        validators=[DataRequired(), Length(max=20)],
        render_kw={'placeholder': '+94 xx xxx xxxx'},
    )
    address = TextAreaField('Address', validators=[Optional(), Length(max=500)],
                            render_kw={'rows': 2})
    join_date = DateField('Join Date', validators=[DataRequired()])
    date_of_birth = DateField('Date of Birth', validators=[Optional()])
    gender = SelectField(
        'Gender',
        choices=[('', '— Select —')] + [(g.value, g.label) for g in Gender],
        validators=[Optional()],
    )
    emergency_contact_name = StringField(
        'Emergency Contact Name', validators=[Optional(), Length(max=100)]
    )
    emergency_contact_no = StringField(
        'Emergency Contact No', validators=[Optional(), Length(max=20)]
    )
    notes = TextAreaField('Admin Notes', validators=[Optional(), Length(max=1000)],
                          render_kw={'rows': 3})

    submit = SubmitField('Save Changes')

    def validate_join_date(self, field):
        if field.data and field.data > date.today():
            raise ValidationError('Join date cannot be in the future.')

    def validate_date_of_birth(self, field):
        if field.data and field.data > date.today():
            raise ValidationError('Date of birth cannot be in the future.')
