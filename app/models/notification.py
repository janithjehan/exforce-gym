import enum
from datetime import datetime
from app.extensions import db


class NotificationAudience(enum.Enum):
    ALL_ACTIVE = 'all_active'
    PACKAGE = 'package'
    EXPIRING_SOON = 'expiring_soon'

    @property
    def label(self):
        return {
            'all_active': 'All Active Members',
            'package': 'By Package',
            'expiring_soon': 'Expiring Within 30 Days',
        }[self.value]


class Notification(db.Model):
    """Internal (in-app) announcement sent to members by Admin/Manager,
    e.g. holiday notices — plus automated expiry reminders."""
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)

    audience = db.Column(
        db.Enum(NotificationAudience), nullable=False,
        default=NotificationAudience.ALL_ACTIVE,
    )
    package_id = db.Column(db.Integer, db.ForeignKey('packages.id'), nullable=True)

    is_auto = db.Column(db.Boolean, nullable=False, default=False)  # FR-NOT-03 scheduled reminders

    recipient_count = db.Column(db.Integer, nullable=False, default=0)
    sent_at = db.Column(db.DateTime, nullable=True)

    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    package = db.relationship('Package', foreign_keys=[package_id])
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    logs = db.relationship(
        'NotificationLog', backref='notification', lazy='dynamic',
        order_by='NotificationLog.created_at.desc()',
    )

    @property
    def audience_label(self):
        if self.audience == NotificationAudience.PACKAGE and self.package:
            return f'Package: {self.package.name}'
        return self.audience.label

    def __repr__(self):
        return f'<Notification id={self.id} "{self.title}" to={self.audience.value}>'


class NotificationLog(db.Model):
    """Per-recipient in-app delivery record with read tracking."""
    __tablename__ = 'notification_logs'

    id = db.Column(db.Integer, primary_key=True)
    notification_id = db.Column(
        db.Integer, db.ForeignKey('notifications.id'), nullable=False
    )
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)

    is_read = db.Column(db.Boolean, nullable=False, default=False)
    read_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    member = db.relationship(
        'Member', foreign_keys=[member_id],
        backref=db.backref('notification_logs', lazy='dynamic'),
    )

    def __repr__(self):
        return f'<NotificationLog n={self.notification_id} m={self.member_id} read={self.is_read}>'