from datetime import date
from flask_wtf import FlaskForm
from wtforms import SelectField, DecimalField, DateField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Optional, Length, NumberRange

from app.models.payroll import PayrollMethod


class PayrollCreateForm(FlaskForm):
    staff_id = SelectField('Staff Member', coerce=int, validators=[DataRequired()])
    pay_period = DateField(
        'Pay Period (any date in the month)',
        validators=[DataRequired()],
        default=date.today,
    )
    gross_amount = DecimalField(
        'Gross Amount (LKR)', places=2,
        validators=[DataRequired(), NumberRange(min=0.01, message='Amount must be greater than 0.')],
    )
    bonus = DecimalField(
        'Bonus (LKR)', places=2, default=0,
        validators=[Optional(), NumberRange(min=0, message='Bonus cannot be negative.')],
    )
    deductions = DecimalField(
        'Deductions (LKR)', places=2, default=0,
        validators=[Optional(), NumberRange(min=0, message='Deductions cannot be negative.')],
    )
    notes = TextAreaField(
        'Notes',
        validators=[Optional(), Length(max=500)],
        render_kw={'rows': 2, 'placeholder': 'Optional notes...'},
    )
    submit = SubmitField('Create Payroll Record')


class PayrollEditForm(FlaskForm):
    pay_period = DateField('Pay Period (any date in the month)', validators=[DataRequired()])
    gross_amount = DecimalField(
        'Gross Amount (LKR)', places=2,
        validators=[DataRequired(), NumberRange(min=0.01, message='Amount must be greater than 0.')],
    )
    bonus = DecimalField(
        'Bonus (LKR)', places=2,
        validators=[Optional(), NumberRange(min=0, message='Bonus cannot be negative.')],
    )
    deductions = DecimalField(
        'Deductions (LKR)', places=2,
        validators=[Optional(), NumberRange(min=0, message='Deductions cannot be negative.')],
    )
    notes = TextAreaField('Notes', validators=[Optional(), Length(max=500)],
                          render_kw={'rows': 2})
    submit = SubmitField('Save Changes')


class BulkPayrollForm(FlaskForm):
    """Header-only form — CSRF + shared pay period. The per-staff checkbox
    and amount rows are dynamic (rendered from the staff list) and parsed
    directly from request.form, same pattern as Schedule's item rows."""
    pay_period = DateField(
        'Pay Period (any date in the month)',
        validators=[DataRequired()],
        default=date.today,
    )
    submit = SubmitField('Create Selected Payroll Records')


class PayrollMarkPaidForm(FlaskForm):
    method = SelectField(
        'Payment Method', validators=[DataRequired()],
        choices=[(m.value, m.label) for m in PayrollMethod],
    )
    payment_date = DateField('Payment Date', validators=[DataRequired()], default=date.today)
    submit = SubmitField('Mark as Paid')
