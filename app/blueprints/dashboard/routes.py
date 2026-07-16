from datetime import date, timedelta
from flask import render_template, redirect, url_for
from flask_login import login_required, current_user

from app.blueprints.dashboard import dashboard_bp
from app.extensions import db
from app.models.user import User, UserRole
from app.models.member import Member
from app.models.membership import Membership, MembershipStatus
from app.models.payment import Payment
from app.models.attendance import Attendance


@dashboard_bp.route('/')
@login_required
def home():
    if current_user.role == UserRole.ADMIN:
        return redirect(url_for('dashboard.admin'))
    if current_user.role == UserRole.MANAGER:
        return redirect(url_for('dashboard.manager'))
    if current_user.role == UserRole.TRAINER:
        return redirect(url_for('dashboard.trainer'))
    return redirect(url_for('dashboard.member'))


@dashboard_bp.route('/admin')
@login_required
def admin():
    if current_user.role != UserRole.ADMIN:
        return redirect(url_for('dashboard.home'))

    today = date.today()
    stats = {
        'total_users': User.query.filter_by(is_archived=False).count(),
        'active_users': User.query.filter_by(is_active=True, is_archived=False).count(),
        'admins': User.query.filter_by(role=UserRole.ADMIN, is_archived=False).count(),
        'trainers': User.query.filter_by(role=UserRole.TRAINER, is_archived=False).count(),
        'total_members': Member.query.filter_by(is_archived=False).count(),
        'incomplete_profiles': Member.query.filter(
            Member.is_archived == False,
            db.or_(Member.contact_no == '', Member.contact_no == None),
        ).count(),
        'active_memberships': Membership.query.filter(
            Membership.status == MembershipStatus.ACTIVE,
            Membership.end_date >= today,
        ).count(),
        'expiring_soon': Membership.query.filter(
            Membership.status == MembershipStatus.ACTIVE,
            Membership.end_date >= today,
            Membership.end_date <= today + timedelta(days=30),
        ).count(),
        'payments_this_month': Payment.query.filter(
            Payment.payment_date >= date(today.year, today.month, 1),
        ).count(),
        'revenue_this_month': db.session.query(
            db.func.sum(Payment.amount)
        ).filter(
            Payment.payment_date >= date(today.year, today.month, 1),
        ).scalar() or 0,
        'today_checkins': Attendance.query.filter(
            db.func.date(Attendance.check_in) == today
        ).count(),
    }
    recent_members = (
        Member.query
        .join(User, Member.user_id == User.id)
        .filter(Member.is_archived == False)
        .order_by(Member.join_date.desc())
        .limit(5)
        .all()
    )
    return render_template(
        'dashboard/admin.html',
        stats=stats,
        recent_members=recent_members,
        title='Admin Dashboard',
    )


@dashboard_bp.route('/manager')
@login_required
def manager():
    if current_user.role != UserRole.MANAGER:
        return redirect(url_for('dashboard.home'))

    today = date.today()
    stats = {
        'total_members': Member.query.filter_by(is_archived=False).count(),
        'incomplete_profiles': Member.query.filter(
            Member.is_archived == False,
            db.or_(Member.contact_no == '', Member.contact_no == None),
        ).count(),
        'active_memberships': Membership.query.filter(
            Membership.status == MembershipStatus.ACTIVE,
            Membership.end_date >= today,
        ).count(),
        'expiring_soon': Membership.query.filter(
            Membership.status == MembershipStatus.ACTIVE,
            Membership.end_date >= today,
            Membership.end_date <= today + timedelta(days=30),
        ).count(),
        'payments_this_month': Payment.query.filter(
            Payment.payment_date >= date(today.year, today.month, 1),
        ).count(),
        'revenue_this_month': db.session.query(
            db.func.sum(Payment.amount)
        ).filter(
            Payment.payment_date >= date(today.year, today.month, 1),
        ).scalar() or 0,
        'today_checkins': Attendance.query.filter(
            db.func.date(Attendance.check_in) == today
        ).count(),
    }
    recent_members = (
        Member.query
        .join(User, Member.user_id == User.id)
        .filter(Member.is_archived == False)
        .order_by(Member.join_date.desc())
        .limit(5)
        .all()
    )
    return render_template(
        'dashboard/manager.html',
        stats=stats,
        recent_members=recent_members,
        title='Manager Dashboard',
    )


@dashboard_bp.route('/trainer')
@login_required
def trainer():
    if current_user.role != UserRole.TRAINER:
        return redirect(url_for('dashboard.home'))
    trainer_profile = current_user.trainer_profile
    return render_template(
        'dashboard/trainer.html',
        trainer_profile=trainer_profile,
        title='Trainer Dashboard',
    )


@dashboard_bp.route('/member')
@login_required
def member():
    if current_user.role != UserRole.MEMBER:
        return redirect(url_for('dashboard.home'))

    membership = None
    recent_attendance = []
    if current_user.member_profile:
        today = date.today()
        membership = (
            Membership.query
            .filter(
                Membership.member_id == current_user.member_profile.id,
                Membership.status == MembershipStatus.ACTIVE,
                Membership.end_date >= today,
            )
            .order_by(Membership.end_date.desc())
            .first()
        )
        recent_attendance = (
            Attendance.query
            .filter_by(member_id=current_user.member_profile.id)
            .order_by(Attendance.check_in.desc())
            .limit(5)
            .all()
        )

    return render_template(
        'dashboard/member.html',
        membership=membership,
        recent_attendance=recent_attendance,
        title='Member Dashboard',
    )
