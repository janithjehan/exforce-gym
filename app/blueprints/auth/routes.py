from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user

from app.blueprints.auth import auth_bp
from app.blueprints.auth.forms import LoginForm, RegisterForm, ChangePasswordForm
from app.extensions import db
from app.models.user import User, UserRole, LoginActivityLog
from app.models.member import Member
from app.utils.decorators import log_activity


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))

    form = LoginForm()
    if form.validate_on_submit():
        # Accept username OR email
        identifier = form.username.data.strip()
        user = (
            User.query.filter_by(username=identifier).first()
            or User.query.filter_by(email=identifier).first()
        )

        if user and user.check_password(form.password.data):
            if user.is_archived:
                flash('This account has been removed. Please contact the gym.', 'danger')
                return render_template('auth/login.html', form=form)
            if not user.is_active:
                flash('Your account is inactive. Please contact the gym administrator.', 'danger')
                _log_failed(user)
                return render_template('auth/login.html', form=form)

            login_user(user, remember=form.remember_me.data)
            session['last_activity'] = datetime.utcnow().isoformat()
            session.permanent = True

            # Update last login
            user.last_login = datetime.utcnow()
            log_activity(LoginActivityLog.Action.LOGIN)
            db.session.commit()

            flash(f'Welcome back, {user.first_name}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard.home'))
        else:
            if user:
                _log_failed(user)
                db.session.commit()
            flash('Invalid username/email or password.', 'danger')

    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    log_activity(LoginActivityLog.Action.LOGOUT)
    db.session.commit()
    logout_user()
    session.clear()
    flash('You have been signed out successfully.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))

    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data.strip(),
            email=form.email.data.strip().lower(),
            first_name=form.first_name.data.strip(),
            last_name=form.last_name.data.strip(),
            phone=form.phone.data.strip() or None,
            role=UserRole.MEMBER,
            is_active=True,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()  # get user.id

        # Auto-create a basic Member profile for self-registered users
        member = Member(
            user_id=user.id,
            contact_no=form.phone.data.strip() if form.phone.data else '',
            join_date=datetime.utcnow().date(),
        )
        db.session.add(member)
        db.session.commit()
        flash('Account created successfully! You can now sign in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', form=form)


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'danger')
            return render_template('auth/change_password.html', form=form)

        current_user.set_password(form.new_password.data)
        current_user.updated_at = datetime.utcnow()
        log_activity(LoginActivityLog.Action.PASSWORD_CHANGED)
        db.session.commit()
        flash('Password updated successfully.', 'success')
        return redirect(url_for('dashboard.home'))

    return render_template('auth/change_password.html', form=form)


def _log_failed(user):
    log_activity(LoginActivityLog.Action.FAILED_LOGIN, user_id=user.id)
