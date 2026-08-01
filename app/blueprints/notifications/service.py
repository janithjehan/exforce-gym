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
from app.models.installment import Installment, InstallmentPlan, InstallmentPlanStatus, InstallmentStatus
from app.models.member import Member
from app.models.membership import Membership, MembershipStatus
from app.models.notification import (
    Notification, NotificationLog, NotificationAudience,
)
from app.models.user import User, UserRole

EXPIRING_SOON_DAYS = 30
INSTALLMENT_LOOKAHEAD_DAYS = 3  # remind this many days before due, plus anything overdue
INSTALLMENT_REMINDER_COOLDOWN_DAYS = 7  # don't re-remind the same installment more often than this

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


def send_installment_reminders():
    """Notify members whose next installment is due within
    INSTALLMENT_LOOKAHEAD_DAYS or already overdue. Each installment gets its
    own direct notice (amounts/dates differ per member, unlike the shared
    expiry-reminder broadcast) and is skipped if already reminded within the
    last INSTALLMENT_REMINDER_COOLDOWN_DAYS. Returns (notified_count, skipped_count)."""
    today = date.today()
    window = today + timedelta(days=INSTALLMENT_LOOKAHEAD_DAYS)
    cooldown_cutoff = datetime.utcnow() - timedelta(days=INSTALLMENT_REMINDER_COOLDOWN_DAYS)

    candidates = (
        Installment.query
        .join(InstallmentPlan, Installment.plan_id == InstallmentPlan.id)
        .filter(
            InstallmentPlan.status == InstallmentPlanStatus.ACTIVE,
            Installment.status == InstallmentStatus.PENDING,
            Installment.due_date <= window,
        )
        .all()
    )

    notified = 0
    for installment in candidates:
        if installment.last_reminded_at and installment.last_reminded_at >= cooldown_cutoff:
            continue

        plan = installment.plan
        member = plan.member
        if not member or member.is_archived or not member.user or not member.user.is_active:
            continue

        overdue = installment.is_overdue
        notification = Notification(
            title='Installment Payment Overdue' if overdue else 'Installment Payment Due Soon',
            message=(
                f'Installment {installment.sequence_no} of {plan.installment_count} '
                f'(LKR {installment.amount:,.2f}) for your "{plan.package.name}" membership is '
                f'{"overdue" if overdue else "due soon"} '
                f'({installment.due_date.strftime("%d %b %Y")}). '
                'Please submit your bank transfer reference to stay on schedule.'
            ),
            audience=NotificationAudience.SINGLE_MEMBER,
            is_auto=True,
            link_url=f'/payments/installment/{installment.id}/pay',
        )
        db.session.add(notification)
        db.session.flush()
        dispatch_notification(notification, [member.user])
        installment.last_reminded_at = datetime.utcnow()
        notified += 1

    db.session.commit()
    return notified, len(candidates) - notified