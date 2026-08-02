import enum
from datetime import datetime
from flask import url_for
from app.extensions import db


class EquipmentCategory(enum.Enum):
    CARDIO = 'cardio'
    STRENGTH_MACHINE = 'strength_machine'
    FREE_WEIGHTS = 'free_weights'
    FUNCTIONAL = 'functional'
    ACCESSORIES = 'accessories'
    OTHER = 'other'

    @property
    def label(self):
        return {
            'cardio': 'Cardio',
            'strength_machine': 'Strength Machine',
            'free_weights': 'Free Weights',
            'functional': 'Functional Training',
            'accessories': 'Accessories',
            'other': 'Other',
        }[self.value]


class EquipmentStatus(enum.Enum):
    AVAILABLE = 'available'
    OUT_OF_SERVICE = 'out_of_service'

    @property
    def label(self):
        return {
            'available': 'Available',
            'out_of_service': 'Out of Service',
        }[self.value]

    @property
    def badge_class(self):
        return {
            'available': 'success',
            'out_of_service': 'danger',
        }[self.value]


class Equipment(db.Model):
    """Gym equipment inventory item (SRS 3.10)."""
    __tablename__ = 'equipments'

    id = db.Column(db.Integer, primary_key=True)

    # FR-EQP-01: Name, Category, Image, Quantity, Status, Notes
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.Enum(EquipmentCategory), nullable=False)
    # Image stored as binary data in the DB (survives redeploys on hosts with
    # no persistent filesystem, unlike app/static/uploads/)
    image_data = db.Column(db.LargeBinary, nullable=True)
    image_mimetype = db.Column(db.String(50), nullable=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(
        db.Enum(EquipmentStatus), nullable=False,
        default=EquipmentStatus.AVAILABLE,
    )
    notes = db.Column(db.Text, nullable=True)

    is_archived = db.Column(db.Boolean, nullable=False, default=False)

    # Audit
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    created_by = db.relationship('User', foreign_keys=[created_by_id])
    updated_by = db.relationship('User', foreign_keys=[updated_by_id])

    @property
    def image_url(self):
        """URL that streams the equipment image from the DB; None if unset."""
        if not self.image_data:
            return None
        return url_for('equipment.equipment_image', equipment_id=self.id)

    @property
    def is_available(self):
        return self.status == EquipmentStatus.AVAILABLE and not self.is_archived

    @property
    def status_label(self):
        if self.is_archived:
            return 'Archived'
        return self.status.label

    @property
    def status_badge_class(self):
        if self.is_archived:
            return 'secondary'
        return self.status.badge_class

    def __repr__(self):
        return f'<Equipment {self.name} x{self.quantity} ({self.status.value})>'