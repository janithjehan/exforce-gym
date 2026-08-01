from flask_wtf import FlaskForm
from wtforms import TextAreaField, StringField, SubmitField
from wtforms.validators import Optional, Length, ValidationError

from app.models.configuration import AppConfiguration


class ConfigurationForm(FlaskForm):
    bank_transfer_details = TextAreaField(
        'Bank Transfer Details',
        validators=[Optional(), Length(max=2000)],
        render_kw={
            'rows': 6,
            'placeholder': 'Bank: ...\nAccount Name: ...\nAccount No: ...\nBranch: ...',
        },
    )
    installment_options = StringField(
        'Available Installment Counts',
        validators=[Optional(), Length(max=100)],
        render_kw={'placeholder': 'e.g. 2,3,4,6,12'},
    )
    submit = SubmitField('Save Configuration')

    def validate_installment_options(self, field):
        """Every comma-separated token must parse as an integer >= 2."""
        raw = (field.data or '').strip()
        if not raw:
            return
        for token in raw.split(','):
            token = token.strip()
            if not token:
                continue
            try:
                n = int(token)
            except ValueError:
                raise ValidationError(f'"{token}" is not a whole number.')
            if n < 2:
                raise ValidationError('Installment counts must be 2 or more (1 installment is just paying in full).')