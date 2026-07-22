from datetime import datetime, date
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import current_user, login_required

from app.blueprints.measurements import measurements_bp
from app.blueprints.measurements.forms import MeasurementForm
from app.extensions import db
from app.models.measurement import Measurement, MeasurementEditLog
from app.models.member import Member
from app.models.user import User, UserRole
from app.utils.decorators import admin_required
from app.utils.search import parse_search_terms, multi_term_filter

MEASUREMENTS_PER_PAGE = 15


def _can_access(measurement):
    """FR-MEAS-02: only Admin or the owning member may view/edit a record."""
    if current_user.role == UserRole.ADMIN:
        return True
    if current_user.role == UserRole.MEMBER:
        profile = current_user.member_profile
        return profile is not None and profile.id == measurement.member_id
    return False


def _own_member_profile_or_403():
    profile = current_user.member_profile
    if profile is None:
        abort(403)
    return profile


@measurements_bp.route('/')
@admin_required
def list_measurements():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()

    query = (
        Measurement.query
        .join(Member, Measurement.member_id == Member.id)
        .join(User, Member.user_id == User.id)
    )

    terms = parse_search_terms(search)
    if terms:
        query = query.filter(multi_term_filter(terms, [
            User.first_name, User.last_name, User.email,
        ]))

    records = query.order_by(
        Measurement.measured_on.desc(), Measurement.id.desc()
    ).paginate(page=page, per_page=MEASUREMENTS_PER_PAGE, error_out=False)

    today = date.today()
    stats = {
        'total': Measurement.query.count(),
        'members_tracked': db.session.query(
            db.func.count(db.func.distinct(Measurement.member_id))
        ).scalar() or 0,
        'this_month': Measurement.query.filter(
            Measurement.measured_on >= date(today.year, today.month, 1)
        ).count(),
    }

    return render_template(
        'measurements/list.html',
        records=records,
        search=search,
        stats=stats,
        title='Measurements',
    )


@measurements_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_measurement():
    if current_user.role not in (UserRole.ADMIN, UserRole.MEMBER):
        abort(403)

    is_member = current_user.role == UserRole.MEMBER
    form = MeasurementForm()

    if is_member:
        profile = _own_member_profile_or_403()
        form.member_id.choices = [(profile.id, profile.full_name)]
        form.member_id.data = profile.id
    else:
        members = (
            Member.query
            .join(User, Member.user_id == User.id)
            .filter(Member.is_archived == False)  # noqa: E712
            .order_by(User.first_name.asc())
            .all()
        )
        form.member_id.choices = [(m.id, f'{m.full_name} ({m.email})') for m in members]

        preselect_member_id = request.args.get('member_id', type=int)
        if request.method == 'GET' and preselect_member_id:
            form.member_id.data = preselect_member_id

    if request.method == 'GET' and not form.measured_on.data:
        form.measured_on.data = date.today()

    if form.validate_on_submit():
        if not form.has_any_value():
            flash('Enter at least one measurement value.', 'danger')
            return render_template(
                'measurements/create.html', form=form,
                is_member=is_member, title='Add Measurement',
            )

        record = Measurement(
            member_id=form.member_id.data,
            measured_on=form.measured_on.data,
            notes=form.notes.data.strip() or None,
            created_by_id=current_user.id,
        )
        for attr, _label, _unit in Measurement.VALUE_FIELDS:
            setattr(record, attr, getattr(form, attr).data)

        db.session.add(record)
        db.session.commit()

        flash('Measurement recorded.', 'success')
        return redirect(url_for('measurements.view_measurement', measurement_id=record.id))

    return render_template(
        'measurements/create.html', form=form,
        is_member=is_member, title='Add Measurement',
    )


@measurements_bp.route('/<int:measurement_id>')
@login_required
def view_measurement(measurement_id):
    record = Measurement.query.get_or_404(measurement_id)
    if not _can_access(record):
        abort(403)

    edit_logs = record.edit_logs.all()
    return render_template(
        'measurements/view.html',
        record=record,
        edit_logs=edit_logs,
        title=f'Measurement #{record.id}',
    )


