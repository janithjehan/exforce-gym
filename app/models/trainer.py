from datetime import datetime
from app.extensions import db


class Trainer(db.Model):
    __tablename__ = 'trainers'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)

    specialization = db.Column(db.String(200), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    experience_years = db.Column(db.Integer, nullable=True)
    certifications = db.Column(db.Text, nullable=True)
    contact_no = db.Column(db.String(20), nullable=False, default='')

    is_archived = db.Column(db.Boolean, nullable=False, default=False)

    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = db.relationship(
        'User', foreign_keys=[user_id],
        backref=db.backref('trainer_profile', uselist=False, lazy='joined')
    )
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    updated_by = db.relationship('User', foreign_keys=[updated_by_id])

    @property
    def full_name(self):
        return self.user.full_name

    @property
    def email(self):
        return self.user.email

    @property
    def username(self):
        return self.user.username

    @property
    def is_profile_complete(self):
        return bool(self.specialization and self.specialization.strip())

    @property
    def status_label(self):
        if self.is_archived:
            return 'Archived'
        return 'Active' if self.user.is_active else 'Inactive'

    @property
    def status_badge_class(self):
        if self.is_archived:
            return 'secondary'
        return 'success' if self.user.is_active else 'warning'

    def __repr__(self):
        return f'<Trainer {self.user.username}>'
