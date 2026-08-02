import enum
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from app.extensions import db


class InstallmentPlanStatus(enum.Enum):
    ACTIVE = 'active'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'

    @property
    def label(self):
        return self.value.capitalize()

    @property
    def badge_class(self):
        return {'active': 'primary', 'completed': 'success', 'cancelled': 'secondary'}[self.value]


class InstallmentStatus(enum.Enum):
    """PENDING: not yet submitted by the member. SUBMITTED: a bank transfer
    reference has been submitted and is awaiting staff verification (mirrors
    Payment.PENDING). PAID: verified."""
    PENDING = 'pending'
    SUBMITTED = 'submitted'
    PAID = 'paid'

    @property
    def label(self):
        return {
            'pending': 'Not Yet Paid',
            'submitted': 'Awaiting Verification',
            'paid': 'Paid',
        }[self.value]

    @property
    def badge_class(self):
        return {'pending': 'secondary', 'submitted': 'warning', 'paid': 'success'}[self.value]


class InstallmentPlan(db.Model):
    """One per Membership sold on installments — holds the split schedule.
    Membership access is granted in full as soon as installment #1 is
    verified (see Membership/Payment); this record just tracks collection
    of the remaining installments."""
    __tablename__ = 'installment_plans'

    id = db.Column(db.Integer, primary_key=True)
    membership_id = db.Column(db.Integer, db.ForeignKey('memberships.id'), nullable=False, unique=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    package_id = db.Column(db.Integer, db.ForeignKey('packages.id'), nullable=False)

    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    installment_count = db.Column(db.Integer, nullable=False)
    status = db.Column(
        db.Enum(InstallmentPlanStatus), nullable=False, default=InstallmentPlanStatus.ACTIVE
    )

    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    membership = db.relationship(
        'Membership', foreign_keys=[membership_id],
        backref=db.backref('installment_plan', uselist=False),
    )
    member = db.relationship('Member', foreign_keys=[member_id])
    package = db.relationship('Package', foreign_keys=[package_id])
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    installments = db.relationship(
        'Installment', backref='plan', lazy='dynamic',
        order_by='Installment.sequence_no.asc()',
        cascade='all, delete-orphan',
    )

    @property
    def paid_count(self):
        return self.installments.filter_by(status=InstallmentStatus.PAID).count()

    @property
    def paid_amount(self):
        return sum((i.amount for i in self.installments.filter_by(status=InstallmentStatus.PAID)), 0)

    @property
    def remaining_amount(self):
        return self.total_amount - self.paid_amount

    @property
    def next_due(self):
        """The earliest not-yet-paid installment (PENDING or SUBMITTED), if any."""
        return (
            self.installments
            .filter(Installment.status != InstallmentStatus.PAID)
            .order_by(Installment.sequence_no.asc())
            .first()
        )

    @property
    def progress_label(self):
        return f'{self.paid_count} of {self.installment_count} paid'

    def __repr__(self):
        return f'<InstallmentPlan membership={self.membership_id} {self.installment_count}x>'

    # ------------------------------------------------------------------ #
    #  Schedule building — used when a member submits the first payment    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def split_amount(total_amount, count):
        """Split total_amount into `count` 2dp amounts that sum back exactly
        to total_amount — the last installment absorbs the rounding remainder."""
        total = Decimal(total_amount)
        base = (total / count).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        amounts = [base] * (count - 1)
        amounts.append(total - base * (count - 1))
        return amounts

    @staticmethod
    def build_due_dates(start_date, end_date, count):
        """Evenly space `count` due dates across [start_date, end_date] —
        the first is due immediately (start_date)."""
        total_days = max((end_date - start_date).days, 0)
        interval = total_days // count
        return [start_date + timedelta(days=interval * i) for i in range(count)]


class Installment(db.Model):
    """A single due slot within an InstallmentPlan."""
    __tablename__ = 'installments'

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('installment_plans.id'), nullable=False)

    sequence_no = db.Column(db.Integer, nullable=False)  # 1-based
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(
        db.Enum(InstallmentStatus), nullable=False, default=InstallmentStatus.PENDING
    )
    paid_at = db.Column(db.DateTime, nullable=True)
    last_reminded_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    @property
    def is_overdue(self):
        return self.status != InstallmentStatus.PAID and self.due_date < date.today()

    @property
    def active_payment(self):
        """The most recent non-rejected Payment submitted for this slot (i.e.
        the one currently PENDING verification, or the one that got VERIFIED)."""
        from app.models.payment import Payment, PaymentStatus
        return (
            self.payments
            .filter(Payment.status != PaymentStatus.REJECTED)
            .order_by(Payment.id.desc())
            .first()
        )

    def __repr__(self):
        return f'<Installment plan={self.plan_id} #{self.sequence_no} due={self.due_date} {self.status.value}>'
