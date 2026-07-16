import enum
from datetime import date, datetime
from app.extensions import db


class Gender(enum.Enum):
    MALE = 'male'
    FEMALE = 'female'
    OTHER = 'other'

    @property
    def label(self):
        return self.value.replace('_', ' ').title()


class Member(db.Model):
    __tablename__ = 'members'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)

    # FR-MEM-01: Required profile fields
    contact_no = db.Column(db.String(20), nullable=False, default='')
    address = db.Column(db.Text, nullable=True)
    join_date = db.Column(db.Date, nullable=False, default=date.today)

    # Additional profile
    date_of_birth = db.Column(db.Date, nullable=True)
    gender = db.Column(db.Enum(Gender), nullable=True)

    # Emergency contact
    emergency_contact_name = db.Column(db.String(100), nullable=True)
    emergency_contact_no = db.Column(db.String(20), nullable=True)

    # Admin notes
    notes = db.Column(db.Text, nullable=True)

    # FR-MEM-03: Soft delete
    is_archived = db.Column(db.Boolean, nullable=False, default=False)

    # Audit
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # ------------------------------------------------------------------ #
    #  Relationships                                                       #
    # ------------------------------------------------------------------ #
    user = db.relationship(
        'User', foreign_keys=[user_id],
        backref=db.backref('member_profile', uselist=False, lazy='joined')
    )
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    updated_by = db.relationship('User', foreign_keys=[updated_by_id])

    # ------------------------------------------------------------------ #
    #  Computed properties                                                 #
    # ------------------------------------------------------------------ #

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
        """True when the minimum required contact_no has been filled in."""
        return bool(self.contact_no and self.contact_no.strip())

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today = date.today()
        return (
            today.year - self.date_of_birth.year
            - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        )

    # FR-MEM-02: Status is determined by active membership.
    # Will be replaced with a real query once the Membership module is built.
    @property
    def is_active_member(self):
        """True if member has a currently valid membership."""
        # Lazy import to avoid circular dependency once Membership model exists
        try:
            from app.models.membership import Membership, MembershipStatus
            today = date.today()
            return (
                Membership.query
                .filter_by(member_id=self.id, status=MembershipStatus.ACTIVE)
                .filter(Membership.end_date >= today)
                .count() > 0
            )
        except Exception:
            return False

    @property
    def status_label(self):
        if self.is_archived:
            return 'Archived'
        return 'Active' if self.is_active_member else 'Inactive'

    @property
    def status_badge_class(self):
        if self.is_archived:
            return 'secondary'
        return 'success' if self.is_active_member else 'warning'

    def __repr__(self):
        return f'<Member {self.user.username}>'
