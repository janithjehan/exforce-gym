from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField, IntegerField, SubmitField
)
from wtforms.validators import (
    DataRequired, Email, Length, Optional, Regexp,
    NumberRange, ValidationError,
)
from app.models.user import User
from app.utils.validators import validate_nic_format, nic_taken


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
    nic_no = StringField(
        'NIC Number',
        validators=[DataRequired(), Length(max=20), validate_nic_format],
        render_kw={'placeholder': 'e.g. 991234567V or 200012345678'},
    )
    # No password fields — the trainer's initial password is their NIC number

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

    def validate_nic_no(self, field):
        if nic_taken(field.data):
            raise ValidationError('That NIC number is already registered.')


class TrainerEditForm(FlaskForm):
    # User fields
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=80)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=80)])
    phone = StringField('Phone (User Account)', validators=[Optional(), Length(max=20)])
    nic_no = StringField(
        'NIC Number',
        validators=[DataRequired(), Length(max=20), validate_nic_format],
        render_kw={'placeholder': 'e.g. 991234567V or 200012345678'},
    )

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

    def __init__(self, user_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._user_id = user_id

    def validate_nic_no(self, field):
        if nic_taken(field.data, exclude_user_id=self._user_id):
            raise ValidationError('That NIC number is already registered.')


# ------------------------------------------------------------------ #
#  Trainer: Self-edit own contact info (mobile number + NIC only)     #
# ------------------------------------------------------------------ #

class TrainerSelfEditForm(FlaskForm):
    phone = StringField(
        'Mobile Number',
        validators=[DataRequired(), Length(max=20)],
        render_kw={'placeholder': '+94 xx xxx xxxx'},
    )
    nic_no = StringField(
        'NIC Number',
        validators=[DataRequired(), Length(max=20), validate_nic_format],
        render_kw={'placeholder': 'e.g. 991234567V or 200012345678'},
    )
    submit = SubmitField('Save Changes')

    def __init__(self, user_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._user_id = user_id

    def validate_nic_no(self, field):
        if nic_taken(field.data, exclude_user_id=self._user_id):
            raise ValidationError('That NIC number is already registered.')
