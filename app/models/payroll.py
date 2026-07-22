import enum
from datetime import datetime
from app.extensions import db


class PayrollStatus(enum.Enum):
    PENDING = 'pending'
    PAID = 'paid'
    CANCELLED = 'cancelled'

    @property
    def label(self):
        return self.value.capitalize()

    @property
    def badge_class(self):
        return {'pending': 'warning', 'paid': 'success', 'cancelled': 'secondary'}[self.value]


class PayrollMethod(enum.Enum):
    CASH = 'cash'
    BANK_TRANSFER = 'bank_transfer'
    CHEQUE = 'cheque'

    @property
    def label(self):
        return {'cash': 'Cash', 'bank_transfer': 'Bank Transfer', 'cheque': 'Cheque'}[self.value]

    @property
    def badge_class(self):
        return {'cash': 'success', 'bank_transfer': 'info', 'cheque': 'primary'}[self.value]


class Payroll(db.Model):
    __tablename__ = 'payroll'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # First-of-month date represents the pay period, e.g. 2026-07-01 = July 2026
    pay_period = db.Column(db.Date, nullable=False)

    gross_amount = db.Column(db.Numeric(10, 2), nullable=False)
    bonus = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    deductions = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    status = db.Column(db.Enum(PayrollStatus), nullable=False, default=PayrollStatus.PENDING)
    method = db.Column(db.Enum(PayrollMethod), nullable=True)  # set when marked paid
    payment_date = db.Column(db.Date, nullable=True)  # set when marked paid

    notes = db.Column(db.Text, nullable=True)

    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = db.relationship(
        'User', foreign_keys=[user_id],
        backref=db.backref('payroll_records', lazy='dynamic',
                           order_by='Payroll.pay_period.desc()')
    )
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    updated_by = db.relationship('User', foreign_keys=[updated_by_id])
    edit_logs = db.relationship(
        'PayrollEditLog', backref='payroll', lazy='dynamic',
        order_by='PayrollEditLog.created_at.desc()'
    )

    @property
    def net_amount(self):
        return self.gross_amount + self.bonus - self.deductions

    @property
    def period_label(self):
        return self.pay_period.strftime('%B %Y')

    def __repr__(self):
        return f'<Payroll id={self.id} user={self.user_id} period={self.pay_period}>'


class PayrollEditLog(db.Model):
    """Audit trail — who changed what and when (same pattern as PaymentEditLog)."""
    __tablename__ = 'payroll_edit_logs'

    id = db.Column(db.Integer, primary_key=True)
    payroll_id = db.Column(db.Integer, db.ForeignKey('payroll.id'), nullable=False)
    edited_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    field_name = db.Column(db.String(50), nullable=False)
    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    edited_by = db.relationship('User', foreign_keys=[edited_by_id])
