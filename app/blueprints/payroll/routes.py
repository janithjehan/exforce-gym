from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from calendar import monthrange
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import current_user, login_required

from app.blueprints.payroll import payroll_bp
from app.blueprints.payroll.forms import (
    PayrollCreateForm, PayrollEditForm, PayrollMarkPaidForm, BulkPayrollForm,
)
from app.extensions import db
from app.models.user import User, UserRole
from app.models.payroll import Payroll, PayrollStatus, PayrollMethod, PayrollEditLog
from app.utils.decorators import admin_or_manager_required

PAYROLL_PER_PAGE = 15
STAFF_ROLES = (UserRole.ADMIN, UserRole.MANAGER, UserRole.TRAINER)


def _first_of_month(d):
    return date(d.year, d.month, 1)


def _staff_choices():
    staff = (
        User.query
        .filter(User.role.in_(STAFF_ROLES), User.is_archived == False, User.is_active == True)
        .order_by(User.first_name.asc())
        .all()
    )
    return [(u.id, f'{u.full_name} ({u.role.label})') for u in staff]


def _selectable_staff_for_bulk():
    """Active Admin/Manager/Trainer users, excluding the current user — the
    bulk screen never lists yourself, so there's no self-guard to enforce
    per row (structurally impossible instead of checked at submit time)."""
    return (
        User.query
        .filter(
            User.role.in_(STAFF_ROLES),
            User.is_archived == False,
            User.is_active == True,
            User.id != current_user.id,
        )
        .order_by(User.role.asc(), User.first_name.asc())
        .all()
    )


def _parse_amount(raw):
    """Parse a posted amount string into a Decimal, or None if blank/invalid."""
    raw = (raw or '').strip()
    if not raw:
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    if value < 0:
        return None
    return value


@payroll_bp.route('/')
@admin_or_manager_required
def list_payroll():
    page = request.args.get('page', 1, type=int)
    staff_filter = request.args.get('staff', type=int)
    status_filter = request.args.get('status', 'all')
    month_filter = request.args.get('month', '')  # YYYY-MM

    query = Payroll.query.join(User, Payroll.user_id == User.id)

    if staff_filter:
        query = query.filter(Payroll.user_id == staff_filter)

    if status_filter in [s.value for s in PayrollStatus]:
        query = query.filter(Payroll.status == PayrollStatus(status_filter))

    if month_filter:
        try:
            year, month = map(int, month_filter.split('-'))
            last_day = monthrange(year, month)[1]
            query = query.filter(
                Payroll.pay_period >= date(year, month, 1),
                Payroll.pay_period <= date(year, month, last_day),
            )
        except (ValueError, AttributeError):
            pass

    records = query.order_by(Payroll.pay_period.desc(), Payroll.id.desc()).paginate(
        page=page, per_page=PAYROLL_PER_PAGE, error_out=False
    )

    today = date.today()
    month_start = date(today.year, today.month, 1)
    stats = {
        'pending': Payroll.query.filter_by(status=PayrollStatus.PENDING).count(),
        'paid_this_month': db.session.query(
            db.func.sum(Payroll.gross_amount + Payroll.bonus - Payroll.deductions)
        ).filter(
            Payroll.status == PayrollStatus.PAID,
            Payroll.payment_date >= month_start,
        ).scalar() or 0,
        'staff_count': len(_staff_choices()),
    }

    return render_template(
        'payroll/list.html',
        records=records,
        staff_filter=staff_filter,
        status_filter=status_filter,
        month_filter=month_filter,
        staff_choices=_staff_choices(),
        statuses=PayrollStatus,
        stats=stats,
        title='Payroll',
    )


@payroll_bp.route('/create', methods=['GET', 'POST'])
@admin_or_manager_required
def create_payroll():
    form = PayrollCreateForm()
    form.staff_id.choices = _staff_choices()

    preselect_staff_id = request.args.get('staff_id', type=int)
    if request.method == 'GET' and preselect_staff_id:
        form.staff_id.data = preselect_staff_id

    if form.validate_on_submit():
        if form.staff_id.data == current_user.id:
            flash('You cannot create a payroll record for yourself.', 'danger')
            return render_template('payroll/create.html', form=form, title='Create Payroll Record')

        staff = User.query.get_or_404(form.staff_id.data)
        period = _first_of_month(form.pay_period.data)

        existing = Payroll.query.filter(
            Payroll.user_id == staff.id,
            Payroll.pay_period == period,
            Payroll.status != PayrollStatus.CANCELLED,
        ).first()
        if existing:
            flash(
                f'{staff.full_name} already has a payroll record for {period.strftime("%B %Y")}.',
                'danger',
            )
            return render_template('payroll/create.html', form=form, title='Create Payroll Record')

        record = Payroll(
            user_id=staff.id,
            pay_period=period,
            gross_amount=form.gross_amount.data,
            bonus=form.bonus.data or 0,
            deductions=form.deductions.data or 0,
            notes=(form.notes.data or '').strip() or None,
            created_by_id=current_user.id,
        )
        db.session.add(record)
        db.session.commit()

        flash(f'Payroll record created for {staff.full_name} — {period.strftime("%B %Y")}.', 'success')
        return redirect(url_for('payroll.view_payroll', payroll_id=record.id))

    return render_template('payroll/create.html', form=form, title='Create Payroll Record')


