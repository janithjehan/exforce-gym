from datetime import datetime, date
from flask import render_template, request, flash

from app.blueprints.reports import reports_bp
from app.extensions import db
from app.models.payment import Payment
from app.models.payroll import Payroll, PayrollStatus
from app.models.expense import Expense
from app.models.user import User
from app.utils.decorators import admin_or_manager_required

NET_PAYROLL_EXPR = Payroll.gross_amount + Payroll.bonus - Payroll.deductions


def _parse_date(raw):
    """Parse a 'YYYY-MM-DD' query param into a date, or None if blank/invalid."""
    if not raw:
        return None
    try:
        return datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError:
        return None


@reports_bp.route('/profit')
@admin_or_manager_required
def profit_report():
    """Show total income (payments) minus expenses (paid payroll + logged expenses) for a date range."""
    today = date.today()
    default_start = date(today.year, today.month, 1)
    default_end = today

    start_date = _parse_date(request.args.get('start_date', ''))
    end_date = _parse_date(request.args.get('end_date', ''))

    if not start_date or not end_date or start_date > end_date:
        if request.args.get('start_date') or request.args.get('end_date'):
            flash('Invalid date range — showing this month instead.', 'warning')
        start_date, end_date = default_start, default_end

    income_total = db.session.query(
        db.func.sum(Payment.amount)
    ).filter(
        Payment.payment_date >= start_date,
        Payment.payment_date <= end_date,
    ).scalar() or 0

    income_by_method = dict(
        db.session.query(Payment.method, db.func.sum(Payment.amount))
        .filter(Payment.payment_date >= start_date, Payment.payment_date <= end_date)
        .group_by(Payment.method)
        .all()
    )

    payroll_expense_total = db.session.query(
        db.func.sum(NET_PAYROLL_EXPR)
    ).filter(
        Payroll.status == PayrollStatus.PAID,
        Payroll.payment_date >= start_date,
        Payroll.payment_date <= end_date,
    ).scalar() or 0

    expense_by_role = dict(
        db.session.query(User.role, db.func.sum(NET_PAYROLL_EXPR))
        .join(User, Payroll.user_id == User.id)
        .filter(
            Payroll.status == PayrollStatus.PAID,
            Payroll.payment_date >= start_date,
            Payroll.payment_date <= end_date,
        )
        .group_by(User.role)
        .all()
    )

    # payroll_id.is_(None) excludes expenses auto-generated from Payroll mark-paid —
    # those are already counted in payroll_expense_total above, so including them
    # here would double-count staff salaries in expense_total.
    other_expense_total = db.session.query(
        db.func.sum(Expense.amount)
    ).filter(
        Expense.is_archived == False,
        Expense.payroll_id.is_(None),
        Expense.expense_date >= start_date,
        Expense.expense_date <= end_date,
    ).scalar() or 0

    expense_by_category = dict(
        db.session.query(Expense.category, db.func.sum(Expense.amount))
        .filter(
            Expense.is_archived == False,
            Expense.payroll_id.is_(None),
            Expense.expense_date >= start_date,
            Expense.expense_date <= end_date,
        )
        .group_by(Expense.category)
        .all()
    )

    expense_total = payroll_expense_total + other_expense_total

    return render_template(
        'reports/profit.html',
        start_date=start_date,
        end_date=end_date,
        income_total=income_total,
        payroll_expense_total=payroll_expense_total,
        other_expense_total=other_expense_total,
        expense_total=expense_total,
        net_profit=income_total - expense_total,
        income_by_method=income_by_method,
        expense_by_role=expense_by_role,
        expense_by_category=expense_by_category,
        title='Profit Report',
    )