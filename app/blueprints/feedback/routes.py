import csv
import io
from datetime import datetime, date
from flask import (
    render_template, redirect, url_for, flash, request, abort, Response,
)
from flask_login import current_user, login_required

from app.blueprints.feedback import feedback_bp
from app.blueprints.feedback.forms import FeedbackSubmitForm, FeedbackRespondForm
from app.extensions import db
from app.models.feedback import Feedback, FeedbackCategory, FeedbackStatus
from app.models.member import Member
from app.models.user import User, UserRole
from app.utils.decorators import admin_required
from app.utils.search import parse_search_terms, multi_term_filter

FEEDBACK_PER_PAGE = 15


def _filtered_query(status_filter, category_filter, search):
    query = (
        Feedback.query
        .join(Member, Feedback.member_id == Member.id)
        .join(User, Member.user_id == User.id)
    )

    if status_filter != 'all':
        try:
            query = query.filter(Feedback.status == FeedbackStatus(status_filter))
        except ValueError:
            pass

    if category_filter:
        try:
            query = query.filter(Feedback.category == FeedbackCategory(category_filter))
        except ValueError:
            pass

    terms = parse_search_terms(search)
    if terms:
        query = query.filter(multi_term_filter(terms, [
            User.first_name, User.last_name, User.email,
        ]))
    return query


@feedback_bp.route('/')
@admin_required
def list_feedback():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'new')
    category_filter = request.args.get('category', '')
    search = request.args.get('search', '').strip()

    query = _filtered_query(status_filter, category_filter, search)
    records = query.order_by(Feedback.created_at.desc()).paginate(
        page=page, per_page=FEEDBACK_PER_PAGE, error_out=False
    )

    today = date.today()
    avg_rating = db.session.query(db.func.avg(Feedback.rating)).scalar()
    stats = {
        'total': Feedback.query.count(),
        'new': Feedback.query.filter_by(status=FeedbackStatus.NEW).count(),
        'avg_rating': round(float(avg_rating), 1) if avg_rating is not None else None,
        'this_month': Feedback.query.filter(
            Feedback.created_at >= datetime(today.year, today.month, 1)
        ).count(),
    }

    return render_template(
        'feedback/list.html',
        records=records,
        status_filter=status_filter,
        category_filter=category_filter,
        search=search,
        stats=stats,
        statuses=list(FeedbackStatus),
        categories=list(FeedbackCategory),
        title='Feedback',
    )


@feedback_bp.route('/submit', methods=['GET', 'POST'])
@login_required
def submit_feedback():
    if current_user.role != UserRole.MEMBER:
        abort(403)

    profile = current_user.member_profile
    if profile is None:
        abort(403)

    # FR-FDB-04: only active members can send feedback
    if not profile.is_active_member:
        flash('Feedback can only be submitted with an active membership.', 'warning')
        return redirect(url_for('dashboard.home'))

    form = FeedbackSubmitForm()

    if form.validate_on_submit():
        record = Feedback(
            member_id=profile.id,
            category=FeedbackCategory(form.category.data) if form.category.data else None,
            rating=int(form.rating.data),
            comments=form.comments.data.strip(),
        )
        db.session.add(record)
        db.session.commit()

        flash('Thank you — your feedback has been submitted.', 'success')
        return redirect(url_for('feedback.my_feedback'))

    return render_template('feedback/submit.html', form=form, title='Submit Feedback')


@feedback_bp.route('/<int:feedback_id>')
@login_required
def view_feedback(feedback_id):
    record = Feedback.query.get_or_404(feedback_id)

    if current_user.role == UserRole.MEMBER:
        if not current_user.member_profile or current_user.member_profile.id != record.member_id:
            abort(403)
    elif current_user.role != UserRole.ADMIN:
        abort(403)

    respond_form = None
    if current_user.role == UserRole.ADMIN:
        respond_form = FeedbackRespondForm(obj=record)
        if request.method == 'GET':
            respond_form.status.data = record.status.value

    return render_template(
        'feedback/view.html',
        record=record,
        respond_form=respond_form,
        title=f'Feedback #{record.id}',
    )


@feedback_bp.route('/<int:feedback_id>/respond', methods=['POST'])
@admin_required
def respond_feedback(feedback_id):
    record = Feedback.query.get_or_404(feedback_id)
    form = FeedbackRespondForm()

    if form.validate_on_submit():
        response_text = form.admin_response.data.strip() or None

        record.status = FeedbackStatus(form.status.data)
        if response_text != record.admin_response:
            record.admin_response = response_text
            if response_text:
                record.responded_by_id = current_user.id
                record.responded_at = datetime.utcnow()
            else:
                record.responded_by_id = None
                record.responded_at = None
        record.updated_at = datetime.utcnow()
        db.session.commit()

        flash('Feedback updated.', 'success')
    else:
        flash('Could not update feedback — check the form values.', 'danger')

    return redirect(url_for('feedback.view_feedback', feedback_id=record.id))


@feedback_bp.route('/my-feedback')
@login_required
def my_feedback():
    if current_user.role == UserRole.ADMIN:
        return redirect(url_for('feedback.list_feedback'))
    if current_user.role != UserRole.MEMBER:
        abort(403)

    profile = current_user.member_profile
    if profile is None:
        abort(403)

    page = request.args.get('page', 1, type=int)
    records = (
        Feedback.query
        .filter_by(member_id=profile.id)
        .order_by(Feedback.created_at.desc())
        .paginate(page=page, per_page=10, error_out=False)
    )

    return render_template(
        'feedback/my_feedback.html',
        records=records,
        can_submit=profile.is_active_member,
        title='My Feedback',
    )


@feedback_bp.route('/export')
@admin_required
def export_feedback():
    """FR-FDB-03: CSV feedback report, honouring the current list filters."""
    status_filter = request.args.get('status', 'all')
    category_filter = request.args.get('category', '')
    search = request.args.get('search', '').strip()

    rows = (
        _filtered_query(status_filter, category_filter, search)
        .order_by(Feedback.created_at.desc())
        .all()
    )

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([
        'ID', 'Member', 'Email', 'Date', 'Category', 'Rating',
        'Comments', 'Status', 'Response', 'Responded By', 'Responded At',
    ])
    for r in rows:
        writer.writerow([
            r.id,
            r.member.full_name,
            r.member.email,
            r.created_at.strftime('%Y-%m-%d %H:%M'),
            r.category_label,
            r.rating,
            r.comments,
            r.status.label,
            r.admin_response or '',
            r.responded_by.full_name if r.responded_by else '',
            r.responded_at.strftime('%Y-%m-%d %H:%M') if r.responded_at else '',
        ])

    filename = f'feedback_report_{date.today().strftime("%Y%m%d")}.csv'
    return Response(
        out.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )
