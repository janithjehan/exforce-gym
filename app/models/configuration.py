from datetime import datetime
from app.extensions import db


class AppConfiguration(db.Model):
    """Singleton row holding gym-wide settings editable by Admin (e.g. bank
    transfer details shown to members on the Bank Transfer payment page)."""
    __tablename__ = 'app_configuration'

    id = db.Column(db.Integer, primary_key=True)
    bank_transfer_details = db.Column(db.Text, nullable=True)

    # Global menu of installment counts a Package may opt into, e.g. "2,3,4,6,12".
    # A count of 1 is meaningless (that's just paying in full) so it's never stored here.
    installment_options = db.Column(db.String(100), nullable=True)

    updated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    updated_by = db.relationship('User', foreign_keys=[updated_by_id])

    @staticmethod
    def parse_installment_options(raw):
        """Parse a comma-separated string of installment counts into a sorted,
        de-duplicated list of ints >= 2. Used for both the global Configuration
        list and a Package's chosen subset. Silently drops invalid tokens."""
        if not raw:
            return []
        counts = set()
        for token in raw.split(','):
            token = token.strip()
            if not token:
                continue
            try:
                n = int(token)
            except ValueError:
                continue
            if n >= 2:
                counts.add(n)
        return sorted(counts)

    @property
    def installment_options_list(self):
        return self.parse_installment_options(self.installment_options)

    @classmethod
    def get(cls):
        """Return the single settings row, creating it on first access."""
        settings = cls.query.first()
        if not settings:
            settings = cls()
            db.session.add(settings)
            db.session.commit()
        return settings

    def __repr__(self):
        return f'<AppConfiguration id={self.id}>'