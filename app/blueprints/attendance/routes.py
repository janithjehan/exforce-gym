from datetime import datetime, date, timedelta
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import current_user, login_required

from app.blueprints.attendance import attendance_bp
from app.blueprints.attendance.forms import AttendanceCreateForm
from app.extensions import db
from app.models.attendance import Attendance
from app.models.member import Member
from app.models.user import User, UserRole
from app.utils.decorators import admin_manager_or_trainer_required
from app.utils.search import parse_search_terms, multi_term_filter

ATTENDANCE_PER_PAGE = 20


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

        record = Attendance(
            member_id=form.member_id.data,
            check_in=form.check_in.data,
            check_out=check_out,
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
