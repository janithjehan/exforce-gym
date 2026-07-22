from datetime import datetime
from app.extensions import db


class Measurement(db.Model):
    """Body measurement entry for a member (SRS 3.12).

    FR-MEAS-01: Member + Date + measurement fields (all values optional —
    a record stores whichever fields were measured that day).
    FR-MEAS-03: rows are never deleted; edits are logged to MeasurementEditLog.
    """
    __tablename__ = 'measurements'

    # (attribute, label, unit) — drives forms, tables and the edit-audit diff
    VALUE_FIELDS = [
        ('weight_kg', 'Weight', 'kg'),
        ('height_cm', 'Height', 'cm'),
        ('chest_cm', 'Chest', 'cm'),
        ('waist_cm', 'Waist', 'cm'),
        ('hips_cm', 'Hips', 'cm'),
        ('arms_cm', 'Arms', 'cm'),
        ('thighs_cm', 'Thighs', 'cm'),
    ]

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    measured_on = db.Column(db.Date, nullable=False)

    weight_kg = db.Column(db.Numeric(5, 2), nullable=True)
    height_cm = db.Column(db.Numeric(5, 2), nullable=True)
    chest_cm = db.Column(db.Numeric(5, 2), nullable=True)
    waist_cm = db.Column(db.Numeric(5, 2), nullable=True)
    hips_cm = db.Column(db.Numeric(5, 2), nullable=True)
    arms_cm = db.Column(db.Numeric(5, 2), nullable=True)
    thighs_cm = db.Column(db.Numeric(5, 2), nullable=True)

    notes = db.Column(db.Text, nullable=True)

    # Audit
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    member = db.relationship(
        'Member', foreign_keys=[member_id],
        backref=db.backref(
            'measurements', lazy='dynamic',
            order_by='Measurement.measured_on.desc()',
        ),
    )
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    updated_by = db.relationship('User', foreign_keys=[updated_by_id])

    edit_logs = db.relationship(
        'MeasurementEditLog', backref='measurement', lazy='dynamic',
        order_by='MeasurementEditLog.created_at.desc()',
    )

    @property
    def recorded_values(self):
        """List of (label, value, unit) for the fields actually measured."""
        out = []
        for attr, label, unit in self.VALUE_FIELDS:
            value = getattr(self, attr)
            if value is not None:
                out.append((label, value, unit))
        return out

    @property
    def bmi(self):
        """BMI when both weight and height are recorded, else None."""
        if self.weight_kg and self.height_cm:
            h_m = float(self.height_cm) / 100
            if h_m > 0:
                return round(float(self.weight_kg) / (h_m * h_m), 1)
        return None

    @property
    def was_edited(self):
        return self.edit_logs.count() > 0

    def __repr__(self):
        return f'<Measurement {self.id} member={self.member_id} on={self.measured_on}>'


class MeasurementEditLog(db.Model):
    """FR-MEAS-03: one row per changed field on every edit — who, when, old → new."""
    __tablename__ = 'measurement_edit_logs'

    id = db.Column(db.Integer, primary_key=True)
    measurement_id = db.Column(
        db.Integer, db.ForeignKey('measurements.id'), nullable=False
    )
    edited_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    field_name = db.Column(db.String(50), nullable=False)
    old_value = db.Column(db.String(255), nullable=True)
    new_value = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    edited_by = db.relationship('User', foreign_keys=[edited_by_id])

    def __repr__(self):
        return f'<MeasurementEditLog m={self.measurement_id} {self.field_name}>'