@payroll_bp.route('/bulk-create', methods=['GET', 'POST'])
@admin_or_manager_required
def bulk_create_payroll():
    """Select any number of Managers/Trainers and create one payroll record
    each for the same pay period, with per-person amounts, in one submit."""
    form = BulkPayrollForm()
    staff_list = _selectable_staff_for_bulk()

    if form.validate_on_submit():
        period = _first_of_month(form.pay_period.data)
        created, skipped = [], []

        for staff in staff_list:
            if not request.form.get(f'selected_{staff.id}'):
                continue  # checkbox not ticked — ignore this row entirely

            gross = _parse_amount(request.form.get(f'gross_{staff.id}'))
            bonus = _parse_amount(request.form.get(f'bonus_{staff.id}')) or Decimal('0')
            deductions = _parse_amount(request.form.get(f'deductions_{staff.id}')) or Decimal('0')

            if gross is None or gross <= 0:
                skipped.append(f'{staff.full_name} (missing/invalid gross amount)')
                continue

            existing = Payroll.query.filter(
                Payroll.user_id == staff.id,
                Payroll.pay_period == period,
                Payroll.status != PayrollStatus.CANCELLED,
            ).first()
            if existing:
                skipped.append(f'{staff.full_name} (already has a record for {period.strftime("%B %Y")})')
                continue

            created.append(Payroll(
                user_id=staff.id,
                pay_period=period,
                gross_amount=gross,
                bonus=bonus,
                deductions=deductions,
                created_by_id=current_user.id,
            ))

        if not created and not skipped:
            flash('No staff selected. Check at least one row before submitting.', 'warning')
            return render_template('payroll/bulk_create.html', form=form, staff_list=staff_list, title='Bulk Create Payroll')

        for record in created:
            db.session.add(record)
        db.session.commit()

        if created:
            flash(f'Created {len(created)} payroll record(s) for {period.strftime("%B %Y")}.', 'success')
        if skipped:
            flash('Skipped: ' + '; '.join(skipped), 'warning')

        return redirect(url_for('payroll.list_payroll'))

    return render_template('payroll/bulk_create.html', form=form, staff_list=staff_list, title='Bulk Create Payroll')


@payroll_bp.route('/<int:payroll_id>')
@login_required
def view_payroll(payroll_id):
    record = Payroll.query.get_or_404(payroll_id)

    is_staff_self = record.user_id == current_user.id
    is_manager_or_admin = current_user.role in (UserRole.ADMIN, UserRole.MANAGER)
    if not is_manager_or_admin and not is_staff_self:
        abort(403)

    edit_logs = record.edit_logs.all()
    return render_template(
        'payroll/view.html',
        record=record,
        edit_logs=edit_logs,
        has_list_access=is_manager_or_admin,
        can_manage=is_manager_or_admin and not is_staff_self,
        title=f'Payroll #{record.id}',
    )