@measurements_bp.route('/<int:measurement_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_measurement(measurement_id):
    """FR-MEAS-03: edits never overwrite silently — every changed field is logged."""
    record = Measurement.query.get_or_404(measurement_id)
    if not _can_access(record):
        abort(403)

    form = MeasurementForm(obj=record)
    form.member_id.choices = [(record.member_id, record.member.full_name)]
    form.member_id.data = record.member_id
    form.submit.label.text = 'Save Changes'

    if form.validate_on_submit():
        if not form.has_any_value():
            flash('Enter at least one measurement value.', 'danger')
            return render_template(
                'measurements/edit.html', form=form, record=record, title='Edit Measurement',
            )

        changes = _detect_changes(record, form)
        if not changes:
            flash('No changes detected.', 'info')
            return redirect(url_for('measurements.view_measurement', measurement_id=record.id))

        for field_name, old_val, new_val in changes:
            db.session.add(MeasurementEditLog(
                measurement_id=record.id,
                edited_by_id=current_user.id,
                field_name=field_name,
                old_value=old_val,
                new_value=new_val,
            ))

        record.measured_on = form.measured_on.data
        for attr, _label, _unit in Measurement.VALUE_FIELDS:
            setattr(record, attr, getattr(form, attr).data)
        record.notes = form.notes.data.strip() or None
        record.updated_by_id = current_user.id
        record.updated_at = datetime.utcnow()
        db.session.commit()

        flash(f'Measurement updated — {len(changes)} field(s) changed (logged).', 'success')
        return redirect(url_for('measurements.view_measurement', measurement_id=record.id))

    return render_template(
        'measurements/edit.html', form=form, record=record, title='Edit Measurement',
    )


@measurements_bp.route('/my-measurements')
@login_required
def my_measurements():
    if current_user.role == UserRole.ADMIN:
        return redirect(url_for('measurements.list_measurements'))
    if current_user.role != UserRole.MEMBER:
        abort(403)

    profile = _own_member_profile_or_403()

    page = request.args.get('page', 1, type=int)
    records = (
        Measurement.query
        .filter_by(member_id=profile.id)
        .order_by(Measurement.measured_on.desc(), Measurement.id.desc())
        .paginate(page=page, per_page=10, error_out=False)
    )

    # Weight trend (oldest → newest) for the chart
    trend_rows = (
        Measurement.query
        .filter(
            Measurement.member_id == profile.id,
            Measurement.weight_kg != None,  # noqa: E711
        )
        .order_by(Measurement.measured_on.asc(), Measurement.id.asc())
        .all()
    )
    trend = {
        'labels': [r.measured_on.strftime('%d %b %Y') for r in trend_rows],
        'weights': [float(r.weight_kg) for r in trend_rows],
    }

    latest = (
        Measurement.query
        .filter_by(member_id=profile.id)
        .order_by(Measurement.measured_on.desc(), Measurement.id.desc())
        .first()
    )

    return render_template(
        'measurements/my_measurements.html',
        records=records,
        trend=trend,
        latest=latest,
        title='My Measurements',
    )


def _detect_changes(record, form):
    """Return list of (field_name, old_str, new_str) for changed fields."""
    changes = []

    checks = [(
        'measured_on',
        record.measured_on.strftime('%Y-%m-%d'),
        form.measured_on.data.strftime('%Y-%m-%d'),
    )]
    for attr, _label, _unit in Measurement.VALUE_FIELDS:
        old = getattr(record, attr)
        new = getattr(form, attr).data
        checks.append((
            attr,
            '' if old is None else f'{old:.2f}',
            '' if new is None else f'{new:.2f}',
        ))
    checks.append(('notes', record.notes or '', form.notes.data.strip()))

    for field, old, new in checks:
        if old != new:
            changes.append((field, old or None, new or None))
    return changes