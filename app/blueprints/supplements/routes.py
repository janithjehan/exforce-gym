from datetime import datetime

from flask import render_template, redirect, url_for, flash, request, current_app, abort
from flask_login import current_user

from app.blueprints.supplements import supplements_bp
from app.blueprints.supplements.forms import SupplementForm, StockUpdateForm
from app.extensions import db
from app.models.supplement import Supplement, SupplementType, SupplementStatus
from app.models.user import UserRole
from app.utils.decorators import admin_required, admin_or_manager_required, roles_required
from app.utils.search import parse_search_terms, multi_term_filter

SUPPLEMENTS_PER_PAGE = 15


@supplements_bp.route('/')
@admin_or_manager_required
def list_supplements():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    search = request.args.get('q', '').strip()
    type_filter = request.args.get('type', '')

    query = Supplement.query.filter_by(is_archived=False)

    if status_filter in [s.value for s in SupplementStatus]:
        query = query.filter_by(status=SupplementStatus(status_filter))

    terms = parse_search_terms(search)
    if terms:
        query = query.filter(multi_term_filter(terms, [Supplement.name, Supplement.brand]))
    if type_filter:
        try:
            query = query.filter_by(supplement_type=SupplementType(type_filter))
        except ValueError:
            pass

    supplements = query.order_by(Supplement.name.asc()).paginate(
        page=page, per_page=SUPPLEMENTS_PER_PAGE, error_out=False
    )

    base = Supplement.query.filter_by(is_archived=False)
    total_items = base.count()
    available = base.filter_by(status=SupplementStatus.AVAILABLE).count()
    out_of_stock = base.filter_by(status=SupplementStatus.OUT_OF_STOCK).count()

    return render_template(
        'supplements/list.html',
        supplements=supplements,
        status_filter=status_filter,
        search=search,
        type_filter=type_filter,
        types=SupplementType,
        statuses=SupplementStatus,
        total_items=total_items,
        available=available,
        out_of_stock=out_of_stock,
        title='Supplements',
    )


@supplements_bp.route('/create', methods=['GET', 'POST'])
@admin_required
def create_supplement():
    form = SupplementForm()
    if form.validate_on_submit():
        item = Supplement(
            name=form.name.data.strip(),
            supplement_type=SupplementType(form.supplement_type.data),
            brand=(form.brand.data or '').strip() or None,
            price=form.price.data,
            stock_qty=form.stock_qty.data,
            status=SupplementStatus(form.status.data),
            description=form.description.data.strip() or None,
            created_by_id=current_user.id,
        )
        db.session.add(item)
        db.session.commit()
        flash(f'Supplement "{item.name}" added to the catalog.', 'success')
        return redirect(url_for('supplements.view_supplement', supplement_id=item.id))

    return render_template('supplements/create.html', form=form, title='New Supplement')


@supplements_bp.route('/<int:supplement_id>')
@admin_or_manager_required
def view_supplement(supplement_id):
    item = Supplement.query.get_or_404(supplement_id)
    stock_form = StockUpdateForm(stock_qty=item.stock_qty)
    return render_template(
        'supplements/view.html', item=item, stock_form=stock_form, title=item.name
    )


@supplements_bp.route('/<int:supplement_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_supplement(supplement_id):
    item = Supplement.query.get_or_404(supplement_id)

    if item.is_archived:
        flash('Archived supplements cannot be edited.', 'warning')
        return redirect(url_for('supplements.view_supplement', supplement_id=supplement_id))

    form = SupplementForm()

    if request.method == 'GET':
        form.name.data = item.name
        form.supplement_type.data = item.supplement_type.value
        form.brand.data = item.brand
        form.price.data = item.price
        form.stock_qty.data = item.stock_qty
        form.status.data = item.status.value
        form.description.data = item.description

    if form.validate_on_submit():
        item.name = form.name.data.strip()
        item.supplement_type = SupplementType(form.supplement_type.data)
        item.brand = (form.brand.data or '').strip() or None
        item.price = form.price.data
        item.stock_qty = form.stock_qty.data
        item.status = SupplementStatus(form.status.data)
        item.description = form.description.data.strip() or None
        item.updated_by_id = current_user.id
        item.updated_at = datetime.utcnow()
        db.session.commit()
        flash(f'Supplement "{item.name}" updated successfully.', 'success')
        return redirect(url_for('supplements.view_supplement', supplement_id=supplement_id))

    return render_template('supplements/edit.html', form=form, item=item, title='Edit Supplement')


@supplements_bp.route('/<int:supplement_id>/update-stock', methods=['POST'])
@admin_required
def update_stock(supplement_id):
    item = Supplement.query.get_or_404(supplement_id)

    if item.is_archived:
        flash('Cannot update stock of an archived supplement.', 'warning')
        return redirect(url_for('supplements.view_supplement', supplement_id=supplement_id))

    form = StockUpdateForm()
    if form.validate_on_submit():
        item.stock_qty = form.stock_qty.data
        # Keep status in sync with stock unless the product is discontinued
        if item.status != SupplementStatus.DISCONTINUED:
            item.status = (
                SupplementStatus.OUT_OF_STOCK if item.stock_qty == 0
                else SupplementStatus.AVAILABLE
            )
        item.updated_by_id = current_user.id
        item.updated_at = datetime.utcnow()
        db.session.commit()
        flash(f'Stock for "{item.name}" set to {item.stock_qty}.', 'success')
    else:
        for errors in form.errors.values():
            for e in errors:
                flash(e, 'danger')

    return redirect(url_for('supplements.view_supplement', supplement_id=supplement_id))


@supplements_bp.route('/<int:supplement_id>/archive', methods=['POST'])
@admin_required
def archive_supplement(supplement_id):
    item = Supplement.query.get_or_404(supplement_id)
    item.is_archived = True
    item.updated_by_id = current_user.id
    item.updated_at = datetime.utcnow()
    db.session.commit()
    flash(f'Supplement "{item.name}" has been archived.', 'secondary')
    return redirect(url_for('supplements.list_supplements'))


# ── Member-facing catalog (FR-SUP-02: members can view, if enabled) ──

@supplements_bp.route('/catalog')
@roles_required(UserRole.MEMBER)
def catalog():
    if not current_app.config.get('SUPPLEMENTS_MEMBER_VIEW', True):
        abort(404)

    search = request.args.get('q', '').strip()
    type_filter = request.args.get('type', '')

    query = Supplement.query.filter(
        Supplement.is_archived == False,
        Supplement.status != SupplementStatus.DISCONTINUED,
    )
    terms = parse_search_terms(search)
    if terms:
        query = query.filter(multi_term_filter(terms, [Supplement.name, Supplement.brand]))
    if type_filter:
        try:
            query = query.filter_by(supplement_type=SupplementType(type_filter))
        except ValueError:
            pass

    supplements = query.order_by(Supplement.name.asc()).all()

    return render_template(
        'supplements/catalog.html',
        supplements=supplements,
        search=search,
        type_filter=type_filter,
        types=SupplementType,
        title='Supplement Catalog',
    )