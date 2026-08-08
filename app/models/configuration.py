from datetime import datetime
from app.extensions import db


class AppConfiguration(db.Model):
    """Singleton row holding gym-wide settings editable by Admin (e.g. bank
    transfer details shown to members on the Bank Transfer payment page)."""
    __tablename__ = 'app_configuration'

    id = db.Column(db.Integer, primary_key=True)
    bank_transfer_details = db.Column(db.Text, nullable=True)

    updated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    updated_by = db.relationship('User', foreign_keys=[updated_by_id])

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