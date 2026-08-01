import time
from datetime import datetime, date, timedelta
from flask import render_template, redirect, url_for, flash, request, abort, current_app, jsonify
from flask_login import current_user, login_required

from app.blueprints.payments import payments_bp
from app.blueprints.payments.forms import PaymentCreateForm, PaymentEditForm, BankTransferSubmitForm
from app.blueprints.payments.payhere import generate_hash, verify_notification
from app.blueprints.payments.sms import send_payment_confirmation
from app.extensions import db, csrf
from app.models.configuration import AppConfiguration
from app.models.installment import InstallmentPlan, Installment, InstallmentPlanStatus, InstallmentStatus
from app.models.member import Member
from app.models.membership import Membership, MembershipStatus
from app.models.package import Package
from app.models.payment import Payment, PaymentMethod, PaymentStatus, PaymentEditLog
from app.models.user import User, UserRole
from app.utils.decorators import admin_or_manager_required
from app.utils.search import parse_search_terms, multi_term_filter

PAYMENTS_PER_PAGE = 20


@payments_bp.route('/')
@admin_or_manager_required
def list_payments():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    method_filter = request.args.get('method', '')
    month_filter = request.args.get('month', '')  # YYYY-MM
    status_filter = request.args.get('status', '')  # '' / 'pending'

    query = (
        Payment.query
        .join(Member, Payment.member_id == Member.id)
        .join(User, Member.user_id == User.id)
    )

    terms = parse_search_terms(search)
    if terms:
        query = query.filter(multi_term_filter(terms, [
            User.first_name, User.last_name, User.email, Payment.reference_no,
        ]))

    if method_filter:
        try:
            query = query.filter(Payment.method == PaymentMethod(method_filter))
        except ValueError:
            pass

    # Default view lists only VERIFIED payments; the Pending tab is the
    # bank-transfer verification queue. Rejected payments aren't listed here.
    if status_filter == 'pending':
        query = query.filter(Payment.status == PaymentStatus.PENDING)
    else:
        query = query.filter(Payment.status == PaymentStatus.VERIFIED)

    if month_filter:
        try:
            year, month = map(int, month_filter.split('-'))
            from calendar import monthrange
            last_day = monthrange(year, month)[1]
            query = query.filter(
                Payment.payment_date >= date(year, month, 1),
                Payment.payment_date <= date(year, month, last_day),
            )
        except (ValueError, AttributeError):
            pass

    payments = query.order_by(Payment.payment_date.desc(), Payment.id.desc()).paginate(
        page=page, per_page=PAYMENTS_PER_PAGE, error_out=False
    )

    total_revenue = db.session.query(db.func.sum(Payment.amount)).filter(
        Payment.status == PaymentStatus.VERIFIED,
    ).scalar() or 0

    stats = {
        'total': Payment.query.filter(Payment.status == PaymentStatus.VERIFIED).count(),
        'total_revenue': total_revenue,
        'this_month': Payment.query.filter(
            Payment.payment_date >= date(date.today().year, date.today().month, 1),
            Payment.status == PaymentStatus.VERIFIED,
        ).count(),
        'this_month_revenue': db.session.query(db.func.sum(Payment.amount)).filter(
            Payment.payment_date >= date(date.today().year, date.today().month, 1),
            Payment.status == PaymentStatus.VERIFIED,
        ).scalar() or 0,
        'pending_verification': Payment.query.filter(
            Payment.status == PaymentStatus.PENDING,
        ).count(),
    }

    return render_template(
        'payments/list.html',
        payments=payments,
        search=search,
        method_filter=method_filter,
        month_filter=month_filter,
        status_filter=status_filter,
        stats=stats,
        payment_methods=PaymentMethod,
        title='Payments',
    )


@payments_bp.route('/create', methods=['GET', 'POST'])
@admin_or_manager_required
def create_payment():
    form = PaymentCreateForm()

    members = (
        Member.query
        .join(User, Member.user_id == User.id)
        .filter(Member.is_archived == False)
        .order_by(User.first_name.asc())
        .all()
    )
    form.member_id.choices = [(m.id, f'{m.full_name} ({m.email})') for m in members]

    # membership choices populated dynamically; start with empty + all option
    form.membership_id.choices = [(0, '— None / General Payment —')]

    preselect_member_id = request.args.get('member_id', type=int)
    preselect_membership_id = request.args.get('membership_id', type=int)

    if request.method == 'GET':
        if preselect_member_id:
            form.member_id.data = preselect_member_id
            _populate_memberships(form, preselect_member_id)
        if preselect_membership_id and form.membership_id.choices:
            form.membership_id.data = preselect_membership_id

    if form.validate_on_submit():
        member = Member.query.get_or_404(form.member_id.data)
        _populate_memberships(form, member.id)

        membership_id = form.membership_id.data if form.membership_id.data else None
        if membership_id == 0:
            membership_id = None

        if membership_id:
            ms = Membership.query.get(membership_id)
            if not ms or ms.member_id != member.id:
                flash('Invalid membership selected.', 'danger')
                return render_template('payments/create.html', form=form, title='Record Payment')

        payment = Payment(
            member_id=member.id,
            membership_id=membership_id,
            amount=form.amount.data,
            method=PaymentMethod(form.method.data),
            payment_date=form.payment_date.data,
            reference_no=form.reference_no.data.strip() or None,
            notes=form.notes.data.strip() or None,
            created_by_id=current_user.id,
        )
        db.session.add(payment)
        db.session.commit()

        flash(
            f'Payment of LKR {payment.amount:,.2f} recorded for {member.full_name}.',
            'success',
        )

        sms_ok, sms_error = send_payment_confirmation(payment)
        if sms_ok:
            flash('Payment confirmation SMS sent to the member.', 'info')
        elif sms_error != 'SMS gateway not configured':
            flash(f'Confirmation SMS could not be sent: {sms_error}', 'warning')

        return redirect(url_for('payments.view_payment', payment_id=payment.id))

    # On POST validation failure, re-populate memberships for chosen member
    if request.method == 'POST' and form.member_id.data:
        _populate_memberships(form, form.member_id.data)

    return render_template('payments/create.html', form=form, title='Record Payment')