@payroll_bp.route('/<int:payroll_id>/edit', methods=['GET', 'POST'])
@admin_or_manager_required
def edit_payroll(payroll_id):
    record = Payroll.query.get_or_404(payroll_id)

    if record.user_id == current_user.id:
        flash('You cannot edit your own payroll record.', 'danger')
        return redirect(url_for('payroll.view_payroll', payroll_id=payroll_id))

    if record.status != PayrollStatus.PENDING:
        flash('Only pending payroll records can be edited.', 'warning')
        return redirect(url_for('payroll.view_payroll', payroll_id=payroll_id))

    form = PayrollEditForm(obj=record)

    if form.validate_on_submit():
        period = _first_of_month(form.pay_period.data)

        duplicate = Payroll.query.filter(
            Payroll.user_id == record.user_id,
            Payroll.pay_period == period,
            Payroll.status != PayrollStatus.CANCELLED,
            Payroll.id != record.id,
        ).first()
        if duplicate:
            flash(
                f'{record.user.full_name} already has a payroll record for {period.strftime("%B %Y")}.',
                'danger',
            )
            return render_template('payroll/edit.html', form=form, record=record, title=f'Edit Payroll #{record.id}')

        changes = _detect_changes(record, form, period)

        if changes:
            for field_name, old_val, new_val in changes:
                db.session.add(PayrollEditLog(
                    payroll_id=record.id,
                    edited_by_id=current_user.id,
                    field_name=field_name,
                    old_value=old_val,
                    new_value=new_val,
                ))

            record.pay_period = period
            record.gross_amount = form.gross_amount.data
            record.bonus = form.bonus.data or 0
            record.deductions = form.deductions.data or 0
            record.notes = (form.notes.data or '').strip() or None
            record.updated_by_id = current_user.id
            record.updated_at = datetime.utcnow()
            db.session.commit()
            flash('Payroll record updated. Changes have been logged.', 'success')
        else:
            flash('No changes detected.', 'info')

        return redirect(url_for('payroll.view_payroll', payroll_id=record.id))

    return render_template(
        'payroll/edit.html', form=form, record=record, title=f'Edit Payroll #{record.id}'
    )


@payroll_bp.route('/<int:payroll_id>/mark-paid', methods=['GET', 'POST'])
@admin_or_manager_required
def mark_paid(payroll_id):
    record = Payroll.query.get_or_404(payroll_id)

    if record.user_id == current_user.id:
        flash('You cannot mark your own payroll record as paid.', 'danger')
        return redirect(url_for('payroll.view_payroll', payroll_id=payroll_id))

    if record.status != PayrollStatus.PENDING:
        flash('Only pending payroll records can be marked as paid.', 'warning')
        return redirect(url_for('payroll.view_payroll', payroll_id=payroll_id))

    form = PayrollMarkPaidForm()
    if form.validate_on_submit():
        record.status = PayrollStatus.PAID
        record.method = PayrollMethod(form.method.data)
        record.payment_date = form.payment_date.data
        record.updated_by_id = current_user.id
        record.updated_at = datetime.utcnow()
        db.session.commit()
        flash(f'Payroll #{record.id} marked as paid.', 'success')
        return redirect(url_for('payroll.view_payroll', payroll_id=record.id))

    return render_template(
        'payroll/mark_paid.html', form=form, record=record, title=f'Mark Paid — Payroll #{record.id}'
    )


@payroll_bp.route('/<int:payroll_id>/cancel', methods=['POST'])
@admin_or_manager_required
def cancel_payroll(payroll_id):
    record = Payroll.query.get_or_404(payroll_id)

    if record.user_id == current_user.id:
        flash('You cannot cancel your own payroll record.', 'danger')
        return redirect(url_for('payroll.view_payroll', payroll_id=payroll_id))

    if record.status != PayrollStatus.PENDING:
        flash('Only pending payroll records can be cancelled.', 'warning')
        return redirect(url_for('payroll.view_payroll', payroll_id=payroll_id))

    record.status = PayrollStatus.CANCELLED
    record.updated_by_id = current_user.id
    record.updated_at = datetime.utcnow()
    db.session.commit()
    flash(f'Payroll #{record.id} has been cancelled.', 'secondary')
    return redirect(url_for('payroll.view_payroll', payroll_id=record.id))


@payroll_bp.route('/my-payroll')
@login_required
def my_payroll():
    if current_user.role not in (UserRole.MANAGER, UserRole.TRAINER):
        return redirect(url_for('dashboard.home'))

    page = request.args.get('page', 1, type=int)
    records = (
        Payroll.query
        .filter_by(user_id=current_user.id)
        .order_by(Payroll.pay_period.desc())
        .paginate(page=page, per_page=10, error_out=False)
    )
    return render_template('payroll/my_payroll.html', records=records, title='My Payroll')


# ─────────────────────────── helpers ──────────────────────────── #

def _detect_changes(record, form, period):
    """Return list of (field_name, old_str, new_str) for changed fields."""
    changes = []
    checks = [
        ('pay_period', record.pay_period.strftime('%Y-%m-%d'), period.strftime('%Y-%m-%d')),
        ('gross_amount', str(record.gross_amount), str(form.gross_amount.data)),
        ('bonus', str(record.bonus), str(form.bonus.data or 0)),
        ('deductions', str(record.deductions), str(form.deductions.data or 0)),
        ('notes', record.notes or '', (form.notes.data or '').strip()),
    ]
    for field, old, new in checks:
        if old != new:
            changes.append((field, old or None, new or None))
    return changes
