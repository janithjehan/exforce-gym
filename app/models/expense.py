import enum
from datetime import datetime
from app.extensions import db


class ExpenseCategory(enum.Enum):
    RENT = 'rent'
    UTILITIES = 'utilities'
    EQUIPMENT = 'equipment'
    SUPPLIES = 'supplies'
    MAINTENANCE = 'maintenance'
    SALARY = 'salary'
    OTHER = 'other'

    @property
    def label(self):
        return {
            'rent': 'Rent',
            'utilities': 'Utilities',
            'equipment': 'Equipment',
            'supplies': 'Supplies',
            'maintenance': 'Maintenance',
            'salary': 'Salary',
            'other': 'Other',
        }[self.value]

    @property
    def badge_class(self):
        return {
            'rent': 'primary',
            'utilities': 'info',
            'equipment': 'warning',
            'supplies': 'secondary',
            'maintenance': 'danger',
            'salary': 'success',
            'other': 'dark',
        }[self.value]


class Expense(db.Model):
    __tablename__ = 'expenses'

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.Enum(ExpenseCategory), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    expense_date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Set only when this expense was auto-generated from marking a Payroll
    # record paid — locks the record from independent edit/archive so it
    # can't drift out of sync with the payroll record it represents.
    payroll_id = db.Column(db.Integer, db.ForeignKey('payroll.id'), nullable=True, unique=True)

    is_archived = db.Column(db.Boolean, nullable=False, default=False)

    # Audit
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    payroll = db.relationship('Payroll', backref=db.backref('expense', uselist=False))
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    updated_by = db.relationship('User', foreign_keys=[updated_by_id])

    @property
    def is_payroll_generated(self):
        return self.payroll_id is not None

    @property
    def status_label(self):
        """Display status: 'Archived' or 'Recorded'."""
        return 'Archived' if self.is_archived else 'Recorded'

    @property
    def status_badge_class(self):
        """Bootstrap badge color class matching status_label."""
        return 'secondary' if self.is_archived else 'success'

    def __repr__(self):
        """Debug representation showing category and amount."""
        return f'<Expense {self.category.value} {self.amount}>'