from functools import wraps
from flask import abort, redirect, url_for, flash, request
from flask_login import current_user

from app.models.user import UserRole


def roles_required(*roles):
    """Allow access only to users whose role is in `roles`."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


def admin_required(f):
    """Restrict endpoint to Admin role only."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        if current_user.role != UserRole.ADMIN:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def trainer_required(f):
    """Restrict endpoint to Trainer role only."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        if current_user.role != UserRole.TRAINER:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def admin_or_trainer_required(f):
    """Restrict endpoint to Admin or Trainer roles."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        if current_user.role not in (UserRole.ADMIN, UserRole.TRAINER):
            abort(403)
        return f(*args, **kwargs)
    return decorated


def admin_or_manager_required(f):
    """Restrict endpoint to Admin or Manager roles."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        if current_user.role not in (UserRole.ADMIN, UserRole.MANAGER):
            abort(403)
        return f(*args, **kwargs)
    return decorated


def admin_manager_or_trainer_required(f):
    """Restrict endpoint to Admin, Manager, or Trainer roles."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        if current_user.role not in (UserRole.ADMIN, UserRole.MANAGER, UserRole.TRAINER):
            abort(403)
        return f(*args, **kwargs)
    return decorated


def log_activity(action, details=None, user_id=None):
    """Write a LoginActivityLog entry. Uses current_user when user_id is not given."""
    from flask import request as _request
    from app.models.user import LoginActivityLog
    from app.extensions import db

    log = LoginActivityLog(
        user_id=user_id if user_id is not None else current_user.id,
        action=action,
        ip_address=_request.remote_addr,
        user_agent=_request.user_agent.string[:256],
        details=details,
    )
    db.session.add(log)
