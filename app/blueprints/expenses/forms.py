from flask_wtf import FlaskForm
from wtforms import SelectField, TextAreaField, SubmitField
from wtforms.fields import DecimalField, DateField
from wtforms.validators import DataRequired, NumberRange, Length
from app.models.expense import ExpenseCategory


class ExpenseForm(FlaskForm):
    category = SelectField(
        'Category',
        choices=[(c.value, c.label) for c in ExpenseCategory],
        validators=[DataRequired()],
    )
    amount = DecimalField(
        'Amount (LKR)',
        places=2,
        validators=[DataRequired(), NumberRange(min=0.01, message='Amount must be greater than zero.')],
    )
    expense_date = DateField('Date', validators=[DataRequired()])
    description = TextAreaField(
        'Description',
        validators=[Length(max=1000)],
        render_kw={'rows': 3, 'placeholder': 'What was this expense for?'},
    )
    submit = SubmitField('Save Expense')
