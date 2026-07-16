from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, Optional


class NotificationCreateForm(FlaskForm):
    title = StringField(
        'Title',
        validators=[DataRequired(), Length(max=150)],
        render_kw={'placeholder': 'e.g. Gym closed for Poya day holiday'},
    )
    message = TextAreaField(
        'Message',
        validators=[DataRequired(), Length(max=1000)],
        render_kw={'rows': 4, 'placeholder': 'Write the announcement...'},
    )
    audience = SelectField(
        'Audience',
        choices=[
            ('all_active', 'All Active Members'),
            ('package', 'Members on a Specific Package'),
            ('expiring_soon', 'Memberships Expiring Within 30 Days'),
        ],
        validators=[DataRequired()],
    )
    package_id = SelectField('Package', coerce=int, validators=[Optional()])
    submit = SubmitField('Send Notification')