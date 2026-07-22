import os
import uuid
from datetime import datetime

from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import current_user
from sqlalchemy import func
from werkzeug.utils import secure_filename

from app.blueprints.equipment import equipment_bp
from app.blueprints.equipment.forms import EquipmentForm
from app.extensions import db
from app.models.equipment import Equipment, EquipmentCategory, EquipmentStatus
from app.utils.decorators import admin_required, admin_manager_or_trainer_required
from app.utils.search import parse_search_terms, multi_term_filter

EQUIPMENT_PER_PAGE = 15


def _upload_dir():
    path = os.path.join(current_app.static_folder, 'uploads', 'equipment')
    os.makedirs(path, exist_ok=True)
    return path


def _save_image(file_storage):
    """Store an uploaded image with a unique name; returns the stored filename."""
    original = secure_filename(file_storage.filename)
    ext = original.rsplit('.', 1)[-1].lower() if '.' in original else 'jpg'
    filename = f'{uuid.uuid4().hex}.{ext}'
    file_storage.save(os.path.join(_upload_dir(), filename))
    return filename


def _delete_image(filename):
    if not filename:
        return
    path = os.path.join(_upload_dir(), filename)
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass  # never block the request on filesystem cleanup


@equipment_bp.route('/')
@admin_manager_or_trainer_required
def list_equipment():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    search = request.args.get('q', '').strip()
    category_filter = request.args.get('category', '')

    query = Equipment.query.filter_by(is_archived=False)

    if status_filter == 'available':
        query = query.filter_by(status=EquipmentStatus.AVAILABLE)
    elif status_filter == 'out_of_service':
        query = query.filter_by(status=EquipmentStatus.OUT_OF_SERVICE)

    terms = parse_search_terms(search)
    if terms:
        query = query.filter(multi_term_filter(terms, [Equipment.name]))
    if category_filter:
        try:
            query = query.filter_by(category=EquipmentCategory(category_filter))
        except ValueError:
            pass

    equipment = query.order_by(Equipment.name.asc()).paginate(
        page=page, per_page=EQUIPMENT_PER_PAGE, error_out=False
    )

    base = Equipment.query.filter_by(is_archived=False)
    total_items = base.count()
    total_units = base.with_entities(func.coalesce(func.sum(Equipment.quantity), 0)).scalar()
    out_of_service = base.filter_by(status=EquipmentStatus.OUT_OF_SERVICE).count()

    return render_template(
        'equipment/list.html',
        equipment=equipment,
        status_filter=status_filter,
        search=search,
        category_filter=category_filter,
        categories=EquipmentCategory,
        total_items=total_items,
        total_units=total_units,
        out_of_service=out_of_service,
        title='Equipment',
    )


@equipment_bp.route('/create', methods=['GET', 'POST'])
@admin_required
def create_equipment():
    form = EquipmentForm()
    if form.validate_on_submit():
        image_filename = None
        if form.image.data:
            image_filename = _save_image(form.image.data)

        item = Equipment(
            name=form.name.data.strip(),
            category=EquipmentCategory(form.category.data),
            quantity=form.quantity.data,
            status=EquipmentStatus(form.status.data),
            image_filename=image_filename,
            notes=form.notes.data.strip() or None,
            created_by_id=current_user.id,
        )
        db.session.add(item)
        db.session.commit()
        flash(f'Equipment "{item.name}" added.', 'success')
        return redirect(url_for('equipment.view_equipment', equipment_id=item.id))

    return render_template('equipment/create.html', form=form, title='New Equipment')


@equipment_bp.route('/<int:equipment_id>')
@admin_manager_or_trainer_required
def view_equipment(equipment_id):
    item = Equipment.query.get_or_404(equipment_id)
    return render_template('equipment/view.html', item=item, title=item.name)


@equipment_bp.route('/<int:equipment_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_equipment(equipment_id):
    item = Equipment.query.get_or_404(equipment_id)

    if item.is_archived:
        flash('Archived equipment cannot be edited.', 'warning')
        return redirect(url_for('equipment.view_equipment', equipment_id=equipment_id))

    form = EquipmentForm()

    if request.method == 'GET':
        form.name.data = item.name
        form.category.data = item.category.value
        form.quantity.data = item.quantity
        form.status.data = item.status.value
        form.notes.data = item.notes

    if form.validate_on_submit():
        item.name = form.name.data.strip()
        item.category = EquipmentCategory(form.category.data)
        item.quantity = form.quantity.data
        item.status = EquipmentStatus(form.status.data)
        item.notes = form.notes.data.strip() or None

        if form.image.data:
            _delete_image(item.image_filename)
            item.image_filename = _save_image(form.image.data)
        elif form.remove_image.data:
            _delete_image(item.image_filename)
            item.image_filename = None

        item.updated_by_id = current_user.id
        item.updated_at = datetime.utcnow()
        db.session.commit()
        flash(f'Equipment "{item.name}" updated successfully.', 'success')
        return redirect(url_for('equipment.view_equipment', equipment_id=equipment_id))

    return render_template('equipment/edit.html', form=form, item=item, title='Edit Equipment')


@equipment_bp.route('/<int:equipment_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_status(equipment_id):
    item = Equipment.query.get_or_404(equipment_id)

    if item.is_archived:
        flash('Cannot change status of archived equipment.', 'warning')
        return redirect(url_for('equipment.view_equipment', equipment_id=equipment_id))

    if item.status == EquipmentStatus.AVAILABLE:
        item.status = EquipmentStatus.OUT_OF_SERVICE
        flash(f'"{item.name}" marked as Out of Service.', 'warning')
    else:
        item.status = EquipmentStatus.AVAILABLE
        flash(f'"{item.name}" marked as Available.', 'success')

    item.updated_by_id = current_user.id
    item.updated_at = datetime.utcnow()
    db.session.commit()
    return redirect(url_for('equipment.view_equipment', equipment_id=equipment_id))


@equipment_bp.route('/<int:equipment_id>/archive', methods=['POST'])
@admin_required
def archive_equipment(equipment_id):
    item = Equipment.query.get_or_404(equipment_id)
    item.is_archived = True
    item.updated_by_id = current_user.id
    item.updated_at = datetime.utcnow()
    db.session.commit()
    flash(f'Equipment "{item.name}" has been archived.', 'secondary')
    return redirect(url_for('equipment.list_equipment'))