import enum
from datetime import datetime
from app.extensions import db


class FeedbackCategory(enum.Enum):
    SERVICE = 'service'
    TRAINERS = 'trainers'
    FACILITY = 'facility'
    EQUIPMENT = 'equipment'
    OTHER = 'other'

    @property
    def label(self):
        return {
            'service': 'Service',
            'trainers': 'Trainers',
            'facility': 'Facility',
            'equipment': 'Equipment',
            'other': 'Other',
        }[self.value]


class FeedbackStatus(enum.Enum):
    NEW = 'new'
    REVIEWED = 'reviewed'
    RESOLVED = 'resolved'

    @property
    def label(self):
        return self.value.capitalize()

    @property
    def badge_class(self):
        return {
            'new': 'primary',
            'reviewed': 'warning',
            'resolved': 'success',
        }[self.value]


class Feedback(db.Model):
    """Member feedback entry (SRS 3.13).

    FR-FDB-01: Member + Date (created_at) + Category (optional) + Rating (1–5) + Comments.
    Admin responds and moves status NEW → REVIEWED/RESOLVED.
    """
    __tablename__ = 'feedbacks'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)

    category = db.Column(db.Enum(FeedbackCategory), nullable=True)
    rating = db.Column(db.Integer, nullable=False)  # 1–5, validated in form
    comments = db.Column(db.Text, nullable=False)

    status = db.Column(
        db.Enum(FeedbackStatus), nullable=False, default=FeedbackStatus.NEW
    )

    # Admin response
    admin_response = db.Column(db.Text, nullable=True)
    responded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    responded_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    member = db.relationship(
        'Member', foreign_keys=[member_id],
        backref=db.backref(
            'feedbacks', lazy='dynamic',
            order_by='Feedback.created_at.desc()',
        ),
    )
    responded_by = db.relationship('User', foreign_keys=[responded_by_id])

    @property
    def category_label(self):
        return self.category.label if self.category else 'General'

    @property
    def has_response(self):
        return bool(self.admin_response)

    def __repr__(self):
        return f'<Feedback {self.id} member={self.member_id} rating={self.rating} {self.status.value}>'
