from datetime import datetime, date, timedelta
from flask import render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import current_user, login_required

from app.blueprints.attendance import attendance_bp
from app.blueprints.attendance.forms import AttendanceCreateForm
from app.extensions import db
from app.models.attendance import Attendance
from app.models.member import Member
from app.models.user import User, UserRole
from app.utils.decorators import admin_manager_or_trainer_required
from app.utils.search import parse_search_terms, multi_term_filter
from app.utils.timezones import to_utc, to_local

ATTENDANCE_PER_PAGE = 20
SCAN_DEBOUNCE_SECONDS = 8  # ignore a repeat scan of the same member's card within this window


@attendance_bp.route('/')
@admin_manager_or_trainer_required
def list_attendance():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    date_filter = request.args.get('date', '')

    query = (
        Attendance.query
        .join(Member, Attendance.member_id == Member.id)
        .join(User, Member.user_id == User.id)
    )

    terms = parse_search_terms(search)
    if terms:
        query = query.filter(multi_term_filter(terms, [
            User.first_name, User.last_name,
        ]))

    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            query = query.filter(db.func.date(Attendance.check_in) == filter_date)
        except ValueError:
            pass

    records = query.order_by(Attendance.check_in.desc()).paginate(
        page=page, per_page=ATTENDANCE_PER_PAGE, error_out=False
    )

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    stats = {
        'today': Attendance.query.filter(
            db.func.date(Attendance.check_in) == today
        ).count(),
        'this_week': Attendance.query.filter(
            db.func.date(Attendance.check_in) >= week_start
        ).count(),
        'checked_in': Attendance.query.filter(
            Attendance.check_out == None  # noqa: E711
        ).count(),
        'total': Attendance.query.count(),
    }

    return render_template(
        'attendance/list.html',
        records=records,
        search=search,
        date_filter=date_filter,
        stats=stats,
        title='Attendance',
    )


@attendance_bp.route('/create', methods=['GET', 'POST'])
@admin_manager_or_trainer_required
def create_attendance():
    form = AttendanceCreateForm()

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

    if form.validate_on_submit():
        check_out = form.check_out.data or None
        if check_out and check_out <= form.check_in.data:
            flash('Check-out time must be after check-in time.', 'danger')
            return render_template('attendance/create.html', form=form, title='Record Attendance')

        # Staff enter times in local (Sri Lanka) time; persist as UTC like
        # everything else (checkout uses utcnow, displays convert back).
        record = Attendance(
            member_id=form.member_id.data,
            check_in=to_utc(form.check_in.data),
            check_out=to_utc(check_out),
            notes=form.notes.data.strip() or None,
            created_by_id=current_user.id,
        )
        db.session.add(record)
        db.session.commit()

        member = Member.query.get(record.member_id)
        flash(f'Attendance recorded for {member.full_name}.', 'success')
        return redirect(url_for('attendance.view_attendance', attendance_id=record.id))

    return render_template('attendance/create.html', form=form, title='Record Attendance')


@attendance_bp.route('/<int:attendance_id>')
@login_required
def view_attendance(attendance_id):
    record = Attendance.query.get_or_404(attendance_id)

    if current_user.role == UserRole.MEMBER:
        if not current_user.member_profile or current_user.member_profile.id != record.member_id:
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

    if record.is_checked_out:
        flash('This record already has a check-out time.', 'warning')
        return redirect(url_for('attendance.view_attendance', attendance_id=record.id))

    record.check_out = datetime.utcnow()
    record.updated_by_id = current_user.id
    record.updated_at = datetime.utcnow()
    db.session.commit()

    flash(f'Check-out recorded for {record.member.full_name}.', 'success')
    return redirect(url_for('attendance.view_attendance', attendance_id=record.id))


@attendance_bp.route('/scan')
@admin_manager_or_trainer_required
def scan_kiosk():
    """Kiosk page — a laptop/tablet browser left open at reception, decoding
    printed member QR cards via the device camera. Runs entirely offline:
    jsQR is vendored under app/static/vendor (no CDN), and the page is meant
    to be opened at http://localhost so camera access works with no HTTPS
    setup (browsers only grant camera access on a secure context — localhost
    is exempt, a plain LAN address is not)."""
    return render_template('attendance/scan.html', title='Attendance Scan')


@attendance_bp.route('/scan', methods=['POST'])
@admin_manager_or_trainer_required
def scan_submit():
    """JSON API called by the kiosk page for every decoded QR code. Toggles
    check-in/check-out on the existing Attendance model — no schema change:
    the member's most recent Attendance row today with no check_out yet means
    this scan is a check-out; otherwise it's a new check-in. Whichever scan
    ends up being the member's last one for the day is therefore the checkout,
    with no special "end of day" logic needed."""
    payload = request.get_json(silent=True) or {}
    raw_code = str(payload.get('code', '')).strip()

    if not raw_code.isdigit():
        return jsonify(ok=False, message='Unrecognized code.'), 400

    member = Member.query.get(int(raw_code))
    if not member or member.is_archived:
        return jsonify(ok=False, message='Card not recognized — member not found.'), 404
    if not member.user.is_active:
        return jsonify(ok=False, message=f'{member.full_name}: account is inactive.'), 403

    now = datetime.utcnow()
    latest = member.attendances.first()

    # Debounce — ignore a repeat decode of the same card held in front of the
    # camera for a couple of seconds, which would otherwise flap check-in/out.
    last_event_at = (latest.check_out or latest.check_in) if latest else None
    if last_event_at and (now - last_event_at).total_seconds() < SCAN_DEBOUNCE_SECONDS:
        action = 'check_out' if latest.check_out else 'check_in'
        return jsonify(
            ok=True, duplicate=True, action=action, member=member.full_name,
            message=f'{member.full_name} — already recorded, please wait a moment.',
        )

    if latest and latest.check_in.date() == now.date() and latest.check_out is None:
        latest.check_out = now
        latest.updated_by_id = current_user.id
        latest.updated_at = now
        db.session.commit()
        return jsonify(
            ok=True, action='check_out', member=member.full_name,
            time=to_local(now).strftime('%H:%M'),
            message=f'{member.full_name} — checked out.',
        )

    record = Attendance(
        member_id=member.id,
        check_in=now,
        created_by_id=current_user.id,
    )
    db.session.add(record)
    db.session.commit()
    return jsonify(
        ok=True, action='check_in', member=member.full_name,
        time=to_local(now).strftime('%H:%M'),
        message=f'{member.full_name} — checked in.',
    )


@attendance_bp.route('/my-attendance')
@login_required
def my_attendance():
    if current_user.role in (UserRole.ADMIN, UserRole.MANAGER, UserRole.TRAINER):
        return redirect(url_for('attendance.list_attendance'))

    if not current_user.member_profile:
        abort(403)

    page = request.args.get('page', 1, type=int)
    records = (
        Attendance.query
        .filter_by(member_id=current_user.member_profile.id)
        .order_by(Attendance.check_in.desc())
        .paginate(page=page, per_page=ATTENDANCE_PER_PAGE, error_out=False)
    )

    return render_template(
        'attendance/my_attendance.html',
        records=records,
        title='My Attendance',
    )
