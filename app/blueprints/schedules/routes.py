from datetime import datetime
from flask import (
    render_template, redirect, url_for, flash, request, abort, Response,
)
from flask_login import current_user

from app.blueprints.schedules import schedules_bp
from app.blueprints.schedules.forms import ScheduleForm, parse_item_rows
from app.blueprints.schedules.pdf import build_schedule_pdf
from app.extensions import db
from app.models.member import Member
from app.models.schedule import (
    Schedule, ScheduleItem, ScheduleStatus, ScheduleEditLog,
)
from app.models.trainer import Trainer
from app.models.user import User, UserRole
from app.models.workout import Workout
from app.utils.decorators import (
    admin_or_trainer_required, admin_manager_or_trainer_required, roles_required,
)
from app.utils.search import parse_search_terms, multi_term_filter

SCHEDULES_PER_PAGE = 15


def _can_manage(schedule):
    """Admin manages any schedule; a trainer only their own."""
    if current_user.role == UserRole.ADMIN:
        return True
    if current_user.role == UserRole.TRAINER:
        profile = getattr(current_user, 'trainer_profile', None)
        return profile is not None and schedule.trainer_id == profile.id
    return False


def _populate_choices(form):
    members = (
        Member.query.join(User, Member.user_id == User.id)
        .filter(Member.is_archived == False, User.is_active == True)
        .order_by(User.first_name.asc())
        .all()
    )
    form.member_id.choices = [(m.id, m.full_name) for m in members]

    if current_user.role == UserRole.TRAINER:
        profile = current_user.trainer_profile
        form.trainer_id.choices = [(profile.id, profile.full_name)] if profile else []
    else:
        trainers = (
            Trainer.query.join(User, Trainer.user_id == User.id)
            .filter(Trainer.is_archived == False, User.is_active == True)
            .order_by(User.first_name.asc())
            .all()
        )
        form.trainer_id.choices = [(t.id, t.full_name) for t in trainers]


def _active_workouts():
    return (
        Workout.query.filter_by(is_active=True, is_archived=False)
        .order_by(Workout.name.asc())
        .all()
    )


@schedules_bp.route('/')
@admin_manager_or_trainer_required
def list_schedules():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'planned')
    search = request.args.get('q', '').strip()

    query = Schedule.query

    if status_filter in ('planned', 'completed', 'cancelled'):
        query = query.filter(Schedule.status == ScheduleStatus(status_filter))

    terms = parse_search_terms(search)
    if terms:
        query = (
            query.join(Member, Schedule.member_id == Member.id)
            .join(User, Member.user_id == User.id)
            .filter(multi_term_filter(terms, [
                User.first_name, User.last_name, Schedule.title,
            ]))
        )

    schedules = query.order_by(Schedule.start_date.desc(), Schedule.id.desc()).paginate(
        page=page, per_page=SCHEDULES_PER_PAGE, error_out=False
    )

    stats = {
        'planned': Schedule.query.filter_by(status=ScheduleStatus.PLANNED).count(),
        'completed': Schedule.query.filter_by(status=ScheduleStatus.COMPLETED).count(),
        'cancelled': Schedule.query.filter_by(status=ScheduleStatus.CANCELLED).count(),
    }

    return render_template(
        'schedules/list.html',
        schedules=schedules,
        status_filter=status_filter,
        search=search,
        stats=stats,
        title='Schedules',
    )


@schedules_bp.route('/create', methods=['GET', 'POST'])
@admin_or_trainer_required
def create_schedule():
    if current_user.role == UserRole.TRAINER and not current_user.trainer_profile:
        flash('Your trainer profile has not been set up yet. Contact admin.', 'warning')
        return redirect(url_for('dashboard.home'))

    form = ScheduleForm()
    _populate_choices(form)
    workouts = _active_workouts()

    if request.method == 'GET':
        member_id = request.args.get('member_id', type=int)
        if member_id and any(member_id == c[0] for c in form.member_id.choices):
            form.member_id.data = member_id
        if current_user.role == UserRole.TRAINER:
            form.trainer_id.data = current_user.trainer_profile.id

    if form.validate_on_submit():
        items, item_errors = parse_item_rows(request.form)
        valid_workout_ids = {w.id for w in workouts}
        for item in items:
            if item['workout_id'] not in valid_workout_ids:
                item_errors.append('One of the selected workouts is not available.')
                break

        if item_errors:
            for e in item_errors:
                flash(e, 'danger')
        else:
            schedule = Schedule(
                member_id=form.member_id.data,
                trainer_id=form.trainer_id.data,
                title=form.title.data.strip(),
                start_date=form.start_date.data,
                end_date=form.end_date.data,
                notes=form.notes.data.strip() or None,
                created_by_id=current_user.id,
            )
            db.session.add(schedule)
            db.session.flush()
            for item in items:
                db.session.add(ScheduleItem(schedule_id=schedule.id, **item))
            db.session.commit()
            flash(f'Schedule "{schedule.title}" created with {len(items)} workout item(s).', 'success')
            return redirect(url_for('schedules.view_schedule', schedule_id=schedule.id))

    return render_template(
        'schedules/create.html',
        form=form,
        workouts=workouts,
        existing_items=[],
        title='New Schedule',
    )


