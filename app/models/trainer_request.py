import enum
from datetime import datetime
from app.extensions import db


class TrainerRequestStatus(enum.Enum):
    PENDING = 'pending'      # awaiting the trainer's (or admin's) response
    ACCEPTED = 'accepted'    # trainer assigned — member appears under "My Members"
    REJECTED = 'rejected'    # declined by the trainer or an admin
    CANCELLED = 'cancelled'  # withdrawn by the member before a response
    ENDED = 'ended'          # a previously accepted assignment was ended (member left / staff removed)

    @property
    def label(self):
        return {
            'pending': 'Pending',
            'accepted': 'Accepted',
            'rejected': 'Rejected',
            'cancelled': 'Cancelled',
            'ended': 'Ended',
        }[self.value]

    @property
    def badge_class(self):
        return {
            'pending': 'warning',
            'accepted': 'success',
            'rejected': 'danger',
            'cancelled': 'secondary',
            'ended': 'secondary',
        }[self.value]


# States that count as an "open" request. A member with a request in one of
# these states cannot submit another (only one request at a time — a Pending
# OR an Accepted request blocks a new one).
OPEN_STATUSES = (TrainerRequestStatus.PENDING, TrainerRequestStatus.ACCEPTED)


class TrainerRequest(db.Model):
    """A member's request to be trained by a specific trainer. Created by the
    member; accepted/rejected by that trainer or an Admin. An accepted request
    is the member↔trainer assignment that drives the trainer's "My Members"."""
    __tablename__ = 'trainer_requests'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    trainer_id = db.Column(db.Integer, db.ForeignKey('trainers.id'), nullable=False)

    status = db.Column(
        db.Enum(TrainerRequestStatus), nullable=False,
        default=TrainerRequestStatus.PENDING,
    )
    message = db.Column(db.Text, nullable=True)        # member's optional note to the trainer
    response_note = db.Column(db.Text, nullable=True)  # trainer/admin note (esp. a reject reason)

    requested_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime, nullable=True)
    responded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)
    ended_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    member = db.relationship(
        'Member', foreign_keys=[member_id],
        backref=db.backref('trainer_requests', lazy='dynamic',
                           order_by='TrainerRequest.requested_at.desc()')
    )
    trainer = db.relationship(
        'Trainer', foreign_keys=[trainer_id],
        backref=db.backref('trainer_requests', lazy='dynamic',
                           order_by='TrainerRequest.requested_at.desc()')
    )
    responded_by = db.relationship('User', foreign_keys=[responded_by_id])
    ended_by = db.relationship('User', foreign_keys=[ended_by_id])

    # ------------------------------------------------------------------ #
    #  Instance helpers                                                    #
    # ------------------------------------------------------------------ #
    @property
    def is_pending(self):
        return self.status == TrainerRequestStatus.PENDING

    @property
    def is_accepted(self):
        return self.status == TrainerRequestStatus.ACCEPTED

    @property
    def status_label(self):
        return self.status.label

    @property
    def status_badge_class(self):
        return self.status.badge_class

    # ------------------------------------------------------------------ #
    #  Class helpers                                                       #
    # ------------------------------------------------------------------ #
    @classmethod
    def open_for_member(cls, member_id):
        """Return the member's current open (pending or accepted) request, if any."""
        return (
            cls.query
            .filter(cls.member_id == member_id, cls.status.in_(OPEN_STATUSES))
            .order_by(cls.requested_at.desc())
            .first()
        )

    def __repr__(self):
        return f'<TrainerRequest m={self.member_id} t={self.trainer_id} {self.status.value}>'
