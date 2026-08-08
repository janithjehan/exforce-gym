from datetime import datetime
from flask import render_template, redirect, url_for, flash
from flask_login import current_user

from app.blueprints.configuration import configuration_bp
from app.blueprints.configuration.forms import ConfigurationForm, EquipmentCategoryForm, WorkoutCategoryForm
from app.extensions import db
from app.models.configuration import AppConfiguration
from app.models.equipment_category import EquipmentCategory
from app.models.workout_category import WorkoutCategory
from app.utils.decorators import admin_required


@configuration_bp.route('/', methods=['GET', 'POST'])
@admin_required
def edit_configuration():
    """Singleton settings page — bank transfer details shown to members."""
    settings = AppConfiguration.get()
    form = ConfigurationForm(obj=settings)

    if form.validate_on_submit():
        settings.bank_transfer_details = form.bank_transfer_details.data.strip() or None
        settings.updated_by_id = current_user.id
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Configuration updated.', 'success')
        return redirect(url_for('configuration.edit_configuration'))

    return render_template(
        'configuration/edit.html', form=form, settings=settings, title='Configuration'
    )


@configuration_bp.route('/equipment-categories')
@admin_required
def list_equipment_categories():
    """Lists all equipment categories (active + inactive) with their status."""
    categories = EquipmentCategory.query.order_by(EquipmentCategory.name.asc()).all()
    return render_template(
        'configuration/equipment_categories/list.html', categories=categories,
        title='Equipment Categories'
    )


@configuration_bp.route('/equipment-categories/create', methods=['GET', 'POST'])
@admin_required
def create_equipment_category():
    """Creates a new equipment category, starting Active."""
    form = EquipmentCategoryForm()
    if form.validate_on_submit():
        category = EquipmentCategory(
            name=form.name.data.strip(),
            is_active=True,
            created_by_id=current_user.id,
        )
        db.session.add(category)
        db.session.commit()
        flash(f'Category "{category.name}" added.', 'success')
        return redirect(url_for('configuration.list_equipment_categories'))

    return render_template(
        'configuration/equipment_categories/create.html', form=form, title='New Equipment Category'
    )


@configuration_bp.route('/equipment-categories/<int:category_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_equipment_category(category_id):
    """Renames an equipment category; renaming propagates to every Equipment row using it."""
    category = EquipmentCategory.query.get_or_404(category_id)
    form = EquipmentCategoryForm(obj=category)

    if form.validate_on_submit():
        category.name = form.name.data.strip()
        category.updated_by_id = current_user.id
        category.updated_at = datetime.utcnow()
        db.session.commit()
        flash(f'Category "{category.name}" updated.', 'success')
        return redirect(url_for('configuration.list_equipment_categories'))

    return render_template(
        'configuration/equipment_categories/edit.html', form=form, category=category,
        title='Edit Equipment Category'
    )


@configuration_bp.route('/equipment-categories/<int:category_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_equipment_category_status(category_id):
    """Flips a category's Active/Inactive status; deactivated categories drop out of new-item pickers
    but stay valid on equipment already tagged with them."""
    category = EquipmentCategory.query.get_or_404(category_id)
    category.is_active = not category.is_active
    category.updated_by_id = current_user.id
    category.updated_at = datetime.utcnow()
    db.session.commit()

    status = 'activated' if category.is_active else 'deactivated'
    flash(f'Category "{category.name}" has been {status}.', 'success' if category.is_active else 'warning')
    return redirect(url_for('configuration.list_equipment_categories'))


@configuration_bp.route('/equipment-categories/<int:category_id>/delete', methods=['POST'])
@admin_required
def delete_equipment_category(category_id):
    """Permanently removes a category. Blocked while any Equipment row still uses it —
    category_id is a required FK, so unlinking it from equipment first (recategorize or
    archive those items) is a prerequisite, not something this route can do silently."""
    category = EquipmentCategory.query.get_or_404(category_id)
    in_use = category.equipment_items.count()
    if in_use:
        flash(
            f'Cannot delete "{category.name}" — {in_use} equipment item(s) still use it. '
            'Recategorize or archive them first.',
            'danger',
        )
        return redirect(url_for('configuration.list_equipment_categories'))

    name = category.name
    db.session.delete(category)
    db.session.commit()
    flash(f'Category "{name}" deleted.', 'success')
    return redirect(url_for('configuration.list_equipment_categories'))

@configuration_bp.route('/workout-categories')
@admin_required
def list_workout_categories():
    """Lists all workout categories (active + inactive) with their status."""
    categories = WorkoutCategory.query.order_by(WorkoutCategory.name.asc()).all()
    return render_template(
        'configuration/workout_categories/list.html', categories=categories,
        title='Workout Categories'
    )


@configuration_bp.route('/workout-categories/create', methods=['GET', 'POST'])
@admin_required
def create_workout_category():
    """Creates a new workout category, starting Active."""
    form = WorkoutCategoryForm()
    if form.validate_on_submit():
        category = WorkoutCategory(
            name=form.name.data.strip(),
            is_active=True,
            created_by_id=current_user.id,
        )
        db.session.add(category)
        db.session.commit()
        flash(f'Category "{category.name}" added.', 'success')
        return redirect(url_for('configuration.list_workout_categories'))

    return render_template(
        'configuration/workout_categories/create.html', form=form, title='New Workout Category'
    )


@configuration_bp.route('/workout-categories/<int:category_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_workout_category(category_id):
    """Renames an workout category; renaming propagates to every Workout row using it."""
    category = WorkoutCategory.query.get_or_404(category_id)
    form = WorkoutCategoryForm(obj=category)

    if form.validate_on_submit():
        category.name = form.name.data.strip()
        category.updated_by_id = current_user.id
        category.updated_at = datetime.utcnow()
        db.session.commit()
        flash(f'Category "{category.name}" updated.', 'success')
        return redirect(url_for('configuration.list_workout_categories'))

    return render_template(
        'configuration/workout_categories/edit.html', form=form, category=category,
        title='Edit Workout Category'
    )

@configuration_bp.route('/workout-categories/<int:category_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_workout_category_status(category_id):
    """Flips a category's Active/Inactive status; deactivated categories drop out of new-item pickers
    but stay valid on workout already tagged with them."""
    category = WorkoutCategory.query.get_or_404(category_id)
    category.is_active = not category.is_active
    category.updated_by_id = current_user.id
    category.updated_at = datetime.utcnow()
    db.session.commit()

    status = 'activated' if category.is_active else 'deactivated'
    flash(f'Category "{category.name}" has been {status}.', 'success' if category.is_active else 'warning')
    return redirect(url_for('configuration.list_workout_categories'))

@configuration_bp.route('/workout-categories/<int:category_id>/delete', methods=['POST'])
@admin_required
def delete_workout_category(category_id):
    """Permanently removes a category. Blocked while any Workout row still uses it —
    category_id is a required FK, so unlinking it from workout first (recategorize or
    archive those items) is a prerequisite, not something this route can do silently."""
    category = WorkoutCategory.query.get_or_404(category_id)
    in_use = category.workout_items.count()
    if in_use:
        flash(
            f'Cannot delete "{category.name}" — {in_use} workout item(s) still use it. '
            'Recategorize or archive them first.',
            'danger',
        )
        return redirect(url_for('configuration.list_workout_categories'))

    name = category.name
    db.session.delete(category)
    db.session.commit()
    flash(f'Category "{name}" deleted.', 'success')
    return redirect(url_for('configuration.list_workout_categories'))