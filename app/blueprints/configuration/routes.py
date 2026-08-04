from datetime import datetime
from flask import render_template, redirect, url_for, flash, request
from flask_login import current_user

from app.blueprints.configuration import configuration_bp
from app.blueprints.configuration.forms import ConfigurationForm, EquipmentCategoryForm
from app.extensions import db
from app.models.configuration import AppConfiguration
from app.models.equipment_category import EquipmentCategory
from app.utils.decorators import admin_required


@configuration_bp.route('/', methods=['GET', 'POST'])
@admin_required
def edit_configuration():
    """Singleton settings page — bank transfer details + globally allowed installment counts."""
    settings = AppConfiguration.get()
    form = ConfigurationForm(obj=settings)

    if form.validate_on_submit():
        settings.bank_transfer_details = form.bank_transfer_details.data.strip() or None
        parsed = AppConfiguration.parse_installment_options(form.installment_options.data)
        settings.installment_options = ','.join(str(n) for n in parsed) or None
        settings.updated_by_id = current_user.id
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Configuration updated.', 'success')
        return redirect(url_for('configuration.edit_configuration'))

    if request.method == 'GET':
        form.installment_options.data = settings.installment_options or ''

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