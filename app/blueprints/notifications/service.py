"""Audience resolution + in-app delivery dispatch for the Notifications module.

Shared by the web routes and the `flask send-expiry-reminders` CLI job.
Notifications are internal (in-app) announcements only — SMS is reserved
for payment confirmations (see app/blueprints/payments/sms.py).

`resolve_audience()` always returns a list of `User` objects (recipients),
regardless of whether the audience is member-based or staff-based —
`dispatch_notification()` and `send_expiry_reminders()` work uniformly
against `User.id` as a result.
"""
from datetime import datetime, date, timedelta

from app.extensions import db
from app.models.member import Member
from app.models.membership import Membership, MembershipStatus
from app.models.notification import (
    Notification, NotificationLog, NotificationAudience,
)
from app.models.user import User, UserRole

EXPIRING_SOON_DAYS = 30

STAFF_ROLES_BY_AUDIENCE = {
    NotificationAudience.ALL_ADMINS: [UserRole.ADMIN],
    NotificationAudience.ALL_MANAGERS: [UserRole.MANAGER],
    NotificationAudience.ALL_TRAINERS: [UserRole.TRAINER],
    NotificationAudience.ALL_STAFF: [UserRole.ADMIN, UserRole.MANAGER, UserRole.TRAINER],
    NotificationAudience.ADMINS_MANAGERS: [UserRole.ADMIN, UserRole.MANAGER],
}


def resolve_audience(audience, package_id=None):
    """Return the list of recipient Users matching the audience filter.

    Member audiences (FR-NOT-01/02): active member = not archived, account
    active, has an ACTIVE membership with end_date >= today.
    Staff audiences: active, non-archived Users with a matching role.
    """
    if audience in STAFF_ROLES_BY_AUDIENCE:
        return User.query.filter(
            User.role.in_(STAFF_ROLES_BY_AUDIENCE[audience]),
            User.is_active == True,
            User.is_archived == False,
        ).all()

    today = date.today()
    query = (
        Member.query
        .join(User, Member.user_id == User.id)
        .join(Membership, Membership.member_id == Member.id)
        .filter(
            Member.is_archived == False,
            User.is_active == True,
            Membership.status == MembershipStatus.ACTIVE,
            Membership.end_date >= today,
        )
    )
    if audience == NotificationAudience.PACKAGE and package_id:
        query = query.filter(Membership.package_id == package_id)
    if audience == NotificationAudience.EXPIRING_SOON:
        query = query.filter(
            Membership.end_date <= today + timedelta(days=EXPIRING_SOON_DAYS)
        )
    members = query.distinct().all()
    return [m.user for m in members]


def dispatch_notification(notification, users):
    """Create an in-app delivery log per recipient User. Caller commits."""
    for user in users:
        db.session.add(NotificationLog(
            notification_id=notification.id,
            recipient_id=user.id,
        ))

    notification.recipient_count = len(users)
    notification.sent_at = datetime.utcnow()


def send_expiry_reminders():
    """FR-NOT-03: scheduled job — remind members whose membership expires
    within 30 days. Members already reminded in the last 30 days are skipped.
    Returns (notified_count, skipped_count)."""
    expiring = resolve_audience(NotificationAudience.EXPIRING_SOON)
    if not expiring:
        return 0, 0

    cutoff = datetime.utcnow() - timedelta(days=EXPIRING_SOON_DAYS)
    already_reminded = {
        row[0]
        for row in (
            db.session.query(NotificationLog.recipient_id)
            .join(Notification, NotificationLog.notification_id == Notification.id)
            .filter(
                Notification.is_auto == True,
                NotificationLog.created_at >= cutoff,
            )
            .distinct()
            .all()
        )
    }
    to_notify = [u for u in expiring if u.id not in already_reminded]
    if not to_notify:
        return 0, len(expiring)

    notification = Notification(
        title='Membership Expiry Reminder',
        message=(
            'Your Exforce Gym membership expires within the next 30 days. '
            'Please renew your plan to keep uninterrupted access.'
        ),
        audience=NotificationAudience.EXPIRING_SOON,
        is_auto=True,
    )
    db.session.add(notification)
    db.session.flush()

    dispatch_notification(notification, to_notify)
    db.session.commit()
    return len(to_notify), len(expiring) - len(to_notify)