from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, login_required, current_user

from app.blueprints.auth import auth_bp
from app.blueprints.auth.forms import (LoginForm, RegisterForm, ChangePasswordForm, ForgotPasswordForm, ResetPasswordForm,)
from app.extensions import db
from app.models.user import User, UserRole, LoginActivityLog
from app.models.member import Member
from app.utils.decorators import log_activity
from app.utils.mailer import send_email
from app.utils.tokens import generate_reset_token, verify_reset_token


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

            login_user(user)
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
    session.clear()
    logout_user()
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
            role=UserRole.MEMBER,
            is_active=True,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()  # get user.id

        # Auto-create a basic Member profile for self-registered users.
        # Mobile number and NIC (with DOB/gender decoded from it) are filled
        # in later via Edit My Profile — quick signup first, details after.
        member = Member(
            user_id=user.id,
            contact_no='',
            join_date=datetime.utcnow().date(),
        )
        db.session.add(member)
        db.session.commit()
        flash('Account created successfully! Add your mobile number and NIC from "Edit My Profile" after signing in.', 'success')
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


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()

        if user and user.is_active and not user.is_archived:
            token = generate_reset_token(user)
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            gym_name = current_app.config.get('GYM_NAME', 'Exforce Gym')
            max_age_minutes = current_app.config.get('PASSWORD_RESET_MAX_AGE', 3600) // 60
            body = (
                f"Hi {user.first_name},\n\n"
                f"We received a request to reset your {gym_name} password.\n\n"
                f"Reset it here (valid for {max_age_minutes} minutes):\n{reset_url}\n\n"
                "If you didn't request this, you can safely ignore this email.\n"
            )
            send_email(user.email, f'{gym_name} — Password Reset', body)

        # Same message whether or not the email matched — avoids leaking
        # which addresses have accounts.
        flash('If that email is registered, a password reset link has been sent to it.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html', form=form)


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))

    user = verify_reset_token(token)
    if not user:
        flash('That password reset link is invalid or has expired. Please request a new one.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.new_password.data)
        user.updated_at = datetime.utcnow()
        log_activity(LoginActivityLog.Action.PASSWORD_CHANGED, details='Reset via forgot-password link', user_id=user.id)
        db.session.commit()
        flash('Your password has been reset. You can now sign in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', form=form)


def _log_failed(user):
    log_activity(LoginActivityLog.Action.FAILED_LOGIN, user_id=user.id)
