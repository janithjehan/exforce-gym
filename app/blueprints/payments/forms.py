from datetime import date
from flask_wtf import FlaskForm
from wtforms import SelectField, DecimalField, DateField, StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Optional, Length, NumberRange

from app.models.payment import PaymentMethod


class PaymentCreateForm(FlaskForm):
    member_id = SelectField('Member', coerce=int, validators=[DataRequired()])
    membership_id = SelectField('Link to Membership (optional)', coerce=int,
                                validators=[Optional()])
    amount = DecimalField('Amount (LKR)', places=2,
                          validators=[DataRequired(), NumberRange(min=0.01, message='Amount must be greater than 0.')])
    method = SelectField('Payment Method', validators=[DataRequired()],
                         choices=[(m.value, m.label) for m in PaymentMethod])
    payment_date = DateField('Payment Date', validators=[DataRequired()], default=date.today)
    reference_no = StringField(
        'Reference No.',
        validators=[Optional(), Length(max=100)],
        render_kw={'placeholder': 'Bank ref / receipt no. (optional)'},
    )
    notes = TextAreaField(
        'Notes',
        validators=[Optional(), Length(max=500)],
        render_kw={'rows': 2, 'placeholder': 'Optional notes...'},
    )
    submit = SubmitField('Record Payment')


class PaymentEditForm(FlaskForm):
    amount = DecimalField('Amount (LKR)', places=2,
                          validators=[DataRequired(), NumberRange(min=0.01, message='Amount must be greater than 0.')])
    method = SelectField('Payment Method', validators=[DataRequired()],
                         choices=[(m.value, m.label) for m in PaymentMethod])
    payment_date = DateField('Payment Date', validators=[DataRequired()])
    reference_no = StringField('Reference No.', validators=[Optional(), Length(max=100)])
    notes = TextAreaField('Notes', validators=[Optional(), Length(max=500)],
                          render_kw={'rows': 2})
    submit = SubmitField('Save Changes')
