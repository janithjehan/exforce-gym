from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, SelectField, IntegerField, TextAreaField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, ValidationError

from app.models.equipment import Equipment, EquipmentCategory, EquipmentStatus

ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp']


class EquipmentForm(FlaskForm):
    name = StringField('Equipment Name', validators=[DataRequired(), Length(max=100)])
    category = SelectField(
        'Category',
        choices=[(c.value, c.label) for c in EquipmentCategory],
        validators=[DataRequired()],
    )
    quantity = IntegerField(
        'Quantity',
        validators=[DataRequired(), NumberRange(min=1, max=9999)],
        default=1,
    )
    status = SelectField(
        'Status',
        choices=[(s.value, s.label) for s in EquipmentStatus],
        validators=[DataRequired()],
    )
    image = FileField(
        'Image',
        validators=[FileAllowed(ALLOWED_IMAGE_EXTENSIONS, 'Images only (jpg, png, gif, webp).')],
    )
    remove_image = BooleanField('Remove current image')
    notes = TextAreaField(
        'Notes',
        validators=[Length(max=2000)],
        render_kw={'rows': 4, 'placeholder': 'Maintenance notes, supplier, purchase info...'},
    )
    submit = SubmitField('Save Equipment')

    def validate_name(self, field):
        from flask import request
        equipment_id = request.view_args.get('equipment_id')
        query = Equipment.query.filter(
            Equipment.name.ilike(field.data.strip()),
            Equipment.is_archived == False,
        )
        if equipment_id:
            query = query.filter(Equipment.id != equipment_id)
        if query.first():
            raise ValidationError('Equipment with this name already exists.')