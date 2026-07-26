"""Trainer Request module.

A member requests a specific trainer; the trainer (or an Admin) accepts or
rejects. An accepted request is the member↔trainer assignment surfaced to the
trainer as "My Members". All notifications reuse the in-app Notifications
system (topbar bell / inbox), mirroring the bank-transfer membership flow.

Access summary:
- Member: request / cancel / leave, and view own request.
- Trainer: incoming requests, accept/reject own, My Members, remove own member.
- Admin: full oversight list + accept/reject any.
- Manager: read-only oversight list (no accept/reject) — they still get a bell
  notification for new requests, so the list link must be openable by them.
"""
from datetime import datetime, date
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import current_user, login_required

from app.blueprints.trainer_requests import trainer_requests_bp
from app.extensions import db
from app.models.member import Member
from app.models.membership import Membership, MembershipStatus
from app.models.trainer import Trainer
from app.models.trainer_request import TrainerRequest, TrainerRequestStatus
from app.models.user import User, UserRole
from app.utils.decorators import (
    admin_or_manager_required, trainer_required,
)
from app.utils.search import parse_search_terms, multi_term_filter

REQUESTS_PER_PAGE = 15


# ─────────────────────────── access helpers ──────────────────────────── #

def _owning_trainer(req):
    """True if the current user is the trainer this request is directed to."""
    return (
        current_user.is_trainer
        and current_user.trainer_profile is not None
        and req.trainer_id == current_user.trainer_profile.id
    )


def _owning_member(req):
    return (
        current_user.is_member
        and current_user.member_profile is not None
        and req.member_id == current_user.member_profile.id
    )


def _can_act(req):
    """Who may Accept/Reject: Admin, or the trainer the request is for."""
    return current_user.is_admin or _owning_trainer(req)


def _can_view(req):
    """Who may open the request detail: Admin/Manager, the owning trainer, or
    the owning member."""
    return (
        current_user.is_admin or current_user.is_manager
        or _owning_trainer(req) or _owning_member(req)
    )


def _active_membership(member):
    return (
        Membership.query
        .filter(
            Membership.member_id == member.id,
            Membership.status == MembershipStatus.ACTIVE,
            Membership.end_date >= date.today(),
        )
        .order_by(Membership.end_date.desc())
        .first()
    )


# ═══════════════════════════ Member routes ═══════════════════════════ #

@trainer_requests_bp.route('/find')
@login_required
def find_trainer():
    """Member: browse available trainers and request one. If the member already
    has an open request, bounce to their request page."""
    if not current_user.is_member:
        abort(403)
    if not current_user.member_profile:
        flash('Your member profile is not set up yet. Please contact the gym.', 'warning')
        return redirect(url_for('dashboard.home'))

    existing = TrainerRequest.open_for_member(current_user.member_profile.id)
    if existing:
        flash('You already have an active trainer request.', 'info')
        return redirect(url_for('trainer_requests.my_request'))

    trainers = (
        Trainer.query
        .join(User, Trainer.user_id == User.id)
        .filter(Trainer.is_archived == False, User.is_active == True)
        .order_by(User.first_name.asc())
        .all()
    )
    return render_template('trainer_requests/find.html', trainers=trainers, title='Find a Trainer')


@trainer_requests_bp.route('/request', methods=['POST'])
@login_required
def submit_request():
    """Member: submit a request for the chosen trainer."""
    if not current_user.is_member:
        abort(403)
    member = current_user.member_profile
    if not member:
        flash('Your member profile is not set up yet. Please contact the gym.', 'warning')
        return redirect(url_for('dashboard.home'))

    # Guard: only one open request at a time (pending or accepted).
    if TrainerRequest.open_for_member(member.id):
        flash('You already have an active trainer request.', 'warning')
        return redirect(url_for('trainer_requests.my_request'))

    trainer_id = request.form.get('trainer_id', type=int)
    trainer = Trainer.query.get(trainer_id) if trainer_id else None
    if not trainer or trainer.is_archived or not trainer.user.is_active:
        flash('That trainer is not available. Please choose another.', 'danger')
        return redirect(url_for('trainer_requests.find_trainer'))

    req = TrainerRequest(
        member_id=member.id,
        trainer_id=trainer.id,
        status=TrainerRequestStatus.PENDING,
        message=(request.form.get('message', '') or '').strip() or None,
    )
    db.session.add(req)
    db.session.commit()

    _notify_new_request(req)

    flash(f'Your request has been sent to {trainer.full_name}. You will be notified when they respond.', 'success')
    return redirect(url_for('trainer_requests.my_request'))


