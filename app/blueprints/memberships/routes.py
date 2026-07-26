from datetime import datetime, timedelta, date
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import current_user, login_required

from app.blueprints.memberships import memberships_bp
from app.blueprints.memberships.forms import MembershipCreateForm
from app.extensions import db
from app.models.member import Member
from app.models.membership import Membership, MembershipStatus
from app.models.package import Package
from app.models.user import User, UserRole
from app.utils.decorators import admin_required, admin_or_manager_required
from app.utils.search import parse_search_terms, multi_term_filter

MEMBERSHIPS_PER_PAGE = 20


@memberships_bp.route('/')
@admin_or_manager_required
def list_memberships():
    Membership.expire_passed()

    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'active')
    search = request.args.get('search', '').strip()

    query = (
        Membership.query
        .join(Member, Membership.member_id == Member.id)
        .join(User, Member.user_id == User.id)
    )

    terms = parse_search_terms(search)
    if terms:
        query = query.filter(multi_term_filter(terms, [
            User.first_name, User.last_name, User.email,
        ]))

    if status_filter == 'active':
        from datetime import date
        query = query.filter(
            Membership.status == MembershipStatus.ACTIVE,
            Membership.end_date >= date.today(),
        )
    elif status_filter == 'expired':
        query = query.filter(Membership.status == MembershipStatus.EXPIRED)
    elif status_filter == 'cancelled':
        query = query.filter(Membership.status == MembershipStatus.CANCELLED)
    elif status_filter == 'pending':
        query = query.filter(Membership.status == MembershipStatus.PENDING)

    memberships = query.order_by(Membership.start_date.desc()).paginate(
        page=page, per_page=MEMBERSHIPS_PER_PAGE, error_out=False
    )

    from datetime import date
    today = date.today()
    stats = {
        'active': Membership.query.filter(
            Membership.status == MembershipStatus.ACTIVE,
            Membership.end_date >= today,
        ).count(),
        'expiring_soon': Membership.query.filter(
            Membership.status == MembershipStatus.ACTIVE,
            Membership.end_date >= today,
            Membership.end_date <= today + timedelta(days=30),
        ).count(),
        'expired': Membership.query.filter_by(status=MembershipStatus.EXPIRED).count(),
        'pending': Membership.query.filter_by(status=MembershipStatus.PENDING).count(),
    }

    return render_template(
        'memberships/list.html',
        memberships=memberships,
        status_filter=status_filter,
        search=search,
        stats=stats,
        title='Memberships',
    )


@memberships_bp.route('/create', methods=['GET', 'POST'])
@admin_or_manager_required
def create_membership():
    form = MembershipCreateForm()

    # Only active packages available — FR-PKG-03
    active_packages = Package.query.filter_by(is_active=True, is_archived=False).order_by(
        Package.duration_months.asc()
    ).all()
    form.package_id.choices = [
        (p.id, f'{p.name} — {p.duration_label} (LKR {p.price:,.2f})')
        for p in active_packages
    ]

    # Members (non-archived) — single query, reused for the datalist options and
    # for resolving the typed label back to an id.
    members = (
        Member.query
        .join(User, Member.user_id == User.id)
        .filter(Member.is_archived == False)
        .order_by(User.first_name.asc())
        .all()
    )
    member_labels = {f'{m.full_name} ({m.email})': m.id for m in members}
    form.member_id.choices = [(mid, label) for label, mid in member_labels.items()]

    # The member field is a native datalist combobox (type-to-search, no JS). It
    # submits the typed label, so map it back to the id the SelectField expects.
    member_label = ''
    if request.method == 'POST':
        member_label = request.form.get('member_label', '').strip()
        form.member_id.data = member_labels.get(member_label)
    else:
        preselect_member_id = request.args.get('member_id', type=int)
        if preselect_member_id:
            form.member_id.data = preselect_member_id
            member_label = next(
                (lbl for lbl, mid in member_labels.items() if mid == preselect_member_id), ''
            )

    if form.validate_on_submit():
        member = Member.query.get_or_404(form.member_id.data)
        package = Package.query.get_or_404(form.package_id.data)

        # only one active membership at a time
        from datetime import date
        existing = Membership.query.filter(
            Membership.member_id == member.id,
            Membership.status == MembershipStatus.ACTIVE,
            Membership.end_date >= date.today(),
        ).first()
        if existing:
            flash(
                f'{member.full_name} already has an active membership '
                f'(expires {existing.end_date.strftime("%d %b %Y")}). '
                'Use Renew to extend it.',
                'warning',
            )
            return render_template(
                'memberships/create.html', form=form, members=members,
                member_label=member_label, title='Assign Membership',
            )

        end_date = Membership.calculate_end_date(form.start_date.data, package.duration_months)

        membership = Membership(
            member_id=member.id,
            package_id=package.id,
            start_date=form.start_date.data,
            end_date=end_date,
            status=MembershipStatus.ACTIVE,
            notes=form.notes.data.strip() or None,
            created_by_id=current_user.id,
        )
        db.session.add(membership)
        db.session.commit()

        flash(
            f'Membership assigned to {member.full_name}. '
            f'Valid until {end_date.strftime("%d %b %Y")}.',
            'success',
        )
        return redirect(url_for('memberships.view_membership', membership_id=membership.id))

    return render_template('memberships/create.html', form=form, members=members,
                           member_label=member_label, title='Assign Membership')


