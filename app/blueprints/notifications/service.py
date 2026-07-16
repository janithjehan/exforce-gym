"""Audience resolution + in-app delivery dispatch for the Notifications module.

Shared by the web routes and the `flask send-expiry-reminders` CLI job.
Notifications are internal (in-app) announcements only — SMS is reserved
for payment confirmations (see app/blueprints/payments/sms.py).
"""
from datetime import datetime, date, timedelta

from app.extensions import db
from app.models.member import Member
from app.models.membership import Membership, MembershipStatus
from app.models.notification import (
    Notification, NotificationLog, NotificationAudience,
)
from app.models.user import User

EXPIRING_SOON_DAYS = 30


def resolve_audience(audience, package_id=None):
    """FR-NOT-01/02: return active members matching the audience filter.
    Active member = not archived, account active, has an ACTIVE membership
    with end_date >= today."""
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
    return query.distinct().all()


def dispatch_notification(notification, members):
    """Create an in-app delivery log per recipient. Caller commits."""
    for member in members:
        db.session.add(NotificationLog(
            notification_id=notification.id,
            member_id=member.id,
        ))

    notification.recipient_count = len(members)
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
            db.session.query(NotificationLog.member_id)
            .join(Notification, NotificationLog.notification_id == Notification.id)
            .filter(
                Notification.is_auto == True,
                NotificationLog.created_at >= cutoff,
            )
            .distinct()
            .all()
        )
    }
    to_notify = [m for m in expiring if m.id not in already_reminded]
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