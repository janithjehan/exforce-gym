from datetime import datetime, date
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import current_user, login_required

from app.blueprints.notifications import notifications_bp
from app.blueprints.notifications.forms import NotificationCreateForm
from app.blueprints.notifications.service import resolve_audience, dispatch_notification
from app.extensions import db
from app.models.notification import (
    Notification, NotificationLog, NotificationAudience,
)
from app.models.package import Package
from app.models.user import UserRole
from app.utils.decorators import admin_or_manager_required

NOTIFICATIONS_PER_PAGE = 15
LOGS_PER_PAGE = 30
MY_NOTIFICATIONS_PER_PAGE = 10


@notifications_bp.route('/')
@admin_or_manager_required
def list_notifications():
    page = request.args.get('page', 1, type=int)

    notifications = (
        Notification.query
        .order_by(Notification.created_at.desc())
        .paginate(page=page, per_page=NOTIFICATIONS_PER_PAGE, error_out=False)
    )

    today = date.today()
    stats = {
        'total': Notification.query.count(),
        'this_month': Notification.query.filter(
            Notification.created_at >= datetime(today.year, today.month, 1),
        ).count(),
        'members_reached': db.session.query(
            db.func.coalesce(db.func.sum(Notification.recipient_count), 0)
        ).scalar(),
        'auto_reminders': Notification.query.filter_by(is_auto=True).count(),
    }

    return render_template(
        'notifications/list.html',
        notifications=notifications,
        stats=stats,
        title='Notifications',
    )


@notifications_bp.route('/create', methods=['GET', 'POST'])
@admin_or_manager_required
def create_notification():
    form = NotificationCreateForm()

    packages = (
        Package.query
        .filter_by(is_active=True, is_archived=False)
        .order_by(Package.name.asc())
        .all()
    )
    form.package_id.choices = [(0, '— Select Package —')] + [
        (p.id, f'{p.name} ({p.duration_label})') for p in packages
    ]

    if form.validate_on_submit():
        audience = NotificationAudience(form.audience.data)
        package_id = form.package_id.data or 0

        if audience == NotificationAudience.PACKAGE and not package_id:
            flash('Please select a package for a package-based audience.', 'danger')
            return render_template(
                'notifications/create.html', form=form, title='Send Notification',
            )
        if audience != NotificationAudience.PACKAGE:
            package_id = None

        members = resolve_audience(audience, package_id)
        if not members:
            flash('No active members match the selected audience. Nothing was sent.', 'warning')
            return render_template(
                'notifications/create.html', form=form, title='Send Notification',
            )

        notification = Notification(
            title=form.title.data.strip(),
            message=form.message.data.strip(),
            audience=audience,
            package_id=package_id,
            created_by_id=current_user.id,
        )
        db.session.add(notification)
        db.session.flush()

        dispatch_notification(notification, members)
        db.session.commit()

        flash(f'Notification sent to {len(members)} member(s).', 'success')
        return redirect(url_for('notifications.view_notification',
                                notification_id=notification.id))

    return render_template(
        'notifications/create.html',
        form=form,
        title='Send Notification',
    )


@notifications_bp.route('/<int:notification_id>')
@admin_or_manager_required
def view_notification(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    page = request.args.get('page', 1, type=int)
    logs = (
        NotificationLog.query
        .filter_by(notification_id=notification.id)
        .order_by(NotificationLog.id.asc())
        .paginate(page=page, per_page=LOGS_PER_PAGE, error_out=False)
    )
    return render_template(
        'notifications/view.html',
        notification=notification,
        logs=logs,
        title=f'Notification #{notification.id}',
    )


@notifications_bp.route('/my-notifications')
@login_required
def my_notifications():
    """Member-facing in-app inbox. Viewing marks everything as read."""
    if current_user.role != UserRole.MEMBER:
        abort(403)
    if not current_user.member_profile:
        flash('Member profile not found. Please contact staff.', 'danger')
        return redirect(url_for('dashboard.home'))

    member_id = current_user.member_profile.id
    page = request.args.get('page', 1, type=int)

    logs = (
        NotificationLog.query
        .filter_by(member_id=member_id)
        .join(Notification, NotificationLog.notification_id == Notification.id)
        .order_by(NotificationLog.created_at.desc())
        .paginate(page=page, per_page=MY_NOTIFICATIONS_PER_PAGE, error_out=False)
    )

    unread_ids = [log.id for log in logs.items if not log.is_read]
    if unread_ids:
        NotificationLog.query.filter(NotificationLog.id.in_(unread_ids)).update(
            {'is_read': True, 'read_at': datetime.utcnow()},
            synchronize_session=False,
        )
        db.session.commit()

    return render_template(
        'notifications/my.html',
        logs=logs,
        unread_ids=unread_ids,
        title='My Notifications',
    )