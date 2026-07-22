import enum
from datetime import datetime
from flask_login import UserMixin
from app.extensions import db, bcrypt


class UserRole(enum.Enum):
    ADMIN = 'admin'
    MANAGER = 'manager'
    TRAINER = 'trainer'
    MEMBER = 'member'

    @property
    def label(self):
        return self.value.capitalize()


class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)

    # Profile
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    # Required (form-level) for MANAGER accounts; optional for other roles
    nic_no = db.Column(db.String(20), nullable=True)

    # Role & status
    role = db.Column(db.Enum(UserRole), nullable=False, default=UserRole.MEMBER)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_archived = db.Column(db.Boolean, nullable=False, default=False)

    # Timestamps
    last_login = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Audit — who created/updated this record
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    created_by = db.relationship(
        'User', foreign_keys=[created_by_id], remote_side='User.id',
        backref=db.backref('created_users', lazy='dynamic')
    )
    updated_by = db.relationship(
        'User', foreign_keys=[updated_by_id], remote_side='User.id',
        backref=db.backref('updated_users', lazy='dynamic')
    )

    # Login activity logs
    login_logs = db.relationship(
        'LoginActivityLog', foreign_keys='LoginActivityLog.user_id',
        backref='user', lazy='dynamic', cascade='all, delete-orphan'
    )

    # ------------------------------------------------------------------ #
    #  Password helpers                                                    #
    # ------------------------------------------------------------------ #

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    # ------------------------------------------------------------------ #
    #  Flask-Login required properties                                    #
    # ------------------------------------------------------------------ #

    @property
    def is_active_account(self):
        return self.is_active and not self.is_archived

    def get_id(self):
        return str(self.id)

    # ------------------------------------------------------------------ #
    #  Convenience helpers                                                 #
    # ------------------------------------------------------------------ #

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    @property
    def is_admin(self):
        return self.role == UserRole.ADMIN

    @property
    def is_manager(self):
        return self.role == UserRole.MANAGER

    @property
    def is_trainer(self):
        return self.role == UserRole.TRAINER

    @property
    def is_member(self):
        return self.role == UserRole.MEMBER

    @property
    def status_label(self):
        if self.is_archived:
            return 'Archived'
        return 'Active' if self.is_active else 'Inactive'

    @property
    def status_badge_class(self):
        if self.is_archived:
            return 'secondary'
        return 'success' if self.is_active else 'danger'

    def __repr__(self):
        return f'<User {self.username} ({self.role.value})>'


class LoginActivityLog(db.Model):
    __tablename__ = 'login_activity_logs'

    class Action(enum.Enum):
        LOGIN = 'login'
        LOGOUT = 'logout'
        FAILED_LOGIN = 'failed_login'
        PASSWORD_CHANGED = 'password_changed'
        ACCOUNT_ACTIVATED = 'account_activated'
        ACCOUNT_DEACTIVATED = 'account_deactivated'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.Enum(Action), nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(256), nullable=True)
    details = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<LoginActivityLog user={self.user_id} action={self.action.value}>'
