from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField, TextAreaField, IntegerField, BooleanField, DateField, SelectField, SubmitField
)
from wtforms.validators import (
    DataRequired, Email, Length, Optional,
    NumberRange, ValidationError,
)
from app.models.user import User
from app.models.member import Gender
from app.models.trainer_category import TrainerCategory
from app.utils.uploads import ALLOWED_IMAGE_EXTENSIONS
from app.utils.validators import validate_nic_format, nic_taken

def _coerce_category(value):
    if value in (None, ''):
        return 0
    return int(value)

class TrainerCreateForm(FlaskForm):
    # User account section
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=80)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=80)])
    username = StringField(
        'Username',
        validators=[
            DataRequired(), Length(min=3, max=80),
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
    category = SelectField(
        'Specialization',
        choices=[],
        coerce=_coerce_category,
        validators=[DataRequired()],
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
    date_of_birth = DateField('Date of Birth', validators=[Optional()])
    gender = SelectField(
        'Gender',
        choices=[('', '— Auto from NIC —')] + [(g.value, g.label) for g in Gender],
        validators=[Optional()],
    )
    photo = FileField(
        'Profile Photo',
        validators=[FileAllowed(ALLOWED_IMAGE_EXTENSIONS, 'Images only (jpg, png, gif, webp).')],
    )

    submit = SubmitField('Create Trainer')

    def __init__(self, *args, current_category=None, **kwargs):
        super().__init__(*args, **kwargs)
        categories = TrainerCategory.query.filter_by(is_active=True).order_by(TrainerCategory.name).all()
        if current_category and not current_category.is_active:
            categories = categories + [current_category]
        self.category.choices = [('', 'Select a category...')] + [(c.id, c.name) for c in categories]

    def validate_username(self, field):
        username = field.data
        for char in username:
            if not (char.isalnum() or char in '.-_'):
                raise ValidationError('Letters, numbers, dots, hyphens, underscores only.')

        if User.query.filter_by(username=username).first():
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
    category = SelectField(
        'Specialization',
        choices=[],
        coerce=_coerce_category,
        validators=[DataRequired()],
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
    date_of_birth = DateField('Date of Birth', validators=[Optional()])
    gender = SelectField(
        'Gender',
        choices=[('', '— Select —')] + [(g.value, g.label) for g in Gender],
        validators=[Optional()],
    )
    photo = FileField(
        'Profile Photo',
        validators=[FileAllowed(ALLOWED_IMAGE_EXTENSIONS, 'Images only (jpg, png, gif, webp).')],
    )
    remove_photo = BooleanField('Remove current photo')

    submit = SubmitField('Save Changes')

    def __init__(self, user_id=None, *args, current_category=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._user_id = user_id
        categories = TrainerCategory.query.filter_by(is_active=True).order_by(TrainerCategory.name).all()
        if current_category and not current_category.is_active:
            categories = categories + [current_category]
        self.category.choices = [('', 'Select a category...')] + [(c.id, c.name) for c in categories]

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
    photo = FileField(
        'Profile Photo',
        validators=[FileAllowed(ALLOWED_IMAGE_EXTENSIONS, 'Images only (jpg, png, gif, webp).')],
    )
    remove_photo = BooleanField('Remove current photo')
    submit = SubmitField('Save Changes')

    def __init__(self, user_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._user_id = user_id

    def validate_nic_no(self, field):
        if nic_taken(field.data, exclude_user_id=self._user_id):
            raise ValidationError('That NIC number is already registered.')