@trainer_requests_bp.route('/my')
@login_required
def my_request():
    """Member: current request status + full history."""
    if not current_user.is_member:
        abort(403)
    member = current_user.member_profile
    if not member:
        flash('Your member profile is not set up yet. Please contact the gym.', 'warning')
        return redirect(url_for('dashboard.home'))

    current = TrainerRequest.open_for_member(member.id)
    history = member.trainer_requests.all()
    return render_template(
        'trainer_requests/my.html',
        current=current, history=history, title='My Trainer',
    )


@trainer_requests_bp.route('/<int:request_id>/cancel', methods=['POST'])
@login_required
def cancel_request(request_id):
    """Member: withdraw a still-pending request."""
    req = TrainerRequest.query.get_or_404(request_id)
    if not _owning_member(req):
        abort(403)
    if req.status != TrainerRequestStatus.PENDING:
        flash('Only a pending request can be cancelled.', 'warning')
        return redirect(url_for('trainer_requests.my_request'))

    req.status = TrainerRequestStatus.CANCELLED
    req.ended_at = datetime.utcnow()
    req.ended_by_id = current_user.id
    db.session.commit()

    _notify_trainer_of_member_action(req, 'cancel')
    flash('Your trainer request has been cancelled. You can request another anytime.', 'secondary')
    return redirect(url_for('trainer_requests.find_trainer'))


@trainer_requests_bp.route('/<int:request_id>/leave', methods=['POST'])
@login_required
def leave_trainer(request_id):
    """Member: end an accepted assignment (frees them to request another)."""
    req = TrainerRequest.query.get_or_404(request_id)
    if not _owning_member(req):
        abort(403)
    if req.status != TrainerRequestStatus.ACCEPTED:
        flash('You can only leave a trainer you are currently assigned to.', 'warning')
        return redirect(url_for('trainer_requests.my_request'))

    req.status = TrainerRequestStatus.ENDED
    req.ended_at = datetime.utcnow()
    req.ended_by_id = current_user.id
    db.session.commit()

    _notify_trainer_of_member_action(req, 'leave')
    flash('You have left your trainer. You can request a new trainer anytime.', 'secondary')
    return redirect(url_for('trainer_requests.find_trainer'))


# ═══════════════════════════ Trainer routes ═══════════════════════════ #

@trainer_requests_bp.route('/incoming')
@trainer_required
def incoming():
    """Trainer: pending requests directed to me, plus recent responded ones."""
    trainer = current_user.trainer_profile
    if not trainer:
        flash('Your trainer profile is not set up yet. Please contact an admin.', 'warning')
        return redirect(url_for('dashboard.home'))

    pending = (
        trainer.trainer_requests
        .filter(TrainerRequest.status == TrainerRequestStatus.PENDING)
        .all()
    )
    recent = (
        trainer.trainer_requests
        .filter(TrainerRequest.status != TrainerRequestStatus.PENDING)
        .limit(10)
        .all()
    )
    return render_template(
        'trainer_requests/incoming.html',
        pending=pending, recent=recent, title='Trainer Requests',
    )


@trainer_requests_bp.route('/my-members')
@trainer_required
def my_members():
    """Trainer: members currently assigned to me (accepted requests)."""
    trainer = current_user.trainer_profile
    if not trainer:
        flash('Your trainer profile is not set up yet. Please contact an admin.', 'warning')
        return redirect(url_for('dashboard.home'))

    assignments = (
        trainer.trainer_requests
        .filter(TrainerRequest.status == TrainerRequestStatus.ACCEPTED)
        .all()
    )
    return render_template(
        'trainer_requests/my_members.html',
        assignments=assignments, title='My Members',
    )


