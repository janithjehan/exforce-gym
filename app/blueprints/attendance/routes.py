import io
from datetime import datetime, date, timedelta
from flask import render_template, redirect, url_for, flash, request, abort, Response
from flask_login import current_user, login_required
from openpyxl import Workbook
from openpyxl.styles import Font

from app.blueprints.attendance import attendance_bp
from app.blueprints.attendance.forms import AttendanceCreateForm
from app.extensions import db
from app.models.attendance import Attendance
from app.models.trainer_request import TrainerRequest, TrainerRequestStatus
from app.models.user import User, UserRole
from app.utils.decorators import admin_manager_or_trainer_required
from app.utils.search import parse_search_terms, multi_term_filter
from app.utils.timezones import to_utc, to_local

ATTENDANCE_PER_PAGE = 20
SCAN_DEBOUNCE_SECONDS = 8  # ignore a repeat scan/entry of the same id within this window


def _filtered_attendance_query(base_query, search, role_filter, date_from, date_to):
    """Builds the shared Attendance query (search/role/date filters) used by both list_attendance and export_attendance."""
    query = base_query

    terms = parse_search_terms(search)
    if terms:
        query = query.filter(multi_term_filter(terms, [
            User.first_name, User.last_name,
        ]))

    if role_filter:
        try:
            query = query.filter(User.role == UserRole(role_filter))
        except ValueError:
            pass

    if date_from:
        try:
            start = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(db.func.date(Attendance.check_in) >= start)
        except ValueError:
            pass

    if date_to:
        try:
            end = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(db.func.date(Attendance.check_in) <= end)
        except ValueError:
            pass

    return query


def _trainer_assigned_user_ids(trainer):
    """User ids of members currently assigned to this trainer (accepted requests).
    Mirrors trainer_requests.routes.my_members()'s query."""
    if not trainer:
        return []
    return [
        req.member.user_id
        for req in trainer.trainer_requests.filter(
            TrainerRequest.status == TrainerRequestStatus.ACCEPTED
        ).all()
    ]


def _attendance_base_query():
    """Attendance joined to User, scoped to a Trainer's assigned members only
    (Admin/Manager see everyone). Shared by list_attendance and export_attendance
    so the two can never drift out of sync on who's visible to whom."""
    base_query = Attendance.query.join(User, Attendance.user_id == User.id)

    if current_user.role == UserRole.TRAINER:
        assigned_ids = _trainer_assigned_user_ids(current_user.trainer_profile)
        base_query = base_query.filter(Attendance.user_id.in_(assigned_ids or [-1]))

    return base_query


@attendance_bp.route('/')
@admin_manager_or_trainer_required
def list_attendance():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    role_filter = request.args.get('role', '')

    base_query = _attendance_base_query()
    query = _filtered_attendance_query(base_query, search, role_filter, date_from, date_to)

    records = query.order_by(Attendance.check_in.desc()).paginate(
        page=page, per_page=ATTENDANCE_PER_PAGE, error_out=False
    )

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    stats = {
        'today': base_query.filter(
            db.func.date(Attendance.check_in) == today
        ).count(),
        'this_week': base_query.filter(
            db.func.date(Attendance.check_in) >= week_start
        ).count(),
        'checked_in': base_query.filter(
            Attendance.check_out == None  # noqa: E711
        ).count(),
        'total': base_query.count(),
    }

    return render_template(
        'attendance/list.html',
        records=records,
        search=search,
        date_from=date_from,
        date_to=date_to,
        role_filter=role_filter,
        user_roles=UserRole,
        stats=stats,
        title='Attendance',
    )


