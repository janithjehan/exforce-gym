import enum
from datetime import datetime
from app.extensions import db


class PaymentMethod(enum.Enum):
    CASH = 'cash'
    CARD = 'card'
    BANK_TRANSFER = 'bank_transfer'
    ONLINE = 'online'

    @property
    def label(self):
        return {
            'cash': 'Cash',
            'card': 'Card',
            'bank_transfer': 'Bank Transfer',
            'online': 'Online',
        }[self.value]

    @property
    def badge_class(self):
        return {
            'cash': 'success',
            'card': 'primary',
            'bank_transfer': 'info',
            'online': 'warning',
        }[self.value]

    @property
    def icon(self):
        return {
            'cash': 'fa-money-bill-wave',
            'card': 'fa-credit-card',
            'bank_transfer': 'fa-building-columns',
            'online': 'fa-globe',
        }[self.value]


class PaymentStatus(enum.Enum):
    """Verification state. Only member-submitted bank transfers start PENDING —
    every other payment (cash/card entered by staff, PayHere) is final the
    moment it's created, so they default straight to VERIFIED."""
    PENDING = 'pending'
    VERIFIED = 'verified'
    REJECTED = 'rejected'

    @property
    def label(self):
        return self.value.capitalize()

    @property
    def badge_class(self):
        return {
            'pending': 'warning',
            'verified': 'success',
            'rejected': 'danger',
        }[self.value]


class Payment(db.Model):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    # FR-PAY-01: linked to member (required) and membership (optional)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    membership_id = db.Column(db.Integer, db.ForeignKey('memberships.id'), nullable=True)

    amount = db.Column(db.Numeric(10, 2), nullable=False)
    method = db.Column(db.Enum(PaymentMethod), nullable=False)  # FR-PAY-02
    payment_date = db.Column(db.Date, nullable=False)
    reference_no = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # Member-submitted bank transfers start PENDING until an Admin/Manager
    # verifies the reference number against the bank statement.
    status = db.Column(
        db.Enum(PaymentStatus), nullable=False, default=PaymentStatus.VERIFIED
    )
    verified_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)  # set when status == REJECTED

    # Audit
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    member = db.relationship(
        'Member', foreign_keys=[member_id],
        backref=db.backref('payments', lazy='dynamic',
                           order_by='Payment.payment_date.desc()')
    )
    membership = db.relationship(
        'Membership', foreign_keys=[membership_id],
        backref=db.backref('payments', lazy='dynamic')
    )
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    updated_by = db.relationship('User', foreign_keys=[updated_by_id])
    verified_by = db.relationship('User', foreign_keys=[verified_by_id])
    edit_logs = db.relationship(
        'PaymentEditLog', backref='payment', lazy='dynamic',
        order_by='PaymentEditLog.created_at.desc()'
    )

    @property
    def is_pending_verification(self):
        return self.status == PaymentStatus.PENDING

    def __repr__(self):
        return f'<Payment id={self.id} member={self.member_id} amount={self.amount}>'


class PaymentEditLog(db.Model):
    """FR-PAY-03: audit trail — who changed what and when."""
    __tablename__ = 'payment_edit_logs'

    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=False)
    edited_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    field_name = db.Column(db.String(50), nullable=False)
    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    edited_by = db.relationship('User', foreign_keys=[edited_by_id])
