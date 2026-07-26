import os
from datetime import datetime
from flask import Flask, session, redirect, url_for
from flask_login import current_user, logout_user

from config import config
from app.extensions import db, login_manager, bcrypt, csrf


def create_app(config_name=None):
    """
        Application factory that creates and configures the Flask app.
        Initializes extensions, enforces session timeout, registers blueprints,
        and sets up error handlers. Loads config from FLASK_ENV if not provided.
    """
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')

    app = Flask(__name__, template_folder='../templates')
    app.config.from_object(config[config_name])

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)

    # Session timeout enforcement
    @app.before_request
    def enforce_session_timeout():
        if current_user.is_authenticated:
            last_activity = session.get('last_activity')
            if last_activity:
                elapsed = datetime.utcnow() - datetime.fromisoformat(last_activity)
                if elapsed > app.config['PERMANENT_SESSION_LIFETIME']:
                    logout_user()
                    session.clear()
                    from flask import flash
                    flash('Your session has expired. Please log in again.', 'warning')
                    return redirect(url_for('auth.login'))
            session['last_activity'] = datetime.utcnow().isoformat()
            session.permanent = True

    # Register blueprints
    from app.blueprints.auth import auth_bp
    from app.blueprints.users import users_bp
    from app.blueprints.members import members_bp
    from app.blueprints.packages import packages_bp
    from app.blueprints.memberships import memberships_bp
    from app.blueprints.payments import payments_bp
    from app.blueprints.attendance import attendance_bp
    from app.blueprints.trainers import trainers_bp
    from app.blueprints.trainer_requests import trainer_requests_bp
    from app.blueprints.notifications import notifications_bp
    from app.blueprints.workouts import workouts_bp
    from app.blueprints.schedules import schedules_bp
    from app.blueprints.equipment import equipment_bp
    from app.blueprints.supplements import supplements_bp
    from app.blueprints.measurements import measurements_bp
    from app.blueprints.feedback import feedback_bp
    from app.blueprints.payroll import payroll_bp
    from app.blueprints.expenses import expenses_bp
    from app.blueprints.reports import reports_bp
    from app.blueprints.configuration import configuration_bp
    from app.blueprints.dashboard import dashboard_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(users_bp, url_prefix='/users')
    app.register_blueprint(members_bp, url_prefix='/members')
    app.register_blueprint(packages_bp, url_prefix='/packages')
    app.register_blueprint(memberships_bp, url_prefix='/memberships')
    app.register_blueprint(payments_bp, url_prefix='/payments')
    app.register_blueprint(attendance_bp, url_prefix='/attendance')
    app.register_blueprint(trainers_bp, url_prefix='/trainers')
    app.register_blueprint(trainer_requests_bp, url_prefix='/trainer-requests')
    app.register_blueprint(notifications_bp, url_prefix='/notifications')
    app.register_blueprint(workouts_bp, url_prefix='/workouts')
    app.register_blueprint(schedules_bp, url_prefix='/schedules')
    app.register_blueprint(equipment_bp, url_prefix='/equipment')
    app.register_blueprint(supplements_bp, url_prefix='/supplements')
    app.register_blueprint(measurements_bp, url_prefix='/measurements')
    app.register_blueprint(feedback_bp, url_prefix='/feedback')
    app.register_blueprint(payroll_bp, url_prefix='/payroll')
    app.register_blueprint(expenses_bp, url_prefix='/expenses')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(configuration_bp, url_prefix='/configuration')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')

    # Timezone display filter — stored timestamps are naive UTC; render them
    # in the gym's local time (Asia/Colombo, UTC+5:30). Use in templates as
    # {{ some_datetime | localdt }} or {{ some_datetime | localdt('%d %b %Y') }}.
    from app.utils.timezones import to_local

    @app.template_filter('localdt')
    def localdt(dt, fmt='%d %b %Y, %H:%M'):
        local = to_local(dt)
        return local.strftime(fmt) if local else ''

    # Avatar renderer — a user's uploaded photo, or their initials as a fallback.
    # `classes` are applied to both the <img> and the initials <div> so the call
    # site keeps its existing sizing/utility classes (e.g. 'user-avatar user-avatar-lg mx-auto').
    from markupsafe import Markup, escape

    @app.template_global()
    def avatar(user, classes='user-avatar'):
        if user is not None and getattr(user, 'avatar_url', None):
            src = url_for('static', filename=user.avatar_url)
            return Markup(
                f'<img src="{src}" alt="{escape(user.full_name)}" class="avatar-img {escape(classes)}">'
            )
        initials = escape(user.initials) if user is not None else '?'
        return Markup(f'<div class="{escape(classes)}">{initials}</div>')

    # Unread in-app notification badge — available to every authenticated role
    @app.context_processor
    def inject_unread_notifications():
        unread = 0
        if current_user.is_authenticated:
            from app.models.notification import NotificationLog
            unread = NotificationLog.query.filter_by(
                recipient_id=current_user.id,
                is_read=False,
            ).count()
        return {'unread_notifications': unread}

    # Pending trainer-request count for a trainer's sidebar badge
    @app.context_processor
    def inject_trainer_request_counts():
        from app.models.user import UserRole
        count = 0
        if (current_user.is_authenticated
                and current_user.role == UserRole.TRAINER
                and current_user.trainer_profile):
            from app.models.trainer_request import TrainerRequest, TrainerRequestStatus
            count = TrainerRequest.query.filter_by(
                trainer_id=current_user.trainer_profile.id,
                status=TrainerRequestStatus.PENDING,
            ).count()
        return {'trainer_pending_requests': count}

    # Root redirect
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.home'))
        return redirect(url_for('auth.login'))

    # Error handlers
    from app.blueprints.errors import register_error_handlers
    register_error_handlers(app)

    # In-process daily scheduler (membership expiry + expiry reminders).
    # Guarded so Werkzeug's debug reloader (which forks a watcher + child
    # process) only starts it once, in the child that actually serves requests.
    if not app.config.get('TESTING') and (
        os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug
    ):
        from app.scheduler import init_scheduler
        init_scheduler(app)

    return app
