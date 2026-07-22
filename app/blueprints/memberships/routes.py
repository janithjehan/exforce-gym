from datetime import datetime, timedelta
from flask import render_template, redirect, url_for, flash, request
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

    # Members dropdown (non-archived)
    members = (
        Member.query
        .join(User, Member.user_id == User.id)
        .filter(Member.is_archived == False)
        .order_by(User.first_name.asc())
        .all()
    )
    form.member_id.choices = [(m.id, f'{m.full_name} ({m.email})') for m in members]

    # Pre-select member if passed as query param
    preselect_member_id = request.args.get('member_id', type=int)
    if request.method == 'GET' and preselect_member_id:
        form.member_id.data = preselect_member_id

    if form.validate_on_submit():
        member = Member.query.get_or_404(form.member_id.data)
        package = Package.query.get_or_404(form.package_id.data)

        # FR-MSHIP-02: only one active membership at a time
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
                'memberships/create.html', form=form, title='Assign Membership'
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

    return render_template('memberships/create.html', form=form, title='Assign Membership')


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

    # FR-MSHIP-03: extend from current end_date, not today
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

    membership.status = MembershipStatus.CANCELLED
    membership.updated_by_id = current_user.id
    membership.updated_at = datetime.utcnow()
    db.session.commit()

    flash(f'Membership #{membership.id} has been cancelled.', 'secondary')
    return redirect(url_for('memberships.list_memberships'))
