import enum
from datetime import datetime
from app.extensions import db


class SupplementType(enum.Enum):
    CREATINE = 'creatine'
    PROTEIN = 'protein'
    OTHER = 'other'

    @property
    def label(self):
        return {
            'creatine': 'Creatine',
            'protein': 'Protein',
            'other': 'Other',
        }[self.value]


class SupplementStatus(enum.Enum):
    AVAILABLE = 'available'
    OUT_OF_STOCK = 'out_of_stock'
    DISCONTINUED = 'discontinued'

    @property
    def label(self):
        return {
            'available': 'Available',
            'out_of_stock': 'Out of Stock',
            'discontinued': 'Discontinued',
        }[self.value]

    @property
    def badge_class(self):
        return {
            'available': 'success',
            'out_of_stock': 'warning',
            'discontinued': 'secondary',
        }[self.value]


class Supplement(db.Model):
    """Supplement catalog entry (SRS 3.11)."""
    __tablename__ = 'supplements'

    id = db.Column(db.Integer, primary_key=True)

    # FR-SUP-01: Name, Type, Brand, Price (optional), Stock Qty (optional), Status
    name = db.Column(db.String(100), nullable=False)
    supplement_type = db.Column(db.Enum(SupplementType), nullable=False)
    brand = db.Column(db.String(100), nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=True)
    stock_qty = db.Column(db.Integer, nullable=True)  # None = stock not tracked
    status = db.Column(
        db.Enum(SupplementStatus), nullable=False,
        default=SupplementStatus.AVAILABLE,
    )
    description = db.Column(db.Text, nullable=True)

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
    def price_label(self):
        if self.price is None:
            return '—'
        return f'Rs. {self.price:,.2f}'

    @property
    def stock_label(self):
        if self.stock_qty is None:
            return 'Not tracked'
        return str(self.stock_qty)

    @property
    def is_stock_tracked(self):
        return self.stock_qty is not None

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
        return f'<Supplement {self.name} ({self.supplement_type.value}/{self.status.value})>'