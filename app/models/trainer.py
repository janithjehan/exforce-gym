from datetime import date, datetime
from app.extensions import db
from app.models.member import Gender


class Trainer(db.Model):
    __tablename__ = 'trainers'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)

    category_id = db.Column(db.Integer, db.ForeignKey('trainer_categories.id'), nullable=True)
    category = db.relationship('TrainerCategory', backref=db.backref('specialization_items', lazy='dynamic'))
    bio = db.Column(db.Text, nullable=True)
    experience_years = db.Column(db.Integer, nullable=True)
    certifications = db.Column(db.Text, nullable=True)
    contact_no = db.Column(db.String(20), nullable=False, default='')

    date_of_birth = db.Column(db.Date, nullable=True)
    gender = db.Column(db.Enum(Gender), nullable=True)

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
        return self.category_id is not None

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today = date.today()
        return (
            today.year - self.date_of_birth.year
            - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        )

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