@memberships_bp.route('/my-memberships')
@login_required
def my_memberships():
    """Member-facing self-service list of own memberships (current + history)."""
    if current_user.role != UserRole.MEMBER:
        return redirect(url_for('dashboard.home'))
    if not current_user.member_profile:
        abort(403)

    Membership.expire_passed()  # keep statuses current before displaying

    member = current_user.member_profile
    page = request.args.get('page', 1, type=int)
    memberships = member.memberships.paginate(page=page, per_page=10, error_out=False)

    today = date.today()
    current = (
        Membership.query
        .filter(
            Membership.member_id == member.id,
            Membership.status == MembershipStatus.ACTIVE,
            Membership.end_date >= today,
        )
        .order_by(Membership.end_date.desc())
        .first()
    )
    pending = (
        Membership.query
        .filter(
            Membership.member_id == member.id,
            Membership.status == MembershipStatus.PENDING,
        )
        .order_by(Membership.created_at.desc())
        .first()
    )

    return render_template(
        'memberships/my_memberships.html',
        memberships=memberships,
        current=current,
        pending=pending,
        title='My Membership',
    )


@memberships_bp.route('/<int:membership_id>')
@login_required
def view_membership(membership_id):
    membership = Membership.query.get_or_404(membership_id)

    # Members can only view their own
    if current_user.role == UserRole.MEMBER:
        if (not current_user.member_profile
                or current_user.member_profile.id != membership.member_id):
            from flask import abort
            abort(403)

    return render_template(
        'memberships/view.html', membership=membership, title='Membership Details'
    )


@memberships_bp.route('/<int:membership_id>/renew', methods=['POST'])
@admin_or_manager_required
def renew_membership(membership_id):
    membership = Membership.query.get_or_404(membership_id)

    if membership.status == MembershipStatus.CANCELLED:
        flash('Cancelled memberships cannot be renewed.', 'warning')
        return redirect(url_for('memberships.view_membership', membership_id=membership_id))

    if membership.status == MembershipStatus.PENDING:
        flash('This membership is awaiting bank transfer verification and cannot be renewed yet.', 'warning')
        return redirect(url_for('memberships.view_membership', membership_id=membership_id))

    # Extend from current end_date, not today
    from datetime import date
    new_start = membership.end_date + timedelta(days=1)
    new_end = Membership.calculate_end_date(new_start, membership.package.duration_months)

    renewal = Membership(
        member_id=membership.member_id,
        package_id=membership.package_id,
        start_date=new_start,
        end_date=new_end,
        status=MembershipStatus.ACTIVE,
        notes=f'Renewal of membership #{membership.id}',
        created_by_id=current_user.id,
    )
    db.session.add(renewal)
    db.session.commit()

    flash(
        f'Membership renewed. New period: {new_start.strftime("%d %b %Y")} '
        f'to {new_end.strftime("%d %b %Y")}.',
        'success',
    )
    return redirect(url_for('memberships.view_membership', membership_id=renewal.id))


@memberships_bp.route('/<int:membership_id>/cancel', methods=['POST'])
@admin_or_manager_required
def cancel_membership(membership_id):
    membership = Membership.query.get_or_404(membership_id)

    if membership.status == MembershipStatus.CANCELLED:
        flash('Membership is already cancelled.', 'warning')
        return redirect(url_for('memberships.view_membership', membership_id=membership_id))

    if membership.status == MembershipStatus.PENDING:
        payment = membership.payments.first()
        flash(
            'This membership is awaiting bank transfer verification. '
            'Reject the payment instead to cancel it.',
            'warning',
        )
        if payment:
            return redirect(url_for('payments.view_payment', payment_id=payment.id))
        return redirect(url_for('memberships.view_membership', membership_id=membership_id))

    membership.status = MembershipStatus.CANCELLED
    membership.updated_by_id = current_user.id
    membership.updated_at = datetime.utcnow()
    db.session.commit()

    flash(f'Membership #{membership.id} has been cancelled.', 'secondary')
    return redirect(url_for('memberships.list_memberships'))