@attendance_bp.route('/export')
@admin_manager_or_trainer_required
def export_attendance():
    """Excel (.xlsx) export of the attendance list, honouring the current list filters
    (search/role/date range) and the same Trainer scoping as list_attendance."""
    search = request.args.get('search', '').strip()
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    role_filter = request.args.get('role', '')

    base_query = _attendance_base_query()
    records = (
        _filtered_attendance_query(base_query, search, role_filter, date_from, date_to)
        .order_by(Attendance.check_in.desc())
        .all()
    )

    wb = Workbook()
    ws = wb.active
    ws.title = 'Attendance'

    headers = [
        'ID', 'Name', 'Role', 'Check-In', 'Check-Out', 'Duration', 'Notes', 'Recorded By',
    ]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for record in records:
        ws.append([
            record.id,
            record.user.full_name,
            record.user.role.label,
            to_local(record.check_in).strftime('%Y-%m-%d %H:%M'),
            to_local(record.check_out).strftime('%Y-%m-%d %H:%M') if record.check_out else '',
            record.duration_label,
            record.notes or '',
            record.created_by.full_name if record.created_by else '',
        ])

    for col in ws.columns:
        max_len = max((len(str(c.value)) for c in col if c.value is not None), default=8)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 40)

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)

    filename = f'attendance_report_{date.today().strftime("%Y%m%d")}.xlsx'
    return Response(
        out.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )


@attendance_bp.route('/create', methods=['GET', 'POST'])
@admin_manager_or_trainer_required
def create_attendance():
    form = AttendanceCreateForm()

    if current_user.role == UserRole.TRAINER:
        assigned_ids = _trainer_assigned_user_ids(current_user.trainer_profile)
        users = (
            User.query
            .filter(
                User.id.in_(assigned_ids or [-1]),
                User.is_active == True, User.is_archived == False,  # noqa: E712
            )
            .order_by(User.first_name.asc())
            .all()
        )
    else:
        users = (
            User.query
            .filter(User.is_active == True, User.is_archived == False)  # noqa: E712
            .order_by(User.role.asc(), User.first_name.asc())
            .all()
        )
    form.user_id.choices = [(u.id, f'{u.full_name} ({u.role.label})') for u in users]

    preselect_user_id = request.args.get('user_id', type=int)
    if request.method == 'GET' and preselect_user_id:
        form.user_id.data = preselect_user_id

    if form.validate_on_submit():
        check_out = form.check_out.data or None
        if check_out and check_out <= form.check_in.data:
            flash('Check-out time must be after check-in time.', 'danger')
            return render_template('attendance/create.html', form=form, title='Record Attendance')

        # Staff enter times in local (Sri Lanka) time; persist as UTC like
        # everything else (checkout uses utcnow, displays convert back).
        record = Attendance(
            user_id=form.user_id.data,
            check_in=to_utc(form.check_in.data),
            check_out=to_utc(check_out),
            notes=form.notes.data.strip() or None,
            created_by_id=current_user.id,
        )
        db.session.add(record)
        db.session.commit()

        person = User.query.get(record.user_id)
        flash(f'Attendance recorded for {person.full_name}.', 'success')
        return redirect(url_for('attendance.view_attendance', attendance_id=record.id))

    return render_template('attendance/create.html', form=form, title='Record Attendance')


@attendance_bp.route('/<int:attendance_id>')
@login_required
def view_attendance(attendance_id):
    record = Attendance.query.get_or_404(attendance_id)

    # Anyone can view their own record. A Member is restricted to their own;
    # a Trainer is restricted to their own + their assigned members' (mirrors
    # the same scoping as list_attendance, so this can't be bypassed via a
    # direct URL). Admin/Manager keep full access via the route decorator.
    if current_user.role == UserRole.MEMBER and record.user_id != current_user.id:
        abort(403)
    if current_user.role == UserRole.TRAINER:
        allowed_ids = _trainer_assigned_user_ids(current_user.trainer_profile) + [current_user.id]
        if record.user_id not in allowed_ids:
            abort(403)

    return render_template(
        'attendance/view.html',
        record=record,
        title=f'Attendance #{record.id}',
    )


