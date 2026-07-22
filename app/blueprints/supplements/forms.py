from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DecimalField, IntegerField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, Optional, ValidationError

from app.models.supplement import Supplement, SupplementType, SupplementStatus


class SupplementForm(FlaskForm):
    name = StringField('Supplement Name', validators=[DataRequired(), Length(max=100)])
    supplement_type = SelectField(
        'Type',
        choices=[(t.value, t.label) for t in SupplementType],
        validators=[DataRequired()],
    )
    brand = StringField(
        'Brand',
        validators=[Optional(), Length(max=100)],
        render_kw={'placeholder': 'e.g. Optimum Nutrition'},
    )
    price = DecimalField(
        'Price (Rs.)',
        places=2,
        validators=[Optional(), NumberRange(min=0)],
        render_kw={'placeholder': 'Optional'},
    )
    stock_qty = IntegerField(
        'Stock Quantity',
        validators=[Optional(), NumberRange(min=0, max=99999)],
        render_kw={'placeholder': 'Leave empty if not tracked'},
    )
    status = SelectField(
        'Status',
        choices=[(s.value, s.label) for s in SupplementStatus],
        validators=[DataRequired()],
    )
    description = TextAreaField(
        'Description',
        validators=[Length(max=2000)],
        render_kw={'rows': 4, 'placeholder': 'Serving info, flavours, usage notes...'},
    )
    submit = SubmitField('Save Supplement')

    def validate_name(self, field):
        from flask import request
        supplement_id = request.view_args.get('supplement_id')
        query = Supplement.query.filter(
            Supplement.name.ilike(field.data.strip()),
            Supplement.is_archived == False,
        )
        if supplement_id:
            query = query.filter(Supplement.id != supplement_id)
        if query.first():
            raise ValidationError('A supplement with this name already exists.')


class StockUpdateForm(FlaskForm):
    stock_qty = IntegerField(
        'Stock Quantity',
        validators=[InputRequired(message='Enter the new stock quantity.'), NumberRange(min=0, max=99999)],
    )
    submit = SubmitField('Update Stock')