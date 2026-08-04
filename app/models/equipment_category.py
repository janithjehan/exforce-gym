from datetime import datetime
from app.extensions import db


class EquipmentCategory(db.Model):
    """Named category offered in Equipment's Category field, managed under
    Configuration > Equipment Categories. Deactivating a category drops it from
    the picker for new/edited equipment but leaves it attached to any Equipment
    already using it — same is_active convention as Package."""
    __tablename__ = 'equipment_categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    created_by = db.relationship('User', foreign_keys=[created_by_id])
    updated_by = db.relationship('User', foreign_keys=[updated_by_id])

    @property
    def status_label(self):
        return 'Active' if self.is_active else 'Inactive'

    @property
    def status_badge_class(self):
        return 'success' if self.is_active else 'warning'

    def __repr__(self):
        return f'<EquipmentCategory {self.name} ({"active" if self.is_active else "inactive"})>'