@payments_bp.route('/<int:payment_id>')
@admin_or_manager_required
def view_payment(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    edit_logs = payment.edit_logs.all()
    return render_template(
        'payments/view.html',
        payment=payment,
        edit_logs=edit_logs,
        title=f'Payment #{payment.id}',
    )


@payments_bp.route('/<int:payment_id>/edit', methods=['GET', 'POST'])
@admin_or_manager_required
def edit_payment(payment_id):
    """FR-PAY-03: editing restricted to Admin and fully audited."""
    payment = Payment.query.get_or_404(payment_id)
    form = PaymentEditForm(obj=payment)

    if form.validate_on_submit():
        changes = _detect_changes(payment, form)

        if changes:
            for field_name, old_val, new_val in changes:
                log = PaymentEditLog(
                    payment_id=payment.id,
                    edited_by_id=current_user.id,
                    field_name=field_name,
                    old_value=old_val,
                    new_value=new_val,
                )
                db.session.add(log)

            payment.amount = form.amount.data
            payment.method = PaymentMethod(form.method.data)
            payment.payment_date = form.payment_date.data
            payment.reference_no = form.reference_no.data.strip() or None
            payment.notes = form.notes.data.strip() or None
            payment.updated_by_id = current_user.id
            payment.updated_at = datetime.utcnow()
            db.session.commit()
            flash('Payment updated. Changes have been logged.', 'success')
        else:
            flash('No changes detected.', 'info')

        return redirect(url_for('payments.view_payment', payment_id=payment.id))

    # Pre-populate method on GET
    if request.method == 'GET':
        form.method.data = payment.method.value

    return render_template(
        'payments/edit.html',
        form=form,
        payment=payment,
        title=f'Edit Payment #{payment.id}',
    )


@payments_bp.route('/memberships-for-member/<int:member_id>')
@admin_or_manager_required
def memberships_for_member(member_id):
    """AJAX: return memberships for a given member as JSON for the create form."""
    memberships = (
        Membership.query
        .filter_by(member_id=member_id)
        .order_by(Membership.start_date.desc())
        .all()
    )
    data = [{'id': 0, 'label': '— None / General Payment —'}] + [
        {
            'id': ms.id,
            'label': (
                f'#{ms.id} {ms.package.name} '
                f'({ms.start_date.strftime("%d %b %Y")} → {ms.end_date.strftime("%d %b %Y")}) '
                f'[{ms.status_label}]'
            ),
        }
        for ms in memberships
    ]
    return jsonify(data)


# ─────────────────────────── helpers ──────────────────────────── #

def _populate_memberships(form, member_id):
    memberships = (
        Membership.query
        .filter_by(member_id=member_id)
        .order_by(Membership.start_date.desc())
        .all()
    )
    form.membership_id.choices = [(0, '— None / General Payment —')] + [
        (ms.id,
         f'#{ms.id} {ms.package.name} ({ms.start_date.strftime("%d %b %Y")} → '
         f'{ms.end_date.strftime("%d %b %Y")}) [{ms.status_label}]')
        for ms in memberships
    ]


def _detect_changes(payment, form):
    """Return list of (field_name, old_str, new_str) for changed fields."""
    changes = []
    new_method = PaymentMethod(form.method.data)

    checks = [
        ('amount', str(payment.amount), str(form.amount.data)),
        ('method', payment.method.label, new_method.label),
        ('payment_date',
         payment.payment_date.strftime('%Y-%m-%d'),
         form.payment_date.data.strftime('%Y-%m-%d')),
        ('reference_no', payment.reference_no or '', form.reference_no.data.strip()),
        ('notes', payment.notes or '', form.notes.data.strip()),
    ]
    for field, old, new in checks:
        if old != new:
            changes.append((field, old or None, new or None))
    return changes


# ─────────────────────────── PayHere routes ──────────────────────────── #

@payments_bp.route('/buy')
@login_required
def buy():
    """Member self-service: choose a package and start date before paying."""
    if current_user.role != UserRole.MEMBER:
        abort(403)
    if not current_user.member_profile:
        flash('Member profile not found. Please contact staff.', 'danger')
        return redirect(url_for('dashboard.home'))

    packages = (
        Package.query
        .filter_by(is_active=True, is_archived=False)
        .order_by(Package.price.asc())
        .all()
    )

    today = date.today()
    active_membership = (
        Membership.query
        .filter(
            Membership.member_id == current_user.member_profile.id,
            Membership.status == MembershipStatus.ACTIVE,
            Membership.end_date >= today,
        )
        .order_by(Membership.end_date.desc())
        .first()
    )

    pending_membership = (
        Membership.query
        .filter(
            Membership.member_id == current_user.member_profile.id,
            Membership.status == MembershipStatus.PENDING,
        )
        .order_by(Membership.created_at.desc())
        .first()
    )

    min_date = (active_membership.end_date + timedelta(days=1)) if active_membership else today

    return render_template(
        'payments/buy.html',
        packages=packages,
        active_membership=active_membership,
        pending_membership=pending_membership,
        min_date=min_date.strftime('%Y-%m-%d'),
        title='Choose a Plan',
    )


@payments_bp.route('/checkout')
@login_required
def payhere_checkout():
    """Member-facing: build PayHere checkout form for a chosen package + start date."""
    # PayHere authorizes by domain — only `localhost` is registered, and
    # 127.0.0.1 counts as a different domain. Bounce to localhost first.
    if request.host.startswith('127.0.0.1'):
        return redirect(request.url.replace('127.0.0.1', 'localhost', 1))

    if current_user.role != UserRole.MEMBER:
        abort(403)
    if not current_user.member_profile:
        flash('Member profile not found. Please contact staff.', 'danger')
        return redirect(url_for('dashboard.home'))

    existing_pending = Membership.query.filter(
        Membership.member_id == current_user.member_profile.id,
        Membership.status == MembershipStatus.PENDING,
    ).first()
    if existing_pending:
        flash(
            'You already have a bank transfer submission awaiting verification. '
            'Please wait for staff to confirm it before starting a new payment.',
            'warning',
        )
        return redirect(url_for('memberships.view_membership', membership_id=existing_pending.id))

    package_id = request.args.get('package_id', type=int)
    start_date_str = request.args.get('start_date', '').strip()

    if not package_id or not start_date_str:
        flash('Please select a package and start date.', 'danger')
        return redirect(url_for('payments.buy'))

    package = Package.query.get_or_404(package_id)
    if not package.is_active or package.is_archived:
        flash('This package is no longer available.', 'danger')
        return redirect(url_for('payments.buy'))

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid start date.', 'danger')
        return redirect(url_for('payments.buy'))

    if start_date < date.today():
        flash('Start date cannot be in the past.', 'danger')
        return redirect(url_for('payments.buy'))

    member = current_user.member_profile
    end_date = Membership.calculate_end_date(start_date, package.duration_months)

    merchant_id = current_app.config['PAYHERE_MERCHANT_ID']
    merchant_secret = current_app.config['PAYHERE_MERCHANT_SECRET']
    ts = int(time.time())
    order_id = f'GMS-{package_id}-{member.id}-{start_date.strftime("%Y%m%d")}-{ts}'
    amount = float(package.price)
    currency = 'LKR'

    notify_base = current_app.config.get('PAYHERE_NOTIFY_BASE_URL', '').rstrip('/')
    notify_url = (
        f'{notify_base}/payments/notify' if notify_base
        else url_for('payments.payhere_notify', _external=True)
    )

    app_base = current_app.config.get('PAYHERE_APP_BASE_URL', '').rstrip('/')
    return_url = (
        f'{app_base}/payments/return' if app_base
        else url_for('payments.payhere_return', _external=True)
    )
    cancel_url = (
        f'{app_base}/payments/cancel' if app_base
        else url_for('payments.payhere_cancel', _external=True)
    )

    computed_hash = generate_hash(merchant_id, order_id, amount, currency, merchant_secret)

    # Debug — visible in Flask dev server terminal
    current_app.logger.warning(
        '[PayHere DEBUG] host=%s merchant_id=%s order_id=%s amount=%s currency=%s hash=%s notify=%s return=%s',
        request.host, merchant_id, order_id, f'{amount:.2f}', currency, computed_hash, notify_url, return_url,
    )

    payhere_data = {
        'merchant_id': merchant_id,
        'return_url':  return_url,
        'cancel_url':  cancel_url,
        'notify_url':  notify_url,
        'order_id':    order_id,
        'items':       f'{package.name} — {package.duration_label}',
        'currency':    currency,
        'amount':      f'{amount:.2f}',
        'first_name':  member.user.first_name,
        'last_name':   member.user.last_name,
        'email':       member.user.email,
        'phone':       member.user.phone or '',
        'address':     member.address or 'Gym',
        'city':        'Colombo',
        'country':     'Sri Lanka',
        'hash':        computed_hash,
    }

    from flask import make_response
    resp = make_response(render_template(
        'payments/checkout.html',
        payhere_data=payhere_data,
        payhere_url=current_app.config['PAYHERE_BASE_URL'],
        package=package,
        start_date=start_date,
        end_date=end_date,
        title='Pay Online',
    ))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    return resp


# ─────────────────────────── Bank Transfer routes ──────────────────────────── #

def _validate_package_and_date(package_id, start_date_str):
    """Shared re-validation for both PayHere and Bank Transfer flows.
    Returns (package, start_date) or (None, None) after flashing + the caller
    should redirect to payments.buy."""
    if not package_id or not start_date_str:
        flash('Please select a package and start date.', 'danger')
        return None, None

    package = Package.query.get(package_id)
    if not package or not package.is_active or package.is_archived:
        flash('This package is no longer available.', 'danger')
        return None, None

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid start date.', 'danger')
        return None, None

    if start_date < date.today():
        flash('Start date cannot be in the past.', 'danger')
        return None, None

    return package, start_date


def _resolve_installment_count(package, raw):
    """Return a validated installment count (>=2) for this package, or 0
    (pay in full) if the raw value is missing/invalid/not offered."""
    if not raw:
        return 0
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return 0
    if package.allow_installments and n in package.installment_options_list:
        return n
    return 0


@payments_bp.route('/bank-transfer', methods=['GET', 'POST'])
@login_required
def bank_transfer():
    """Member-facing: submit a bank transfer reference number for a chosen
    package + start date. Creates a PENDING Membership + PENDING Payment —
    both stay inactive until an Admin/Manager verifies the transfer."""
    if current_user.role != UserRole.MEMBER:
        abort(403)
    if not current_user.member_profile:
        flash('Member profile not found. Please contact staff.', 'danger')
        return redirect(url_for('dashboard.home'))

    member = current_user.member_profile

    existing_pending = (
        Membership.query
        .filter(
            Membership.member_id == member.id,
            Membership.status == MembershipStatus.PENDING,
        )
        .order_by(Membership.created_at.desc())
        .first()
    )
    if existing_pending:
        flash(
            'You already have a bank transfer submission awaiting verification. '
            'Please wait for staff to confirm it before submitting another.',
            'warning',
        )
        return redirect(url_for('memberships.view_membership', membership_id=existing_pending.id))

    package_id = request.args.get('package_id', type=int) or request.form.get('package_id', type=int)
    start_date_str = (request.args.get('start_date') or request.form.get('start_date') or '').strip()
    installments_raw = request.args.get('installments') or request.form.get('installments')

    package, start_date = _validate_package_and_date(package_id, start_date_str)
    if not package:
        return redirect(url_for('payments.buy'))

    installment_count = _resolve_installment_count(package, installments_raw)
    end_date = Membership.calculate_end_date(start_date, package.duration_months)
    settings = AppConfiguration.get()

    if installment_count:
        installment_amounts = InstallmentPlan.split_amount(package.price, installment_count)
        installment_due_dates = InstallmentPlan.build_due_dates(start_date, end_date, installment_count)
        first_amount = installment_amounts[0]
    else:
        installment_amounts = None
        installment_due_dates = None
        first_amount = package.price

    form = BankTransferSubmitForm()

    if form.validate_on_submit():
        membership = Membership(
            member_id=member.id,
            package_id=package.id,
            start_date=start_date,
            end_date=end_date,
            status=MembershipStatus.PENDING,
            notes=(
                f'Awaiting bank transfer verification (Installment 1 of {installment_count}).'
                if installment_count else 'Awaiting bank transfer verification.'
            ),
            created_by_id=current_user.id,
        )
        db.session.add(membership)
        db.session.flush()

        first_installment = None
        if installment_count:
            plan = InstallmentPlan(
                membership_id=membership.id,
                member_id=member.id,
                package_id=package.id,
                total_amount=package.price,
                installment_count=installment_count,
                status=InstallmentPlanStatus.ACTIVE,
                created_by_id=current_user.id,
            )
            db.session.add(plan)
            db.session.flush()

            for seq, (amt, due) in enumerate(zip(installment_amounts, installment_due_dates), start=1):
                installment = Installment(
                    plan_id=plan.id,
                    sequence_no=seq,
                    amount=amt,
                    due_date=due,
                    status=InstallmentStatus.SUBMITTED if seq == 1 else InstallmentStatus.PENDING,
                )
                db.session.add(installment)
                if seq == 1:
                    first_installment = installment
            db.session.flush()

        payment = Payment(
            member_id=member.id,
            membership_id=membership.id,
            installment_id=first_installment.id if first_installment else None,
            amount=first_amount,
            method=PaymentMethod.BANK_TRANSFER,
            payment_date=date.today(),
            reference_no=form.reference_no.data.strip(),
            notes=form.notes.data.strip() or None,
            status=PaymentStatus.PENDING,
            created_by_id=current_user.id,
        )
        db.session.add(payment)
        db.session.commit()

        _notify_staff_of_membership_request(membership, payment)

        flash(
            'Your bank transfer has been submitted and is awaiting verification by staff. '
            'Your membership will activate once confirmed.',
            'success',
        )
        return redirect(url_for('memberships.view_membership', membership_id=membership.id))

    return render_template(
        'payments/bank_transfer.html',
        form=form,
        package=package,
        start_date=start_date,
        end_date=end_date,
        bank_details=settings.bank_transfer_details,
        installment_count=installment_count,
        installment_amounts=installment_amounts,
        installment_due_dates=installment_due_dates,
        first_amount=first_amount,
        title='Pay by Bank Transfer',
    )


@payments_bp.route('/installment/<int:installment_id>/pay', methods=['GET', 'POST'])
@login_required
def pay_installment(installment_id):
    """Member-facing: submit a bank transfer reference for a specific due
    installment slot (#2 onward) of an existing InstallmentPlan. Installment
    #1 is handled by bank_transfer() as part of creating the membership —
    this route only ever deals with later slots."""
    installment = Installment.query.get_or_404(installment_id)
    plan = installment.plan

    if current_user.role != UserRole.MEMBER:
        abort(403)
    if not current_user.member_profile or current_user.member_profile.id != plan.member_id:
        abort(403)

    if plan.status != InstallmentPlanStatus.ACTIVE:
        flash('This installment plan is no longer active.', 'warning')
        return redirect(url_for('memberships.view_membership', membership_id=plan.membership_id))

    if installment.status == InstallmentStatus.PAID:
        flash('This installment has already been paid.', 'info')
        return redirect(url_for('memberships.view_membership', membership_id=plan.membership_id))

    if installment.status == InstallmentStatus.SUBMITTED:
        flash(
            'You already submitted a reference for this installment — it is awaiting staff verification.',
            'warning',
        )
        return redirect(url_for('memberships.view_membership', membership_id=plan.membership_id))

    next_due = plan.next_due
    if next_due and next_due.id != installment.id:
        flash('Please pay installments in order.', 'warning')
        return redirect(url_for('memberships.view_membership', membership_id=plan.membership_id))

    settings = AppConfiguration.get()
    form = BankTransferSubmitForm()

    if form.validate_on_submit():
        payment = Payment(
            member_id=plan.member_id,
            membership_id=plan.membership_id,
            installment_id=installment.id,
            amount=installment.amount,
            method=PaymentMethod.BANK_TRANSFER,
            payment_date=date.today(),
            reference_no=form.reference_no.data.strip(),
            notes=form.notes.data.strip() or None,
            status=PaymentStatus.PENDING,
            created_by_id=current_user.id,
        )
        db.session.add(payment)
        installment.status = InstallmentStatus.SUBMITTED
        db.session.commit()

        _notify_staff_of_installment_submission(installment, payment)

        flash(
            f'Installment {installment.sequence_no} of {plan.installment_count} submitted '
            'and is awaiting verification by staff.',
            'success',
        )
        return redirect(url_for('memberships.view_membership', membership_id=plan.membership_id))

    return render_template(
        'payments/pay_installment.html',
        form=form,
        installment=installment,
        plan=plan,
        bank_details=settings.bank_transfer_details,
        title='Pay Installment',
    )


@payments_bp.route('/<int:payment_id>/verify', methods=['POST'])
@admin_or_manager_required
def verify_payment(payment_id):
    """Confirm a member-submitted bank transfer: activates the linked
    (PENDING) membership and marks the payment VERIFIED."""
    payment = Payment.query.get_or_404(payment_id)

    if payment.method != PaymentMethod.BANK_TRANSFER or payment.status != PaymentStatus.PENDING:
        flash('Only pending bank transfer payments can be verified.', 'warning')
        return redirect(url_for('payments.view_payment', payment_id=payment.id))

    payment.status = PaymentStatus.VERIFIED
    payment.verified_by_id = current_user.id
    payment.verified_at = datetime.utcnow()
    payment.updated_by_id = current_user.id
    payment.updated_at = datetime.utcnow()

    activates_membership = False
    if payment.membership and payment.membership.status == MembershipStatus.PENDING:
        payment.membership.status = MembershipStatus.ACTIVE
        payment.membership.notes = f'Activated via verified bank transfer. Ref: {payment.reference_no}'
        payment.membership.updated_by_id = current_user.id
        payment.membership.updated_at = datetime.utcnow()
        activates_membership = True

    if payment.installment:
        installment = payment.installment
        installment.status = InstallmentStatus.PAID
        installment.paid_at = datetime.utcnow()
        plan = installment.plan
        if plan.paid_count >= plan.installment_count:
            plan.status = InstallmentPlanStatus.COMPLETED
            plan.updated_at = datetime.utcnow()

    db.session.commit()

    if payment.installment:
        _notify_member_of_installment_verified(payment)
    else:
        _notify_member_of_activation(payment)

    sms_ok, sms_error = send_payment_confirmation(payment)

    if payment.installment:
        plan = payment.installment.plan
        flash(
            f'Payment #{payment.id} verified — installment {payment.installment.sequence_no} of '
            f'{plan.installment_count}'
            + (' (membership activated).' if activates_membership else '.')
            + ' The member has been notified.',
            'success',
        )
    else:
        flash(f'Payment #{payment.id} verified. Membership activated. The member has been notified.', 'success')
    if not sms_ok and sms_error != 'SMS gateway not configured':
        flash(f'Confirmation SMS could not be sent: {sms_error}', 'warning')

    return redirect(url_for('payments.view_payment', payment_id=payment.id))


@payments_bp.route('/<int:payment_id>/reject', methods=['POST'])
@admin_or_manager_required
def reject_payment(payment_id):
    """Reject a member-submitted bank transfer: cancels the linked (PENDING)
    membership and marks the payment REJECTED."""
    payment = Payment.query.get_or_404(payment_id)

    if payment.method != PaymentMethod.BANK_TRANSFER or payment.status != PaymentStatus.PENDING:
        flash('Only pending bank transfer payments can be rejected.', 'warning')
        return redirect(url_for('payments.view_payment', payment_id=payment.id))

    reason = request.form.get('rejection_reason', '').strip()
    if not reason:
        flash('A rejection reason is required so the member can be notified why.', 'danger')
        return redirect(request.referrer or url_for('payments.view_payment', payment_id=payment.id))

    payment.status = PaymentStatus.REJECTED
    payment.rejection_reason = reason
    payment.verified_by_id = current_user.id
    payment.verified_at = datetime.utcnow()
    payment.updated_by_id = current_user.id
    payment.updated_at = datetime.utcnow()

    # A later installment (#2+) is just a collection attempt on an already-active
    # membership — rejecting it only reopens that slot, it never touches the
    # membership. Installment #1 (or a plain non-installment bank transfer) IS
    # the thing that grants access, so rejecting it cancels the membership/plan.
    is_later_installment = payment.installment is not None and payment.installment.sequence_no > 1

    if is_later_installment:
        payment.installment.status = InstallmentStatus.PENDING
    elif payment.membership and payment.membership.status == MembershipStatus.PENDING:
        payment.membership.status = MembershipStatus.CANCELLED
        payment.membership.notes = f'Cancelled — bank transfer rejected. Ref: {payment.reference_no}'
        payment.membership.updated_by_id = current_user.id
        payment.membership.updated_at = datetime.utcnow()
        if payment.installment:
            plan = payment.installment.plan
            plan.status = InstallmentPlanStatus.CANCELLED
            plan.updated_at = datetime.utcnow()

    db.session.commit()
    _notify_member_of_rejection(payment, reason)

    flash(f'Payment #{payment.id} rejected. The member has been notified.', 'secondary')
    return redirect(url_for('payments.view_payment', payment_id=payment.id))


@payments_bp.route('/<int:payment_id>/cancel-request', methods=['POST'])
@login_required
def cancel_request(payment_id):
    """Member-facing: withdraw a still-pending bank transfer request the member
    submitted. Cancels the linked PENDING membership and marks the payment
    REJECTED. Only the owning member, only while still PENDING (i.e. before an
    Admin/Manager has verified or rejected it)."""
    payment = Payment.query.get_or_404(payment_id)

    if current_user.role != UserRole.MEMBER:
        abort(403)
    if (not current_user.member_profile
            or current_user.member_profile.id != payment.member_id):
        abort(403)

    if payment.method != PaymentMethod.BANK_TRANSFER or payment.status != PaymentStatus.PENDING:
        flash(
            'This request can no longer be cancelled — staff have already processed it.',
            'warning',
        )
        return redirect(url_for('memberships.view_membership', membership_id=payment.membership_id)
                        if payment.membership_id else url_for('payments.buy'))

    payment.status = PaymentStatus.REJECTED
    payment.rejection_reason = 'Cancelled by the member before verification.'
    payment.updated_by_id = current_user.id
    payment.updated_at = datetime.utcnow()

    is_later_installment = payment.installment is not None and payment.installment.sequence_no > 1

    if is_later_installment:
        payment.installment.status = InstallmentStatus.PENDING
    elif payment.membership and payment.membership.status == MembershipStatus.PENDING:
        payment.membership.status = MembershipStatus.CANCELLED
        payment.membership.notes = 'Cancelled by the member before verification.'
        payment.membership.updated_by_id = current_user.id
        payment.membership.updated_at = datetime.utcnow()
        if payment.installment:
            plan = payment.installment.plan
            plan.status = InstallmentPlanStatus.CANCELLED
            plan.updated_at = datetime.utcnow()

    db.session.commit()
    _notify_staff_of_request_cancellation(payment)

    if is_later_installment:
        flash('Your installment submission has been withdrawn. You can resubmit anytime.', 'secondary')
        return redirect(url_for('memberships.view_membership', membership_id=payment.membership_id))

    flash('Your membership request has been cancelled. You can submit a new one anytime.', 'secondary')
    return redirect(url_for('payments.buy'))


def _notify_staff_of_request_cancellation(payment):
    """In-app notice to every Admin + Manager that a member has withdrawn a
    membership request they had previously submitted (keeps the earlier
    "New Membership Request" alert from going stale)."""
    from app.models.notification import Notification, NotificationAudience
    from app.blueprints.notifications.service import resolve_audience, dispatch_notification

    recipients = resolve_audience(NotificationAudience.ADMINS_MANAGERS)
    if not recipients:
        return

    package_name = payment.membership.package.name if payment.membership else 'a package'

    if payment.installment and payment.installment.sequence_no > 1:
        plan = payment.installment.plan
        message = (
            f'{payment.member.full_name} withdrew their bank transfer submission for installment '
            f'{payment.installment.sequence_no} of {plan.installment_count} ("{package_name}") '
            f'(Ref: {payment.reference_no}) before it was verified. No action is needed.'
        )
    else:
        message = (
            f'{payment.member.full_name} cancelled their membership request for '
            f'"{package_name}" (Ref: {payment.reference_no}) before it was verified. '
            'No action is needed.'
        )

    notification = Notification(
        title='Membership Request Cancelled',
        message=message,
        audience=NotificationAudience.ADMINS_MANAGERS,
        is_auto=False,
        created_by_id=payment.member.user_id,
    )
    db.session.add(notification)
    db.session.flush()
    dispatch_notification(notification, recipients)
    db.session.commit()


def _notify_staff_of_membership_request(membership, payment):
    """In-app notice to every Admin + Manager that a member has requested a
    membership (bank transfer awaiting verification). Surfaces in the topbar
    notification bell / inbox of each staff member."""
    from app.models.notification import Notification, NotificationAudience
    from app.blueprints.notifications.service import resolve_audience, dispatch_notification

    recipients = resolve_audience(NotificationAudience.ADMINS_MANAGERS)
    if not recipients:
        return

    member_name = payment.member.full_name
    installment_note = ''
    if payment.installment and payment.installment.plan:
        plan = payment.installment.plan
        installment_note = f' (Installment 1 of {plan.installment_count} — total plan value LKR {plan.total_amount:,.2f})'
    notification = Notification(
        title='New Membership Request',
        message=(
            f'{member_name} has requested the "{membership.package.name}" package via bank transfer '
            f'and is awaiting verification.\n\n'
            f'Amount: LKR {payment.amount:,.2f}{installment_note}\n'
            f'Reference: {payment.reference_no}\n'
            f'Requested period: {membership.start_date.strftime("%d %b %Y")} → '
            f'{membership.end_date.strftime("%d %b %Y")}\n\n'
            'Review it to verify or reject the transfer.'
        ),
        audience=NotificationAudience.ADMINS_MANAGERS,
        is_auto=False,
        link_url=url_for('memberships.view_membership', membership_id=membership.id),
        created_by_id=payment.created_by_id,
    )
    db.session.add(notification)
    db.session.flush()
    dispatch_notification(notification, recipients)
    db.session.commit()


def _notify_staff_of_installment_submission(installment, payment):
    """In-app notice to every Admin + Manager that a member has submitted a
    reference number for a later (#2+) installment slot — the membership is
    already active, this is purely a collection event to verify."""
    from app.models.notification import Notification, NotificationAudience
    from app.blueprints.notifications.service import resolve_audience, dispatch_notification

    recipients = resolve_audience(NotificationAudience.ADMINS_MANAGERS)
    if not recipients:
        return

    plan = installment.plan
    notification = Notification(
        title='Installment Payment Submitted',
        message=(
            f'{payment.member.full_name} submitted a bank transfer for installment '
            f'{installment.sequence_no} of {plan.installment_count} '
            f'("{plan.package.name}").\n\n'
            f'Amount: LKR {payment.amount:,.2f}\n'
            f'Reference: {payment.reference_no}\n\n'
            'Review it to verify or reject the transfer.'
        ),
        audience=NotificationAudience.ADMINS_MANAGERS,
        is_auto=False,
        link_url=url_for('memberships.view_membership', membership_id=plan.membership_id),
        created_by_id=payment.created_by_id,
    )
    db.session.add(notification)
    db.session.flush()
    dispatch_notification(notification, recipients)
    db.session.commit()


def _notify_member_of_activation(payment):
    """In-app notice to the member that their verified bank transfer has
    activated their membership. Mirrors _notify_member_of_rejection — the
    positive counterpart fired from verify_payment."""
    from app.models.notification import Notification, NotificationAudience
    from app.blueprints.notifications.service import dispatch_notification

    membership = payment.membership
    package_name = membership.package.name if membership else 'your membership'

    message = (
        f'Good news! Your bank transfer (Ref: {payment.reference_no}) has been verified '
        f'and your "{package_name}" membership is now active.'
    )
    if membership:
        message += (
            f'\n\nValid: {membership.start_date.strftime("%d %b %Y")} → '
            f'{membership.end_date.strftime("%d %b %Y")}'
        )
    message += '\n\nEnjoy your training!'

    notification = Notification(
        title='Membership Activated',
        message=message,
        audience=NotificationAudience.SINGLE_MEMBER,
        is_auto=False,
        link_url=(
            url_for('memberships.view_membership', membership_id=membership.id)
            if membership else None
        ),
        created_by_id=payment.verified_by_id,
    )
    db.session.add(notification)
    db.session.flush()
    dispatch_notification(notification, [payment.member.user])
    db.session.commit()


def _notify_member_of_rejection(payment, reason):
    """In-app notice to the member explaining why their bank transfer was rejected."""
    from app.models.notification import Notification, NotificationAudience
    from app.blueprints.notifications.service import dispatch_notification

    package_name = payment.membership.package.name if payment.membership else 'your membership'
    is_later_installment = payment.installment is not None and payment.installment.sequence_no > 1

    installment_note = ''
    if payment.installment:
        plan = payment.installment.plan
        installment_note = f' (Installment {payment.installment.sequence_no} of {plan.installment_count})'

    follow_up = (
        'Please submit a new reference for this installment, or contact the gym reception if you have questions.'
        if is_later_installment else
        'Please contact the gym reception if you have questions, or submit a new payment.'
    )

    notification = Notification(
        title='Bank Transfer Rejected',
        message=(
            f'Your bank transfer (Ref: {payment.reference_no}) for {package_name}{installment_note} could not be '
            f'verified and has been rejected.\n\nReason: {reason}\n\n{follow_up}'
        ),
        audience=NotificationAudience.SINGLE_MEMBER,
        is_auto=False,
        created_by_id=payment.verified_by_id,
    )
    db.session.add(notification)
    db.session.flush()
    dispatch_notification(notification, [payment.member.user])
    db.session.commit()


def _notify_member_of_installment_verified(payment):
    """In-app notice to the member that a specific installment payment has
    been verified. For installment #1 this is also when the membership
    activates for its full term; for #2+ the membership was already active."""
    from app.models.notification import Notification, NotificationAudience
    from app.blueprints.notifications.service import dispatch_notification

    installment = payment.installment
    plan = installment.plan
    membership = payment.membership

    if installment.sequence_no == 1:
        message = (
            f'Good news! Your bank transfer (Ref: {payment.reference_no}) for installment 1 of '
            f'{plan.installment_count} has been verified and your "{plan.package.name}" membership '
            'is now active for the full term.'
        )
    else:
        message = (
            f'Your bank transfer (Ref: {payment.reference_no}) for installment {installment.sequence_no} '
            f'of {plan.installment_count} ("{plan.package.name}") has been verified. Thank you!'
        )

    next_due = plan.next_due
    if next_due:
        message += (
            f'\n\nNext due: installment {next_due.sequence_no} of {plan.installment_count} — '
            f'LKR {next_due.amount:,.2f} on {next_due.due_date.strftime("%d %b %Y")}.'
        )
    else:
        message += '\n\nThis was the final installment — the plan is now fully paid.'

    notification = Notification(
        title='Installment Payment Verified',
        message=message,
        audience=NotificationAudience.SINGLE_MEMBER,
        is_auto=False,
        link_url=(
            url_for('memberships.view_membership', membership_id=membership.id)
            if membership else None
        ),
        created_by_id=payment.verified_by_id,
    )
    db.session.add(notification)
    db.session.flush()
    dispatch_notification(notification, [payment.member.user])
    db.session.commit()


@payments_bp.route('/notify', methods=['POST'])
@csrf.exempt
def payhere_notify():
    """PayHere server-to-server notification. CSRF exempt — verified by hash.
    Creates Membership then Payment from encoded order_id: GMS-{pkg}-{member}-{date}-{ts}
    """
    merchant_secret = current_app.config['PAYHERE_MERCHANT_SECRET']

    if not verify_notification(request.form, merchant_secret):
        return 'Invalid hash', 400

    status_code    = int(request.form.get('status_code', -1))
    order_id       = request.form.get('order_id', '')
    payhere_amount = request.form.get('payhere_amount', '0')
    payhere_method = request.form.get('method', '')

    if not order_id.startswith('GMS-'):
        return 'Invalid order', 400

    parts = order_id.split('-')
    if len(parts) != 5:
        return 'Invalid order format', 400

    try:
        package_id  = int(parts[1])
        member_id   = int(parts[2])
        start_date  = datetime.strptime(parts[3], '%Y%m%d').date()
    except (IndexError, ValueError):
        return 'Invalid order', 400

    member  = Member.query.get(member_id)
    package = Package.query.get(package_id)
    if not member or not package:
        return 'Not found', 404

    if status_code == 2:  # PayHere success
        already_paid = Payment.query.filter_by(reference_no=order_id).first()
        if not already_paid:
            end_date = Membership.calculate_end_date(start_date, package.duration_months)
            membership = Membership(
                member_id=member_id,
                package_id=package_id,
                start_date=start_date,
                end_date=end_date,
                status=MembershipStatus.ACTIVE,
                notes=f'Created via PayHere online payment. Order: {order_id}',
            )
            db.session.add(membership)
            db.session.flush()

            payment = Payment(
                member_id=member_id,
                membership_id=membership.id,
                amount=float(payhere_amount),
                method=PaymentMethod.ONLINE,
                payment_date=date.today(),
                reference_no=order_id,
                notes=f'PayHere online payment. Gateway method: {payhere_method}',
            )
            db.session.add(payment)
            db.session.commit()

            sms_ok, sms_error = send_payment_confirmation(payment)
            if not sms_ok:
                current_app.logger.warning(
                    '[PayHere] Confirmation SMS not sent for %s: %s',
                    order_id, sms_error,
                )

    return 'OK', 200


@payments_bp.route('/return')
@login_required
def payhere_return():
    return render_template('payments/return.html', title='Payment Successful')


@payments_bp.route('/cancel')
@login_required
def payhere_cancel():
    return render_template('payments/cancel.html', title='Payment Cancelled')


@payments_bp.route('/ph-debug')
@admin_or_manager_required
def payhere_debug():
    """Dev-only: show hash calculation so you can verify against PayHere docs."""
    import hashlib
    from flask import jsonify

    merchant_id     = current_app.config['PAYHERE_MERCHANT_ID']
    merchant_secret = current_app.config['PAYHERE_MERCHANT_SECRET']
    order_id        = 'TEST-001'
    amount_str      = '100.00'
    currency        = 'LKR'

    secret_hash = hashlib.md5(merchant_secret.encode()).hexdigest().upper()
    raw         = f'{merchant_id}{order_id}{amount_str}{currency}{secret_hash}'
    final_hash  = hashlib.md5(raw.encode()).hexdigest().upper()

    return jsonify({
        'merchant_id':   merchant_id,
        'secret_prefix': merchant_secret[:6] + '...',
        'secret_length': len(merchant_secret),
        'secret_hash':   secret_hash,
        'raw_string':    raw,
        'final_hash':    final_hash,
        'formula':       'MD5( merchant_id + order_id + amount + currency + MD5(secret).upper() ).upper()',
    })
