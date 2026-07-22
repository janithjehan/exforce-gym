import time
from datetime import datetime, date, timedelta
from flask import render_template, redirect, url_for, flash, request, abort, current_app, jsonify
from flask_login import current_user, login_required

from app.blueprints.payments import payments_bp
from app.blueprints.payments.forms import PaymentCreateForm, PaymentEditForm
from app.blueprints.payments.payhere import generate_hash, verify_notification
from app.blueprints.payments.sms import send_payment_confirmation
from app.extensions import db, csrf
from app.models.member import Member
from app.models.membership import Membership, MembershipStatus
from app.models.package import Package
from app.models.payment import Payment, PaymentMethod, PaymentEditLog
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

    total_revenue = db.session.query(
        db.func.sum(Payment.amount)
    ).scalar() or 0

    stats = {
        'total': Payment.query.count(),
        'total_revenue': total_revenue,
        'this_month': Payment.query.filter(
            Payment.payment_date >= date(date.today().year, date.today().month, 1),
        ).count(),
        'this_month_revenue': db.session.query(db.func.sum(Payment.amount)).filter(
            Payment.payment_date >= date(date.today().year, date.today().month, 1),
        ).scalar() or 0,
    }

    return render_template(
        'payments/list.html',
        payments=payments,
        search=search,
        method_filter=method_filter,
        month_filter=month_filter,
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

    min_date = (active_membership.end_date + timedelta(days=1)) if active_membership else today

    return render_template(
        'payments/buy.html',
        packages=packages,
        active_membership=active_membership,
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
