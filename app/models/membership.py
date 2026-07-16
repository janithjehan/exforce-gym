import enum
from calendar import monthrange
from datetime import datetime, date, timedelta
from app.extensions import db


def _add_months(dt, months):
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


class MembershipStatus(enum.Enum):
    ACTIVE = 'active'
    EXPIRED = 'expired'
    CANCELLED = 'cancelled'

    @property
    def label(self):
        return self.value.capitalize()


class Membership(db.Model):
    __tablename__ = 'memberships'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    package_id = db.Column(db.Integer, db.ForeignKey('packages.id'), nullable=False)

    # FR-MSHIP-01: end_date calculated from start_date + package.duration_months
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)

    status = db.Column(
        db.Enum(MembershipStatus), nullable=False, default=MembershipStatus.ACTIVE
    )
    notes = db.Column(db.Text, nullable=True)

    # Audit
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    member = db.relationship(
        'Member', foreign_keys=[member_id],
        backref=db.backref('memberships', lazy='dynamic',
                           order_by='Membership.start_date.desc()')
    )
    package = db.relationship('Package', foreign_keys=[package_id])
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    updated_by = db.relationship('User', foreign_keys=[updated_by_id])

    # ------------------------------------------------------------------ #
    #  Class helpers                                                       #
    # ------------------------------------------------------------------ #

    @staticmethod
    def calculate_end_date(start_date, duration_months):
        """FR-MSHIP-01: inclusive end date = start + N months - 1 day."""
        return _add_months(start_date, duration_months) - timedelta(days=1)

    @classmethod
    def expire_passed(cls):
        """Mark ACTIVE memberships whose end_date has passed as EXPIRED."""
        today = date.today()
        cls.query.filter(
            cls.status == MembershipStatus.ACTIVE,
            cls.end_date < today,
        ).update(
            {'status': MembershipStatus.EXPIRED, 'updated_at': datetime.utcnow()},
            synchronize_session=False,
        )
        db.session.commit()

    # ------------------------------------------------------------------ #
    #  Instance helpers                                                    #
    # ------------------------------------------------------------------ #

    @property
    def is_currently_active(self):
        return self.status == MembershipStatus.ACTIVE and self.end_date >= date.today()

    @property
    def days_remaining(self):
        if not self.is_currently_active:
            return 0
        return (self.end_date - date.today()).days

    @property
    def status_label(self):
        if self.status == MembershipStatus.ACTIVE and self.end_date < date.today():
            return 'Expired'
        return self.status.label

    @property
    def status_badge_class(self):
        if self.is_currently_active:
            return 'success'
        if self.status == MembershipStatus.CANCELLED:
            return 'secondary'
        return 'danger'

    def __repr__(self):
        return f'<Membership member={self.member_id} pkg={self.package_id} {self.start_date}→{self.end_date}>'