@attendance_bp.route('/<int:attendance_id>/checkout', methods=['POST'])
@admin_manager_or_trainer_required
def checkout(attendance_id):
    record = Attendance.query.get_or_404(attendance_id)

    if current_user.role == UserRole.TRAINER:
        allowed_ids = _trainer_assigned_user_ids(current_user.trainer_profile) + [current_user.id]
        if record.user_id not in allowed_ids:
            abort(403)

    if record.is_checked_out:
        flash('This record already has a check-out time.', 'warning')
        return redirect(url_for('attendance.view_attendance', attendance_id=record.id))

    record.check_out = datetime.utcnow().replace(microsecond=0)
    record.updated_by_id = current_user.id
    record.updated_at = datetime.utcnow()
    db.session.commit()

    flash(f'Check-out recorded for {record.user.full_name}.', 'success')
    return redirect(url_for('attendance.view_attendance', attendance_id=record.id))


@attendance_bp.route('/scan')
@admin_manager_or_trainer_required
def scan_kiosk():
    """Reception page — leave this open at the front desk. Staff type in
    whoever's checking in/out's ID (shown on each person's own dashboard) and
    press Enter; a USB/Bluetooth barcode-style keyboard-wedge device works
    too since it just types digits + Enter into the same field."""
    return render_template('attendance/scan.html', title='Attendance Scan')


@attendance_bp.route('/scan', methods=['POST'])
@admin_manager_or_trainer_required
def scan_submit():
    """Plain form POST from the kiosk page for every entered id — no JS.
    Toggles check-in/check-out on the Attendance model: the person's most
    recent Attendance row today with no check_out yet means this entry is a
    check-out; otherwise it's a new check-in. Whichever entry ends up being
    the person's last one for the day is therefore the checkout, with no
    special "end of day" logic needed. Works the same for any role — Admin,
    Manager, Trainer, or Member — keyed by their User id. Result is shown via
    a flash message after redirecting back to the kiosk page."""
    raw_code = request.form.get('code', '').strip()

    if not raw_code.isdigit():
        flash('Unrecognized ID.', 'danger')
        return redirect(url_for('attendance.scan_kiosk'))

    user = User.query.get(int(raw_code))
    if not user:
        flash('ID not recognized.', 'danger')
        return redirect(url_for('attendance.scan_kiosk'))
    if not user.is_active_account:
        flash(f'{user.full_name}: account is inactive.', 'danger')
        return redirect(url_for('attendance.scan_kiosk'))

    now = datetime.utcnow().replace(microsecond=0)
    latest = user.attendances.first()

    # Debounce — ignore a repeat entry of the same id within a couple of
    # seconds (e.g. a handheld scanner double-firing).
    last_event_at = (latest.check_out or latest.check_in) if latest else None
    if last_event_at and (now - last_event_at).total_seconds() < SCAN_DEBOUNCE_SECONDS:
        flash(f'{user.full_name} - already recorded, please wait a moment.', 'warning')
        return redirect(url_for('attendance.scan_kiosk'))

    if latest and latest.check_in.date() == now.date() and latest.check_out is None:
        latest.check_out = now
        latest.updated_by_id = current_user.id
        latest.updated_at = now
        db.session.commit()
        flash(f'{user.full_name} - checked out at {to_local(now).strftime("%H:%M")}.', 'primary')
        return redirect(url_for('attendance.scan_kiosk'))

    record = Attendance(
        user_id=user.id,
        check_in=now,
        created_by_id=current_user.id,
    )
    db.session.add(record)
    db.session.commit()
    flash(f'{user.full_name} - checked in at {to_local(now).strftime("%H:%M")}.', 'success')
    return redirect(url_for('attendance.scan_kiosk'))


@attendance_bp.route('/my-attendance')
@login_required
def my_attendance():
    """Self-service attendance history — available to every role now that
    Attendance is keyed by User id, not just Member."""
    page = request.args.get('page', 1, type=int)
    records = (
        Attendance.query
        .filter_by(user_id=current_user.id)
        .order_by(Attendance.check_in.desc())
        .paginate(page=page, per_page=ATTENDANCE_PER_PAGE, error_out=False)
    )

    return render_template(
        'attendance/my_attendance.html',
        records=records,
        title='My Attendance',
    )
