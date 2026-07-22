from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import current_user, login_required

from app.blueprints.trainers import trainers_bp
from app.blueprints.trainers.forms import TrainerCreateForm, TrainerEditForm, TrainerSelfEditForm
from app.extensions import db
from app.models.trainer import Trainer
from app.models.user import User, UserRole
from app.utils.decorators import admin_required, admin_or_manager_required
from app.utils.search import parse_search_terms, multi_term_filter
from app.utils.validators import clean_nic

TRAINERS_PER_PAGE = 15


@trainers_bp.route('/')
@admin_or_manager_required
def list_trainers():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', 'active')

    query = (
        Trainer.query
        .join(User, Trainer.user_id == User.id)
    )

    terms = parse_search_terms(search)
    if terms:
        query = query.filter(multi_term_filter(terms, [
            User.first_name, User.last_name, User.email, Trainer.specialization,
        ]))

    if status_filter == 'archived':
        query = query.filter(Trainer.is_archived == True)  # noqa: E712
    else:
        query = query.filter(Trainer.is_archived == False)  # noqa: E712

    trainers = query.order_by(User.first_name.asc()).paginate(
        page=page, per_page=TRAINERS_PER_PAGE, error_out=False
    )

    stats = {
        'total': Trainer.query.filter_by(is_archived=False).count(),
        'archived': Trainer.query.filter_by(is_archived=True).count(),
    }

    return render_template(
        'trainers/list.html',
        trainers=trainers,
        search=search,
        status_filter=status_filter,
        stats=stats,
        title='Trainers',
    )


@trainers_bp.route('/create', methods=['GET', 'POST'])
@admin_required
def create_trainer():
    form = TrainerCreateForm()

    if form.validate_on_submit():
        user = User(
            username=form.username.data.strip(),
            email=form.email.data.strip().lower(),
            first_name=form.first_name.data.strip(),
            last_name=form.last_name.data.strip(),
            phone=form.phone.data.strip() or form.contact_no.data.strip(),
            nic_no=clean_nic(form.nic_no.data),
            role=UserRole.TRAINER,
            is_active=True,
            created_by_id=current_user.id,
        )
        user.set_password(clean_nic(form.nic_no.data))
        db.session.add(user)
        db.session.flush()

        trainer = Trainer(
            user_id=user.id,
            specialization=form.specialization.data.strip() or None,
            bio=form.bio.data.strip() or None,
            experience_years=form.experience_years.data,
            certifications=form.certifications.data.strip() or None,
            contact_no=form.contact_no.data.strip(),
            created_by_id=current_user.id,
        )
        db.session.add(trainer)
        db.session.commit()

        flash(f'Trainer "{user.full_name}" created successfully. Their initial password is their NIC number.', 'success')
        return redirect(url_for('trainers.view_trainer', trainer_id=trainer.id))

    return render_template('trainers/create.html', form=form, title='Add Trainer')


@trainers_bp.route('/<int:trainer_id>')
@login_required
def view_trainer(trainer_id):
    trainer = Trainer.query.get_or_404(trainer_id)

    if current_user.role not in (UserRole.ADMIN, UserRole.MANAGER):
        if current_user.role == UserRole.TRAINER:
            if not current_user.trainer_profile or current_user.trainer_profile.id != trainer_id:
                abort(403)
        else:
            abort(403)

    return render_template(
        'trainers/view.html',
        trainer=trainer,
        title=trainer.full_name,
    )


