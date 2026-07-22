from datetime import datetime
from flask import render_template, redirect, url_for, flash, request
from flask_login import current_user

from app.blueprints.workouts import workouts_bp
from app.blueprints.workouts.forms import WorkoutForm
from app.extensions import db
from app.models.workout import Workout, WorkoutType, MuscleGroup, DifficultyLevel
from app.utils.decorators import admin_or_trainer_required
from app.utils.search import parse_search_terms, multi_term_filter

WORKOUTS_PER_PAGE = 15


@workouts_bp.route('/')
@admin_or_trainer_required
def list_workouts():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'active')
    search = request.args.get('q', '').strip()
    type_filter = request.args.get('type', '')
    muscle_filter = request.args.get('muscle', '')
    difficulty_filter = request.args.get('difficulty', '')

    query = Workout.query.filter_by(is_archived=False)

    if status_filter == 'inactive':
        query = query.filter_by(is_active=False)
    elif status_filter == 'all':
        pass
    else:
        query = query.filter_by(is_active=True)

    terms = parse_search_terms(search)
    if terms:
        query = query.filter(multi_term_filter(terms, [Workout.name]))
    if type_filter:
        try:
            query = query.filter_by(workout_type=WorkoutType(type_filter))
        except ValueError:
            pass
    if muscle_filter:
        try:
            query = query.filter_by(muscle_group=MuscleGroup(muscle_filter))
        except ValueError:
            pass
    if difficulty_filter:
        try:
            query = query.filter_by(difficulty=DifficultyLevel(difficulty_filter))
        except ValueError:
            pass

    workouts = query.order_by(Workout.name.asc()).paginate(
        page=page, per_page=WORKOUTS_PER_PAGE, error_out=False
    )

    total_active = Workout.query.filter_by(is_active=True, is_archived=False).count()
    total_inactive = Workout.query.filter_by(is_active=False, is_archived=False).count()

    return render_template(
        'workouts/list.html',
        workouts=workouts,
        status_filter=status_filter,
        search=search,
        type_filter=type_filter,
        muscle_filter=muscle_filter,
        difficulty_filter=difficulty_filter,
        workout_types=WorkoutType,
        muscle_groups=MuscleGroup,
        difficulty_levels=DifficultyLevel,
        total_active=total_active,
        total_inactive=total_inactive,
        title='Workout Library',
    )


@workouts_bp.route('/create', methods=['GET', 'POST'])
@admin_or_trainer_required
def create_workout():
    form = WorkoutForm()
    if form.validate_on_submit():
        workout = Workout(
            name=form.name.data.strip(),
            workout_type=WorkoutType(form.workout_type.data),
            muscle_group=MuscleGroup(form.muscle_group.data),
            difficulty=DifficultyLevel(form.difficulty.data),
            equipment_needed=form.equipment_needed.data.strip() or None,
            instructions=form.instructions.data.strip() or None,
            is_active=True,
            created_by_id=current_user.id,
        )
        db.session.add(workout)
        db.session.commit()
        flash(f'Workout "{workout.name}" added to the library.', 'success')
        return redirect(url_for('workouts.view_workout', workout_id=workout.id))

    return render_template('workouts/create.html', form=form, title='New Workout')


@workouts_bp.route('/<int:workout_id>')
@admin_or_trainer_required
def view_workout(workout_id):
    workout = Workout.query.get_or_404(workout_id)
    return render_template('workouts/view.html', workout=workout, title=workout.name)


@workouts_bp.route('/<int:workout_id>/edit', methods=['GET', 'POST'])
@admin_or_trainer_required
def edit_workout(workout_id):
    workout = Workout.query.get_or_404(workout_id)

    if workout.is_archived:
        flash('Archived workouts cannot be edited.', 'warning')
        return redirect(url_for('workouts.view_workout', workout_id=workout_id))

    form = WorkoutForm()

    if request.method == 'GET':
        form.name.data = workout.name
        form.workout_type.data = workout.workout_type.value
        form.muscle_group.data = workout.muscle_group.value
        form.difficulty.data = workout.difficulty.value
        form.equipment_needed.data = workout.equipment_needed
        form.instructions.data = workout.instructions

    if form.validate_on_submit():
        workout.name = form.name.data.strip()
        workout.workout_type = WorkoutType(form.workout_type.data)
        workout.muscle_group = MuscleGroup(form.muscle_group.data)
        workout.difficulty = DifficultyLevel(form.difficulty.data)
        workout.equipment_needed = form.equipment_needed.data.strip() or None
        workout.instructions = form.instructions.data.strip() or None
        workout.updated_by_id = current_user.id
        workout.updated_at = datetime.utcnow()
        db.session.commit()
        flash(f'Workout "{workout.name}" updated successfully.', 'success')
        return redirect(url_for('workouts.view_workout', workout_id=workout_id))

    return render_template('workouts/edit.html', form=form, workout=workout, title='Edit Workout')


@workouts_bp.route('/<int:workout_id>/toggle-status', methods=['POST'])
@admin_or_trainer_required
def toggle_status(workout_id):
    workout = Workout.query.get_or_404(workout_id)

    if workout.is_archived:
        flash('Cannot change status of an archived workout.', 'warning')
        return redirect(url_for('workouts.view_workout', workout_id=workout_id))

    workout.is_active = not workout.is_active
    workout.updated_by_id = current_user.id
    workout.updated_at = datetime.utcnow()
    db.session.commit()

    status = 'activated' if workout.is_active else 'deactivated'
    flash(f'Workout "{workout.name}" has been {status}.', 'success' if workout.is_active else 'warning')
    return redirect(url_for('workouts.view_workout', workout_id=workout_id))


@workouts_bp.route('/<int:workout_id>/archive', methods=['POST'])
@admin_or_trainer_required
def archive_workout(workout_id):
    workout = Workout.query.get_or_404(workout_id)
    workout.is_archived = True
    workout.is_active = False
    workout.updated_by_id = current_user.id
    workout.updated_at = datetime.utcnow()
    db.session.commit()
    flash(f'Workout "{workout.name}" has been archived.', 'secondary')
    return redirect(url_for('workouts.list_workouts'))