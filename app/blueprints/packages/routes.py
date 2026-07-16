from datetime import datetime
from flask import render_template, redirect, url_for, flash, request
from flask_login import current_user

from app.blueprints.packages import packages_bp
from app.blueprints.packages.forms import PackageForm
from app.extensions import db
from app.models.package import Package
from app.utils.decorators import admin_or_manager_required

PACKAGES_PER_PAGE = 15


@packages_bp.route('/')
@admin_or_manager_required
def list_packages():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'active')

    query = Package.query.filter_by(is_archived=False)

    if status_filter == 'inactive':
        query = query.filter_by(is_active=False)
    elif status_filter == 'all':
        pass
    else:
        query = query.filter_by(is_active=True)

    packages = query.order_by(Package.duration_months.asc(), Package.price.asc()).paginate(
        page=page, per_page=PACKAGES_PER_PAGE, error_out=False
    )

    total_active = Package.query.filter_by(is_active=True, is_archived=False).count()
    total_inactive = Package.query.filter_by(is_active=False, is_archived=False).count()

    return render_template(
        'packages/list.html',
        packages=packages,
        status_filter=status_filter,
        total_active=total_active,
        total_inactive=total_inactive,
        title='Packages',
    )


@packages_bp.route('/create', methods=['GET', 'POST'])
@admin_or_manager_required
def create_package():
    form = PackageForm()
    if form.validate_on_submit():
        package = Package(
            name=form.name.data.strip(),
            duration_months=int(form.duration_months.data),
            price=form.price.data,
            description=form.description.data.strip() or None,
            is_active=True,
            created_by_id=current_user.id,
        )
        db.session.add(package)
        db.session.commit()
        flash(f'Package "{package.name}" created successfully.', 'success')
        return redirect(url_for('packages.view_package', package_id=package.id))

    return render_template('packages/create.html', form=form, title='Create Package')


@packages_bp.route('/<int:package_id>')
@admin_or_manager_required
def view_package(package_id):
    package = Package.query.get_or_404(package_id)
    return render_template('packages/view.html', package=package, title=package.name)


@packages_bp.route('/<int:package_id>/edit', methods=['GET', 'POST'])
@admin_or_manager_required
def edit_package(package_id):
    package = Package.query.get_or_404(package_id)

    if package.is_archived:
        flash('Archived packages cannot be edited.', 'warning')
        return redirect(url_for('packages.view_package', package_id=package_id))

    form = PackageForm()

    if request.method == 'GET':
        form.name.data = package.name
        form.duration_months.data = str(package.duration_months)
        form.price.data = package.price
        form.description.data = package.description

    if form.validate_on_submit():
        package.name = form.name.data.strip()
        package.duration_months = int(form.duration_months.data)
        package.price = form.price.data
        package.description = form.description.data.strip() or None
        package.updated_by_id = current_user.id
        package.updated_at = datetime.utcnow()
        db.session.commit()
        flash(f'Package "{package.name}" updated successfully.', 'success')
        return redirect(url_for('packages.view_package', package_id=package_id))

    return render_template('packages/edit.html', form=form, package=package, title='Edit Package')


@packages_bp.route('/<int:package_id>/toggle-status', methods=['POST'])
@admin_or_manager_required
def toggle_status(package_id):
    package = Package.query.get_or_404(package_id)

    if package.is_archived:
        flash('Cannot change status of an archived package.', 'warning')
        return redirect(url_for('packages.view_package', package_id=package_id))

    package.is_active = not package.is_active
    package.updated_by_id = current_user.id
    package.updated_at = datetime.utcnow()
    db.session.commit()

    status = 'activated' if package.is_active else 'deactivated'
    flash(f'Package "{package.name}" has been {status}.', 'success' if package.is_active else 'warning')
    return redirect(url_for('packages.view_package', package_id=package_id))


@packages_bp.route('/<int:package_id>/archive', methods=['POST'])
@admin_or_manager_required
def archive_package(package_id):
    package = Package.query.get_or_404(package_id)
    package.is_archived = True
    package.is_active = False
    package.updated_by_id = current_user.id
    package.updated_at = datetime.utcnow()
    db.session.commit()
    flash(f'Package "{package.name}" has been archived.', 'secondary')
    return redirect(url_for('packages.list_packages'))
