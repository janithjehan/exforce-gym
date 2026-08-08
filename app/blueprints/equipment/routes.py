import io
from datetime import datetime, date

from flask import render_template, redirect, url_for, flash, request, abort, Response
from flask_login import current_user
from sqlalchemy import func

from openpyxl import Workbook
from openpyxl.styles import Font

from app.blueprints.equipment import equipment_bp
from app.blueprints.equipment.forms import EquipmentForm
from app.extensions import db
from app.models.equipment import Equipment, EquipmentStatus
from app.models.equipment_category import EquipmentCategory
from app.utils.decorators import admin_required, admin_manager_or_trainer_required, admin_or_manager_required
from app.utils.search import parse_search_terms, multi_term_filter
from app.utils.uploads import read_image_bytes

EQUIPMENT_PER_PAGE = 15

def _filtered_equipments_query(search, status_filter, availability_filter):
    """Builds the shared Equipment query (search/status/availability filters) used by both
    list_equipment and export_equipments. These are two independent axes:
    status_filter (all / archived) is the soft-delete state; availability_filter
    (available / out_of_service) is the operational status — either can combine with the other."""
    if status_filter == 'archived':
        query = Equipment.query.filter_by(is_archived=True)
    else:
        query = Equipment.query.filter_by(is_archived=False)

    if availability_filter == 'available':
        query = query.filter_by(status=EquipmentStatus.AVAILABLE)
    elif availability_filter == 'out_of_service':
        query = query.filter_by(status=EquipmentStatus.OUT_OF_SERVICE)

    terms = parse_search_terms(search)
    if terms:
        query = query.filter(multi_term_filter(terms, [Equipment.name]))

    return query

@equipment_bp.route('/export')
@admin_or_manager_required
def export_equipments():
    """Excel (.xlsx) export of the equipment list, honouring the current list filters."""
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', 'all')
    availability_filter = request.args.get('availability', '')

    equipments = (
        _filtered_equipments_query(search, status_filter, availability_filter)).all()

    wb = Workbook()
    ws = wb.active
    ws.title = 'Equipments'

    headers = [
        'ID', 'Name', 'Quantity', 'Notes'
    ]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for u in equipments:
        ws.append([
            u.id,
            u.name,
            u.quantity,
            u.notes,
        ])

    for col in ws.columns:
        max_len = max((len(str(c.value)) for c in col if c.value is not None), default=8)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 40)

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)

    filename = f'equipments_report_{date.today().strftime("%Y%m%d")}.xlsx'
    return Response(
        out.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )




@equipment_bp.route('/<int:equipment_id>/image')
@admin_manager_or_trainer_required
def equipment_image(equipment_id):
    """Streams an equipment item's image straight from the DB."""
    item = Equipment.query.get_or_404(equipment_id)
    if not item.image_data:
        abort(404)
    return Response(
        item.image_data,
        mimetype=item.image_mimetype or 'image/jpeg',
        headers={'Cache-Control': 'private, max-age=86400'},
    )


@equipment_bp.route('/')
@admin_manager_or_trainer_required
def list_equipment():
    """Equipment list with status tabs, name search, category filter, stats, and pagination."""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    availability_filter = request.args.get('availability', '')
    search = request.args.get('q', '').strip()
    category_filter = request.args.get('category', 0, type=int)

    query = _filtered_equipments_query(search, status_filter, availability_filter)
    if category_filter:
        query = query.filter_by(category_id=category_filter)

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
        availability_filter=availability_filter,
        search=search,
        category_filter=category_filter,
        categories=EquipmentCategory.query.order_by(EquipmentCategory.name.asc()).all(),
        total_items=total_items,
        total_units=total_units,
        out_of_service=out_of_service,
        title='Equipment',
    )


@equipment_bp.route('/create', methods=['GET', 'POST'])
@admin_required
def create_equipment():
    """Creates a new equipment item; blocked if no active equipment category is configured yet."""
    if not EquipmentCategory.query.filter_by(is_active=True).first():
        flash('No equipment categories are configured yet. Add at least one first.', 'warning')
        return redirect(url_for('configuration.list_equipment_categories'))

    form = EquipmentForm()
    if form.validate_on_submit():
        item = Equipment(
            name=form.name.data.strip(),
            category_id=form.category.data,
            quantity=form.quantity.data,
            status=EquipmentStatus(form.status.data),
            notes=form.notes.data.strip() or None,
            created_by_id=current_user.id,
        )
        if form.image.data:
            item.image_data, item.image_mimetype = read_image_bytes(form.image.data)
        db.session.add(item)
        db.session.commit()
        flash(f'Equipment "{item.name}" added.', 'success')
        return redirect(url_for('equipment.view_equipment', equipment_id=item.id))

    return render_template('equipment/create.html', form=form, title='New Equipment')


@equipment_bp.route('/<int:equipment_id>')
@admin_manager_or_trainer_required
def view_equipment(equipment_id):
    """Equipment detail page — image, details, notes, audit info."""
    item = Equipment.query.get_or_404(equipment_id)
    return render_template('equipment/view.html', item=item, title=item.name)


@equipment_bp.route('/<int:equipment_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_equipment(equipment_id):
    """Edits an equipment item's fields/image; blocked if archived."""
    item = Equipment.query.get_or_404(equipment_id)

    if item.is_archived:
        flash('Archived equipment cannot be edited.', 'warning')
        return redirect(url_for('equipment.view_equipment', equipment_id=equipment_id))

    form = EquipmentForm(current_category=item.category)

    if request.method == 'GET':
        form.name.data = item.name
        form.category.data = item.category_id
        form.quantity.data = item.quantity
        form.status.data = item.status.value
        form.notes.data = item.notes

    if form.validate_on_submit():
        item.name = form.name.data.strip()
        item.category_id = form.category.data
        item.quantity = form.quantity.data
        item.status = EquipmentStatus(form.status.data)
        item.notes = form.notes.data.strip() or None

        if form.image.data:
            item.image_data, item.image_mimetype = read_image_bytes(form.image.data)
        elif form.remove_image.data:
            item.image_data = None
            item.image_mimetype = None

        item.updated_by_id = current_user.id
        item.updated_at = datetime.utcnow()
        db.session.commit()
        flash(f'Equipment "{item.name}" updated successfully.', 'success')
        return redirect(url_for('equipment.view_equipment', equipment_id=equipment_id))

    return render_template('equipment/edit.html', form=form, item=item, title='Edit Equipment')


@equipment_bp.route('/<int:equipment_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_status(equipment_id):
    """Flips an equipment item's status between Available and Out of Service."""
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
    """Soft-deletes an equipment item."""
    item = Equipment.query.get_or_404(equipment_id)
    item.is_archived = True
    item.updated_by_id = current_user.id
    item.updated_at = datetime.utcnow()
    db.session.commit()
    flash(f'Equipment "{item.name}" has been archived.', 'secondary')
    return redirect(url_for('equipment.list_equipment'))


@equipment_bp.route('/<int:equipment_id>/restore', methods=['POST'])
@admin_required
def restore_equipment(equipment_id):
    """Soft-deletes an equipment item."""
    item = Equipment.query.get_or_404(equipment_id)
    item.is_archived = False
    item.updated_by_id = current_user.id
    item.updated_at = datetime.utcnow()
    db.session.commit()
    flash(f'Equipment "{item.name}" has been restored.', 'secondary')
    return redirect(url_for('equipment.list_equipment'))