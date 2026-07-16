from flask_wtf import FlaskForm
from wtforms import SelectField, DateTimeField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Optional, Length


class AttendanceCreateForm(FlaskForm):
    member_id = SelectField('Member', coerce=int, validators=[DataRequired()])
    check_in = DateTimeField(
        'Check-In Time',
        format='%Y-%m-%dT%H:%M',
        validators=[DataRequired()],
    )
    check_out = DateTimeField(
        'Check-Out Time (optional)',
        format='%Y-%m-%dT%H:%M',
        validators=[Optional()],
    )
    notes = TextAreaField(
        'Notes',
        validators=[Optional(), Length(max=500)],
        render_kw={'rows': 2, 'placeholder': 'Optional notes...'},
    )
    submit = SubmitField('Record Attendance')