@schedules_bp.route('/<int:schedule_id>')
def view_schedule(schedule_id):
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login', next=request.url))

    schedule = Schedule.query.get_or_404(schedule_id)

    if current_user.role == UserRole.MEMBER:
        profile = getattr(current_user, 'member_profile', None)
        if not profile or schedule.member_id != profile.id:
            abort(403)

    edit_logs = schedule.edit_logs.limit(20).all()
    return render_template(
        'schedules/view.html',
        schedule=schedule,
        edit_logs=edit_logs,
        can_manage=_can_manage(schedule),
        title=schedule.title,
    )


@schedules_bp.route('/<int:schedule_id>/edit', methods=['GET', 'POST'])
@admin_or_trainer_required
def edit_schedule(schedule_id):
    schedule = Schedule.query.get_or_404(schedule_id)

    if not _can_manage(schedule):
        abort(403)
    if schedule.status != ScheduleStatus.PLANNED:
        flash('Completed or cancelled schedules cannot be edited.', 'warning')
        return redirect(url_for('schedules.view_schedule', schedule_id=schedule_id))

    form = ScheduleForm()
    _populate_choices(form)
    # Include workouts referenced by existing items even if since deactivated
    workouts = _active_workouts()
    existing_workout_ids = {w.id for w in workouts}
    for item in schedule.items:
        if item.workout_id not in existing_workout_ids:
            workouts.append(item.workout)

    if request.method == 'GET':
        form.member_id.data = schedule.member_id
        form.trainer_id.data = schedule.trainer_id
        form.title.data = schedule.title
        form.start_date.data = schedule.start_date
        form.end_date.data = schedule.end_date
        form.notes.data = schedule.notes

    if form.validate_on_submit():
        items, item_errors = parse_item_rows(request.form)
        valid_workout_ids = {w.id for w in workouts}
        for item in items:
            if item['workout_id'] not in valid_workout_ids:
                item_errors.append('One of the selected workouts is not available.')
                break

        if item_errors:
            for e in item_errors:
                flash(e, 'danger')
        else:
            # FR-SCH-02: summarize what changed, bump version, log it
            changes = []
            if schedule.title != form.title.data.strip():
                changes.append(f'title "{schedule.title}" → "{form.title.data.strip()}"')
            if schedule.member_id != form.member_id.data:
                changes.append('member reassigned')
            if schedule.trainer_id != form.trainer_id.data:
                changes.append('trainer reassigned')
            if (schedule.start_date, schedule.end_date) != (form.start_date.data, form.end_date.data):
                changes.append(
                    f'dates {schedule.start_date} – {schedule.end_date} → '
                    f'{form.start_date.data} – {form.end_date.data}'
                )
            if (schedule.notes or '') != (form.notes.data.strip() or ''):
                changes.append('notes updated')
            old_items = [
                (i.workout_id, i.day_label, i.sets, i.reps, i.rest_seconds, i.notes)
                for i in schedule.items
            ]
            new_items = [
                (i['workout_id'], i['day_label'], i['sets'], i['reps'], i['rest_seconds'], i['notes'])
                for i in items
            ]
            if old_items != new_items:
                changes.append(f'workout items updated ({len(old_items)} → {len(new_items)})')

            if not changes:
                flash('No changes detected.', 'info')
                return redirect(url_for('schedules.view_schedule', schedule_id=schedule_id))

            schedule.member_id = form.member_id.data
            schedule.trainer_id = form.trainer_id.data
            schedule.title = form.title.data.strip()
            schedule.start_date = form.start_date.data
            schedule.end_date = form.end_date.data
            schedule.notes = form.notes.data.strip() or None
            schedule.items = [ScheduleItem(**item) for item in items]
            schedule.version += 1
            schedule.updated_by_id = current_user.id
            schedule.updated_at = datetime.utcnow()
            db.session.add(ScheduleEditLog(
                schedule_id=schedule.id,
                edited_by_id=current_user.id,
                version=schedule.version,
                summary='; '.join(changes),
            ))
            db.session.commit()
            flash(f'Schedule updated to version {schedule.version}.', 'success')
            return redirect(url_for('schedules.view_schedule', schedule_id=schedule_id))

    existing_items = [
        {
            'workout_id': i.workout_id,
            'day_label': i.day_label,
            'sets': i.sets,
            'reps': i.reps,
            'rest_seconds': i.rest_seconds,
            'notes': i.notes or '',
        }
        for i in schedule.items
    ]

    return render_template(
        'schedules/edit.html',
        form=form,
        schedule=schedule,
        workouts=workouts,
        existing_items=existing_items,
        title='Edit Schedule',
    )