@trainer_requests_bp.route('/<int:request_id>/remove', methods=['POST'])
@login_required
def remove_member(request_id):
    """Trainer (or Admin): end an accepted assignment from the staff side."""
    req = TrainerRequest.query.get_or_404(request_id)
    if not _can_act(req):
        abort(403)
    if req.status != TrainerRequestStatus.ACCEPTED:
        flash('Only an active assignment can be removed.', 'warning')
        return redirect(url_for('trainer_requests.my_members'))

    req.status = TrainerRequestStatus.ENDED
    req.ended_at = datetime.utcnow()
    req.ended_by_id = current_user.id
    db.session.commit()

    _notify_member_of_removal(req)
    flash(f'{req.member.full_name} has been removed from your members.', 'secondary')
    return redirect(url_for('trainer_requests.my_members'))


# ═══════════════════ Shared detail + accept / reject ═══════════════════ #

@trainer_requests_bp.route('/<int:request_id>')
@login_required
def view_request(request_id):
    """Detail page: the request + the member's full details. Trainer/Admin can
    act here; Manager and the member view read-only."""
    req = TrainerRequest.query.get_or_404(request_id)
    if not _can_view(req):
        abort(403)

    member = req.member
    active_membership = _active_membership(member)
    recent_attendance = member.attendances.limit(5).all()

    return render_template(
        'trainer_requests/detail.html',
        req=req,
        member=member,
        active_membership=active_membership,
        recent_attendance=recent_attendance,
        can_act=_can_act(req),
        title=f'Trainer Request #{req.id}',
    )


@trainer_requests_bp.route('/<int:request_id>/accept', methods=['POST'])
@login_required
def accept_request(request_id):
    req = TrainerRequest.query.get_or_404(request_id)
    if not _can_act(req):
        abort(403)
    if req.status != TrainerRequestStatus.PENDING:
        flash('Only a pending request can be accepted.', 'warning')
        return redirect(url_for('trainer_requests.view_request', request_id=req.id))

    req.status = TrainerRequestStatus.ACCEPTED
    req.responded_at = datetime.utcnow()
    req.responded_by_id = current_user.id
    db.session.commit()

    _notify_member_of_response(req, accepted=True)
    flash(f'Request accepted. {req.member.full_name} is now one of your members.', 'success')
    return redirect(url_for('trainer_requests.view_request', request_id=req.id))


@trainer_requests_bp.route('/<int:request_id>/reject', methods=['POST'])
@login_required
def reject_request(request_id):
    req = TrainerRequest.query.get_or_404(request_id)
    if not _can_act(req):
        abort(403)
    if req.status != TrainerRequestStatus.PENDING:
        flash('Only a pending request can be rejected.', 'warning')
        return redirect(url_for('trainer_requests.view_request', request_id=req.id))

    req.status = TrainerRequestStatus.REJECTED
    req.response_note = (request.form.get('response_note', '') or '').strip() or None
    req.responded_at = datetime.utcnow()
    req.responded_by_id = current_user.id
    db.session.commit()

    _notify_member_of_response(req, accepted=False)
    flash('Request rejected. The member has been notified.', 'secondary')
    return redirect(url_for('trainer_requests.view_request', request_id=req.id))


# ═══════════════════════════ Admin oversight ═══════════════════════════ #

@trainer_requests_bp.route('/')
@admin_or_manager_required
def list_requests():
    """Admin (act) + Manager (view-only): all trainer requests."""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'pending')
    search = request.args.get('search', '').strip()

    query = (
        TrainerRequest.query
        .join(Member, TrainerRequest.member_id == Member.id)
        .join(User, Member.user_id == User.id)
    )

    terms = parse_search_terms(search)
    if terms:
        query = query.filter(multi_term_filter(terms, [
            User.first_name, User.last_name, User.email,
        ]))

    if status_filter in [s.value for s in TrainerRequestStatus]:
        query = query.filter(TrainerRequest.status == TrainerRequestStatus(status_filter))

    requests_page = query.order_by(TrainerRequest.requested_at.desc()).paginate(
        page=page, per_page=REQUESTS_PER_PAGE, error_out=False
    )

    stats = {
        'pending': TrainerRequest.query.filter_by(status=TrainerRequestStatus.PENDING).count(),
        'accepted': TrainerRequest.query.filter_by(status=TrainerRequestStatus.ACCEPTED).count(),
        'total': TrainerRequest.query.count(),
    }

    return render_template(
        'trainer_requests/list.html',
        requests=requests_page,
        status_filter=status_filter,
        search=search,
        stats=stats,
        statuses=TrainerRequestStatus,
        title='Trainer Requests',
    )


# ─────────────────────────── notifications ──────────────────────────── #

