from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import current_user, login_required

from app.blueprints.users import users_bp
from app.blueprints.users.forms import UserCreateForm, UserEditForm, AdminResetPasswordForm
from app.extensions import db
from app.models.user import User, UserRole, LoginActivityLog
from app.models.member import Member
from app.models.trainer import Trainer
from app.utils.decorators import admin_required, log_activity

USERS_PER_PAGE = 15


@users_bp.route('/')
@admin_required
def list_users():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    role_filter = request.args.get('role', '')
    status_filter = request.args.get('status', 'all')

    query = User.query

    # Search across name, username, email
    if search:
        like = f'%{search}%'
        query = query.filter(
            db.or_(
                User.username.ilike(like),
                User.email.ilike(like),
                User.first_name.ilike(like),
                User.last_name.ilike(like),
            )
        )

    # Role filter
    if role_filter and role_filter in [r.value for r in UserRole]:
        query = query.filter(User.role == UserRole(role_filter))

    # Status filter
    if status_filter == 'active':
        query = query.filter(User.is_active == True, User.is_archived == False)
    elif status_filter == 'inactive':
        query = query.filter(User.is_active == False, User.is_archived == False)
    elif status_filter == 'archived':
        query = query.filter(User.is_archived == True)
    else:
        # 'all' — exclude archived by default
        query = query.filter(User.is_archived == False)

    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=USERS_PER_PAGE, error_out=False
    )

    return render_template(
        'users/list.html',
        users=users,
        search=search,
        role_filter=role_filter,
        status_filter=status_filter,
        roles=UserRole,
        title='User Management',
    )


@users_bp.route('/create', methods=['GET', 'POST'])
@admin_required
def create_user():
    form = UserCreateForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data.strip(),
            email=form.email.data.strip().lower(),
            first_name=form.first_name.data.strip(),
            last_name=form.last_name.data.strip(),
            phone=form.phone.data.strip() or None,
            role=UserRole(form.role.data),
            is_active=form.is_active.data,
            created_by_id=current_user.id,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()  # get user.id

        # Auto-create a basic Member profile for MEMBER-role users
        if user.role == UserRole.MEMBER:
            member = Member(
                user_id=user.id,
                contact_no=user.phone or '',
                join_date=datetime.utcnow().date(),
                created_by_id=current_user.id,
            )
            db.session.add(member)
        # Auto-create a basic Trainer profile for TRAINER-role users
        elif user.role == UserRole.TRAINER:
            trainer = Trainer(
                user_id=user.id,
                contact_no=user.phone or '',
                created_by_id=current_user.id,
            )
            db.session.add(trainer)

        db.session.commit()
        flash(f'User "{user.username}" created successfully.', 'success')
        return redirect(url_for('users.list_users'))

    return render_template('users/create.html', form=form, title='Create User')


@users_bp.route('/<int:user_id>')
@admin_required
def view_user(user_id):
    user = User.query.get_or_404(user_id)
    recent_logs = (
        LoginActivityLog.query
        .filter_by(user_id=user_id)
        .order_by(LoginActivityLog.timestamp.desc())
        .limit(20)
        .all()
    )
    return render_template('users/view.html', user=user, logs=recent_logs, title=user.full_name)


@users_bp.route('/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_archived:
        flash('Archived users cannot be edited.', 'warning')
        return redirect(url_for('users.view_user', user_id=user_id))

    form = UserEditForm(user_id=user_id, obj=user)
    # Pre-fill role select
    if request.method == 'GET':
        form.role.data = user.role.value

    if form.validate_on_submit():
        # Guard: prevent removing the last admin
        if (
            user.role == UserRole.ADMIN
            and UserRole(form.role.data) != UserRole.ADMIN
            and User.query.filter_by(role=UserRole.ADMIN, is_archived=False).count() <= 1
        ):
            flash('Cannot change role: this is the last admin account.', 'danger')
            return render_template('users/edit.html', form=form, user=user, title='Edit User')

        user.username = form.username.data.strip()
        user.email = form.email.data.strip().lower()
        user.first_name = form.first_name.data.strip()
        user.last_name = form.last_name.data.strip()
        user.phone = form.phone.data.strip() or None
        user.role = UserRole(form.role.data)
        user.is_active = form.is_active.data
        user.updated_by_id = current_user.id
        user.updated_at = datetime.utcnow()

        if form.password.data:
            user.set_password(form.password.data)

        db.session.commit()
        flash(f'User "{user.username}" updated successfully.', 'success')
        return redirect(url_for('users.view_user', user_id=user_id))

    return render_template('users/edit.html', form=form, user=user, title='Edit User')


@users_bp.route('/<int:user_id>/activate', methods=['POST'])
@admin_required
def activate_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_archived:
        flash('Cannot activate an archived user.', 'warning')
        return redirect(url_for('users.view_user', user_id=user_id))

    user.is_active = True
    user.updated_by_id = current_user.id
    user.updated_at = datetime.utcnow()

    log_activity(
        LoginActivityLog.Action.ACCOUNT_ACTIVATED,
        details=f'Activated by admin: {current_user.username}',
        user_id=user_id,
    )
    db.session.commit()
    flash(f'User "{user.username}" has been activated.', 'success')
    return redirect(url_for('users.view_user', user_id=user_id))


@users_bp.route('/<int:user_id>/deactivate', methods=['POST'])
@admin_required
def deactivate_user(user_id):
    user = User.query.get_or_404(user_id)

    # Guard: cannot deactivate yourself
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'danger')
        return redirect(url_for('users.view_user', user_id=user_id))

    # Guard: cannot deactivate the last active admin
    if user.role == UserRole.ADMIN:
        active_admins = User.query.filter_by(
            role=UserRole.ADMIN, is_active=True, is_archived=False
        ).count()
        if active_admins <= 1:
            flash('Cannot deactivate: this is the last active admin account.', 'danger')
            return redirect(url_for('users.view_user', user_id=user_id))

    user.is_active = False
    user.updated_by_id = current_user.id
    user.updated_at = datetime.utcnow()

    log_activity(
        LoginActivityLog.Action.ACCOUNT_DEACTIVATED,
        details=f'Deactivated by admin: {current_user.username}',
        user_id=user_id,
    )
    db.session.commit()
    flash(f'User "{user.username}" has been deactivated.', 'warning')
    return redirect(url_for('users.view_user', user_id=user_id))


@users_bp.route('/<int:user_id>/archive', methods=['POST'])
@admin_required
def archive_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash('You cannot archive your own account.', 'danger')
        return redirect(url_for('users.view_user', user_id=user_id))

    if user.role == UserRole.ADMIN:
        active_admins = User.query.filter_by(
            role=UserRole.ADMIN, is_archived=False
        ).count()
        if active_admins <= 1:
            flash('Cannot archive: this is the last admin account.', 'danger')
            return redirect(url_for('users.view_user', user_id=user_id))

    user.is_archived = True
    user.is_active = False
    user.updated_by_id = current_user.id
    user.updated_at = datetime.utcnow()
    db.session.commit()
    flash(f'User "{user.username}" has been archived.', 'secondary')
    return redirect(url_for('users.list_users'))


@users_bp.route('/<int:user_id>/reset-password', methods=['GET', 'POST'])
@admin_required
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_archived:
        flash('Cannot reset password for an archived user.', 'warning')
        return redirect(url_for('users.view_user', user_id=user_id))

    form = AdminResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.new_password.data)
        user.updated_by_id = current_user.id
        user.updated_at = datetime.utcnow()

        log_activity(
            LoginActivityLog.Action.PASSWORD_CHANGED,
            details=f'Password reset by admin: {current_user.username}',
            user_id=user_id,
        )
        db.session.commit()
        flash(f'Password for "{user.username}" has been reset.', 'success')
        return redirect(url_for('users.view_user', user_id=user_id))

    return render_template(
        'users/reset_password.html', form=form, user=user, title='Reset Password'
    )
