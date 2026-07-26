from flask_wtf import FlaskForm
from wtforms import TextAreaField, SubmitField
from wtforms.validators import Optional, Length


class ConfigurationForm(FlaskForm):
    bank_transfer_details = TextAreaField(
        'Bank Transfer Details',
        validators=[Optional(), Length(max=2000)],
        render_kw={
            'rows': 6,
            'placeholder': 'Bank: ...\nAccount Name: ...\nAccount No: ...\nBranch: ...',
        },
    )
    submit = SubmitField('Save Configuration')