@trainers_bp.route('/<int:trainer_id>/edit', methods=['GET', 'POST'])
@admin_or_manager_required
def edit_trainer(trainer_id):
    trainer = Trainer.query.get_or_404(trainer_id)
    if trainer.is_archived:
        flash('Archived trainer profiles cannot be edited.', 'warning')
        return redirect(url_for('trainers.view_trainer', trainer_id=trainer_id))

    form = TrainerEditForm(user_id=trainer.user_id, obj=trainer)

    if request.method == 'GET':
        form.first_name.data = trainer.user.first_name
        form.last_name.data = trainer.user.last_name
        form.phone.data = trainer.user.phone
        form.nic_no.data = trainer.user.nic_no

    if form.validate_on_submit():
        trainer.user.first_name = form.first_name.data.strip()
        trainer.user.last_name = form.last_name.data.strip()
        trainer.user.phone = form.phone.data.strip() or (form.contact_no.data or '').strip() or None
        trainer.user.nic_no = clean_nic(form.nic_no.data)
        trainer.user.updated_by_id = current_user.id
        trainer.user.updated_at = datetime.utcnow()

        trainer.specialization = form.specialization.data.strip() or None
        trainer.bio = form.bio.data.strip() or None
        trainer.experience_years = form.experience_years.data
        trainer.certifications = form.certifications.data.strip() or None
        trainer.contact_no = form.contact_no.data.strip() if form.contact_no.data else ''
        trainer.updated_by_id = current_user.id
        trainer.updated_at = datetime.utcnow()
        db.session.commit()

        flash(f'Trainer profile updated for {trainer.full_name}.', 'success')
        return redirect(url_for('trainers.view_trainer', trainer_id=trainer_id))

    return render_template(
        'trainers/edit.html',
        form=form,
        trainer=trainer,
        title=f'Edit — {trainer.full_name}',
    )


@trainers_bp.route('/<int:trainer_id>/archive', methods=['POST'])
@admin_or_manager_required
def archive_trainer(trainer_id):
    trainer = Trainer.query.get_or_404(trainer_id)

    if trainer.user.id == current_user.id:
        flash('You cannot archive your own account.', 'danger')
        return redirect(url_for('trainers.view_trainer', trainer_id=trainer_id))

    trainer.is_archived = True
    trainer.updated_by_id = current_user.id
    trainer.updated_at = datetime.utcnow()

    trainer.user.is_active = False
    trainer.user.updated_by_id = current_user.id
    trainer.user.updated_at = datetime.utcnow()

    db.session.commit()
    flash(f'{trainer.full_name} has been archived.', 'secondary')
    return redirect(url_for('trainers.list_trainers'))


@trainers_bp.route('/<int:trainer_id>/restore', methods=['POST'])
@admin_or_manager_required
def restore_trainer(trainer_id):
    trainer = Trainer.query.get_or_404(trainer_id)

    trainer.is_archived = False
    trainer.updated_by_id = current_user.id
    trainer.updated_at = datetime.utcnow()

    trainer.user.is_active = True
    trainer.user.updated_by_id = current_user.id
    trainer.user.updated_at = datetime.utcnow()

    db.session.commit()
    flash(f'{trainer.full_name} has been restored.', 'success')
    return redirect(url_for('trainers.view_trainer', trainer_id=trainer_id))


@trainers_bp.route('/my-profile')
@login_required
def my_profile():
    if current_user.role != UserRole.TRAINER:
        return redirect(url_for('dashboard.home'))
    if not current_user.trainer_profile:
        flash('Trainer profile not set up yet. Contact admin.', 'warning')
        return redirect(url_for('dashboard.home'))
    return redirect(url_for('trainers.view_trainer', trainer_id=current_user.trainer_profile.id))


@trainers_bp.route('/my-profile/edit', methods=['GET', 'POST'])
@login_required
def my_profile_edit():
    """Trainer self-service: mobile number + NIC only. Everything else
    (name, specialization, bio, certifications, etc.) stays admin-managed.
    """
    if current_user.role != UserRole.TRAINER:
        return redirect(url_for('dashboard.home'))

    trainer = current_user.trainer_profile
    if not trainer:
        flash('Trainer profile not set up yet. Contact admin.', 'warning')
        return redirect(url_for('dashboard.home'))

    form = TrainerSelfEditForm(user_id=current_user.id)
    if request.method == 'GET':
        form.phone.data = trainer.user.phone
        form.nic_no.data = trainer.user.nic_no

    if form.validate_on_submit():
        mobile = form.phone.data.strip()
        trainer.user.phone = mobile
        trainer.contact_no = mobile  # keep account phone and profile contact in sync
        trainer.user.nic_no = clean_nic(form.nic_no.data)
        trainer.user.updated_by_id = current_user.id
        trainer.user.updated_at = datetime.utcnow()
        trainer.updated_by_id = current_user.id
        trainer.updated_at = datetime.utcnow()

        db.session.commit()
        flash('Your contact details have been updated.', 'success')
        return redirect(url_for('trainers.view_trainer', trainer_id=trainer.id))

    return render_template('trainers/my_profile_edit.html', form=form, trainer=trainer, title='Edit My Profile')