def _notify_new_request(req):
    """New request → the chosen trainer (direct) + all admins/managers."""
    from app.models.notification import Notification, NotificationAudience
    from app.blueprints.notifications.service import resolve_audience, dispatch_notification

    member_name = req.member.full_name
    trainer_name = req.trainer.full_name

    # 1) the chosen trainer — deep-links to the request they must action
    trainer_msg = f'{member_name} has requested you as their personal trainer.'
    if req.message:
        trainer_msg += f'\n\nTheir message: {req.message}'
    trainer_msg += '\n\nOpen the request to view their details and accept or reject it.'

    n_trainer = Notification(
        title='New Trainer Request',
        message=trainer_msg,
        audience=NotificationAudience.SINGLE_TRAINER,
        is_auto=False,
        link_url=url_for('trainer_requests.view_request', request_id=req.id),
        created_by_id=req.member.user_id,
    )
    db.session.add(n_trainer)
    db.session.flush()
    dispatch_notification(n_trainer, [req.trainer.user])

    # 2) admins + managers — oversight, deep-links to the requests list
    staff = resolve_audience(NotificationAudience.ADMINS_MANAGERS)
    if staff:
        n_staff = Notification(
            title='New Trainer Request',
            message=(
                f'{member_name} has requested {trainer_name} as their trainer '
                'and is awaiting a response.'
            ),
            audience=NotificationAudience.ADMINS_MANAGERS,
            is_auto=False,
            link_url=url_for('trainer_requests.list_requests'),
            created_by_id=req.member.user_id,
        )
        db.session.add(n_staff)
        db.session.flush()
        dispatch_notification(n_staff, staff)

    db.session.commit()


def _notify_member_of_response(req, accepted):
    """Accept/Reject → the requesting member."""
    from app.models.notification import Notification, NotificationAudience
    from app.blueprints.notifications.service import dispatch_notification

    trainer_name = req.trainer.full_name
    if accepted:
        title = 'Trainer Request Accepted'
        message = (
            f'Good news! {trainer_name} has accepted your request and is now your trainer. '
            'Your workout schedules will appear under "My Schedule".'
        )
    else:
        title = 'Trainer Request Declined'
        message = f'Your request for {trainer_name} was not accepted.'
        if req.response_note:
            message += f'\n\nReason: {req.response_note}'
        message += '\n\nYou can request a different trainer anytime.'

    notification = Notification(
        title=title,
        message=message,
        audience=NotificationAudience.SINGLE_MEMBER,
        is_auto=False,
        link_url=url_for('trainer_requests.my_request'),
        created_by_id=req.responded_by_id,
    )
    db.session.add(notification)
    db.session.flush()
    dispatch_notification(notification, [req.member.user])
    db.session.commit()


def _notify_trainer_of_member_action(req, action):
    """Member cancelled a pending request / left an accepted trainer → trainer."""
    from app.models.notification import Notification, NotificationAudience
    from app.blueprints.notifications.service import dispatch_notification

    member_name = req.member.full_name
    if action == 'cancel':
        title = 'Trainer Request Cancelled'
        message = (
            f'{member_name} cancelled their trainer request before it was answered. '
            'No action is needed.'
        )
    else:  # leave
        title = 'Member Left'
        message = f'{member_name} has ended their training assignment with you.'

    notification = Notification(
        title=title,
        message=message,
        audience=NotificationAudience.SINGLE_TRAINER,
        is_auto=False,
        created_by_id=req.member.user_id,
    )
    db.session.add(notification)
    db.session.flush()
    dispatch_notification(notification, [req.trainer.user])
    db.session.commit()


def _notify_member_of_removal(req):
    """Trainer/Admin ended an accepted assignment → the member."""
    from app.models.notification import Notification, NotificationAudience
    from app.blueprints.notifications.service import dispatch_notification

    trainer_name = req.trainer.full_name
    notification = Notification(
        title='Trainer Assignment Ended',
        message=(
            f'{trainer_name} has ended your training assignment. '
            'You can request a trainer again anytime.'
        ),
        audience=NotificationAudience.SINGLE_MEMBER,
        is_auto=False,
        link_url=url_for('trainer_requests.find_trainer'),
        created_by_id=req.ended_by_id,
    )
    db.session.add(notification)
    db.session.flush()
    dispatch_notification(notification, [req.member.user])
    db.session.commit()