@schedules_bp.route('/<int:schedule_id>/complete', methods=['POST'])
def complete_schedule(schedule_id):
    """FR-SCH-03: the assigned member (or admin/own trainer) marks completion."""
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))

    schedule = Schedule.query.get_or_404(schedule_id)

    is_own_member = (
        current_user.role == UserRole.MEMBER
        and getattr(current_user, 'member_profile', None)
        and schedule.member_id == current_user.member_profile.id
    )
    if not (is_own_member or _can_manage(schedule)):
        abort(403)

    if schedule.status != ScheduleStatus.PLANNED:
        flash('Only planned schedules can be marked as completed.', 'warning')
        return redirect(url_for('schedules.view_schedule', schedule_id=schedule_id))

    schedule.status = ScheduleStatus.COMPLETED
    schedule.updated_by_id = current_user.id
    schedule.updated_at = datetime.utcnow()
    db.session.commit()
    flash(f'Schedule "{schedule.title}" marked as completed.', 'success')
    return redirect(url_for('schedules.view_schedule', schedule_id=schedule_id))


@schedules_bp.route('/<int:schedule_id>/cancel', methods=['POST'])
@admin_or_trainer_required
def cancel_schedule(schedule_id):
    schedule = Schedule.query.get_or_404(schedule_id)

    if not _can_manage(schedule):
        abort(403)
    if schedule.status != ScheduleStatus.PLANNED:
        flash('Only planned schedules can be cancelled.', 'warning')
        return redirect(url_for('schedules.view_schedule', schedule_id=schedule_id))

    schedule.status = ScheduleStatus.CANCELLED
    schedule.updated_by_id = current_user.id
    schedule.updated_at = datetime.utcnow()
    db.session.commit()
    flash(f'Schedule "{schedule.title}" cancelled.', 'secondary')
    return redirect(url_for('schedules.view_schedule', schedule_id=schedule_id))


@schedules_bp.route('/<int:schedule_id>/pdf')
def download_pdf(schedule_id):
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login', next=request.url))

    schedule = Schedule.query.get_or_404(schedule_id)

    if current_user.role == UserRole.MEMBER:
        profile = getattr(current_user, 'member_profile', None)
        if not profile or schedule.member_id != profile.id:
            abort(403)

    pdf_bytes = build_schedule_pdf(schedule)
    filename = f'schedule-{schedule.id}-v{schedule.version}.pdf'
    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@schedules_bp.route('/my-schedules')
@roles_required(UserRole.MEMBER)
def my_schedules():
    profile = getattr(current_user, 'member_profile', None)
    if not profile:
        flash('Your member profile has not been set up yet. Contact admin.', 'warning')
        return redirect(url_for('dashboard.home'))

    page = request.args.get('page', 1, type=int)
    schedules = (
        Schedule.query.filter_by(member_id=profile.id)
        .order_by(Schedule.start_date.desc(), Schedule.id.desc())
        .paginate(page=page, per_page=10, error_out=False)
    )
    return render_template(
        'schedules/my_schedules.html',
        schedules=schedules,
        title='My Schedules',
    )