from datetime import date
from flask_wtf import FlaskForm
from wtforms import SelectField, DateField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Optional, Length, ValidationError


class MembershipCreateForm(FlaskForm):
    member_id = SelectField('Member', coerce=int, validators=[DataRequired()])
    package_id = SelectField('Package', coerce=int, validators=[DataRequired()])
    start_date = DateField('Start Date', validators=[DataRequired()], default=date.today)
    notes = TextAreaField(
        'Notes', validators=[Optional(), Length(max=500)],
        render_kw={'rows': 2, 'placeholder': 'Optional internal notes...'},
    )
    submit = SubmitField('Assign Membership')

    def validate_start_date(self, field):
        if field.data and field.data > date.today():
            raise ValidationError('Start date cannot be in the future.')
