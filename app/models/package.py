from datetime import datetime
from app.extensions import db


class Package(db.Model):
    __tablename__ = 'packages'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    duration_months = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Disabled packages cannot be assigned to new memberships
    is_active = db.Column(db.Boolean, nullable=False, default=True)
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

    DURATION_CHOICES = [
        (1, '1 Month'),
        (3, '3 Months'),
        (6, '6 Months'),
        (12, '12 Months (1 Year)'),
    ]

    @property
    def duration_label(self):
        """Human-readable duration, e.g. '12 Months (1 Year)' or 'N Months' for non-preset values."""
        for months, label in self.DURATION_CHOICES:
            if months == self.duration_months:
                return label
        return f'{self.duration_months} Months'

    @property
    def status_label(self):
        """Display status: 'Archived', 'Active', or 'Inactive'."""
        if self.is_archived:
            return 'Archived'
        return 'Active' if self.is_active else 'Inactive'

    @property
    def status_badge_class(self):
        """Bootstrap badge color class matching status_label."""
        if self.is_archived:
            return 'secondary'
        return 'success' if self.is_active else 'warning'

    def __repr__(self):
        """Debug representation showing name and duration."""
        return f'<Package {self.name} ({self.duration_months}mo)>'
