from flask_wtf import FlaskForm
from wtforms import (
    SelectField, DateField, DecimalField, TextAreaField, SubmitField,
)
from wtforms.validators import DataRequired, Optional, Length, NumberRange


def _value_field(label, unit):
    return DecimalField(
        f'{label} ({unit})',
        places=2,
        validators=[Optional(), NumberRange(min=0, max=999, message='Enter a valid value.')],
        render_kw={'step': '0.1', 'min': '0', 'placeholder': '—'},
    )


class MeasurementForm(FlaskForm):
    """Create/edit form — FR-MEAS-01: date + configurable value fields.

    All value fields are optional individually; routes enforce that at
    least one value is present.
    """
    member_id = SelectField('Member', coerce=int, validators=[DataRequired()])
    measured_on = DateField('Measurement Date', validators=[DataRequired()])

    weight_kg = _value_field('Weight', 'kg')
    height_cm = _value_field('Height', 'cm')
    chest_cm = _value_field('Chest', 'cm')
    waist_cm = _value_field('Waist', 'cm')
    hips_cm = _value_field('Hips', 'cm')
    arms_cm = _value_field('Arms', 'cm')
    thighs_cm = _value_field('Thighs', 'cm')

    notes = TextAreaField(
        'Notes',
        validators=[Optional(), Length(max=500)],
        render_kw={'rows': 2, 'placeholder': 'Optional notes (e.g. measured after workout)...'},
    )
    submit = SubmitField('Save Measurement')

    def has_any_value(self):
        return any(
            getattr(self, attr).data is not None
            for attr in (
                'weight_kg', 'height_cm', 'chest_cm', 'waist_cm',
                'hips_cm', 'arms_cm', 'thighs_cm',
            )
        )