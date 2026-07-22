from flask_wtf import FlaskForm
from wtforms import SelectField, RadioField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Optional, Length

from app.models.feedback import FeedbackCategory, FeedbackStatus


class FeedbackSubmitForm(FlaskForm):
    """FR-FDB-01: Category (optional) + Rating (1–5) + Comments."""
    category = SelectField(
        'Category',
        choices=[('', '— General —')] + [(c.value, c.label) for c in FeedbackCategory],
        validators=[Optional()],
    )
    rating = RadioField(
        'Rating',
        choices=[(str(i), str(i)) for i in range(1, 6)],
        validators=[DataRequired(message='Please select a rating.')],
    )
    comments = TextAreaField(
        'Comments',
        validators=[DataRequired(), Length(min=5, max=2000)],
        render_kw={'rows': 5, 'placeholder': 'Tell us about your experience...'},
    )
    submit = SubmitField('Submit Feedback')


class FeedbackRespondForm(FlaskForm):
    """Admin response + status update."""
    status = SelectField(
        'Status',
        choices=[(s.value, s.label) for s in FeedbackStatus],
        validators=[DataRequired()],
    )
    admin_response = TextAreaField(
        'Response',
        validators=[Optional(), Length(max=2000)],
        render_kw={'rows': 4, 'placeholder': 'Optional response to the member...'},
    )
    submit = SubmitField('Save')
