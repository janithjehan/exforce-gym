from datetime import datetime, date
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.blueprints.members import members_bp
from app.blueprints.members.forms import MemberCreateForm, MemberEditForm, MemberSelfEditForm
from app.extensions import db
from app.models.user import User, UserRole
from app.models.member import Member, Gender
from app.utils.decorators import admin_required, admin_or_manager_required
from app.utils.search import parse_search_terms, multi_term_filter
from app.utils.validators import clean_nic, parse_nic

MEMBERS_PER_PAGE = 15


@members_bp.route('/')
@admin_or_manager_required
def list_members():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', 'all')

    # Join Member → User for searching/sorting
    query = (
        Member.query
        .join(User, Member.user_id == User.id)
    )

    terms = parse_search_terms(search)
    if terms:
        query = query.filter(multi_term_filter(terms, [
            User.first_name, User.last_name, User.email, Member.contact_no,
        ]))

    if status_filter == 'archived':
        query = query.filter(Member.is_archived == True)
    else:
        query = query.filter(Member.is_archived == False)

    members = query.order_by(Member.join_date.desc()).paginate(
        page=page, per_page=MEMBERS_PER_PAGE, error_out=False
    )

    # Stats (only non-archived)
    total = Member.query.filter_by(is_archived=False).count()
    incomplete = Member.query.filter(
        Member.is_archived == False,
        db.or_(Member.contact_no == '', Member.contact_no == None),
    ).count()

    return render_template(
        'members/list.html',
        members=members,
        search=search,
        status_filter=status_filter,
        total=total,
        incomplete=incomplete,
        title='Members',
    )


@members_bp.route('/create', methods=['GET', 'POST'])
@admin_or_manager_required
def create_member():
    form = MemberCreateForm()
    if form.validate_on_submit():
        # Create User account
        user = User(
            username=form.username.data.strip(),
            email=form.email.data.strip().lower(),
            first_name=form.first_name.data.strip(),
            last_name=form.last_name.data.strip(),
            phone=form.phone.data.strip() or form.contact_no.data.strip(),
            nic_no=clean_nic(form.nic_no.data),
            role=UserRole.MEMBER,
            is_active=True,
            created_by_id=current_user.id,
        )
        user.set_password(clean_nic(form.nic_no.data))
        db.session.add(user)
        db.session.flush()  # get user.id before committing

        # Create Member profile
        # DOB/gender/age are derived from the NIC — the NIC is authoritative
        nic_dob, nic_gender = parse_nic(form.nic_no.data)
        member = Member(
            user_id=user.id,
            contact_no=form.contact_no.data.strip(),
            address=form.address.data.strip() or None,
            join_date=form.join_date.data,
            date_of_birth=nic_dob or form.date_of_birth.data,
            gender=Gender(nic_gender) if nic_gender else None,
            emergency_contact_name=form.emergency_contact_name.data.strip() or None,
            emergency_contact_no=form.emergency_contact_no.data.strip() or None,
            notes=form.notes.data.strip() or None,
            created_by_id=current_user.id,
        )
        db.session.add(member)
        db.session.commit()

        flash(f'Member "{user.full_name}" created successfully. Their initial password is their NIC number.', 'success')
        return redirect(url_for('members.view_member', member_id=member.id))

    return render_template('members/create.html', form=form, title='Add Member')


@members_bp.route('/<int:member_id>')
@login_required
def view_member(member_id):
    member = Member.query.get_or_404(member_id)

    # Members can only view their own profile
    if current_user.role == UserRole.MEMBER:
        if not current_user.member_profile or current_user.member_profile.id != member_id:
            from flask import abort
            abort(403)

    return render_template('members/view.html', member=member, title=member.full_name)


@members_bp.route('/<int:member_id>/edit', methods=['GET', 'POST'])
@admin_or_manager_required
def edit_member(member_id):
    member = Member.query.get_or_404(member_id)

    if member.is_archived:
        flash('Archived member profiles cannot be edited.', 'warning')
        return redirect(url_for('members.view_member', member_id=member_id))

    form = MemberEditForm(user_id=member.user_id)

    if request.method == 'GET':
        # Pre-populate form
        form.first_name.data = member.user.first_name
        form.last_name.data = member.user.last_name
        form.phone.data = member.user.phone
        form.nic_no.data = member.user.nic_no
        form.contact_no.data = member.contact_no
        form.address.data = member.address
        form.join_date.data = member.join_date
        form.date_of_birth.data = member.date_of_birth
        form.gender.data = member.gender.value if member.gender else ''
        form.emergency_contact_name.data = member.emergency_contact_name
        form.emergency_contact_no.data = member.emergency_contact_no
        form.notes.data = member.notes

    if form.validate_on_submit():
        # Update User name and phone
        member.user.first_name = form.first_name.data.strip()
        member.user.last_name = form.last_name.data.strip()
        member.user.phone = form.phone.data.strip() or form.contact_no.data.strip()
        member.user.nic_no = clean_nic(form.nic_no.data)
        member.user.updated_by_id = current_user.id
        member.user.updated_at = datetime.utcnow()

        # Update Member profile
        member.contact_no = form.contact_no.data.strip()
        member.address = form.address.data.strip() or None
        member.join_date = form.join_date.data
        member.date_of_birth = form.date_of_birth.data or None
        member.gender = Gender(form.gender.data) if form.gender.data else None
        member.emergency_contact_name = form.emergency_contact_name.data.strip() or None
        member.emergency_contact_no = form.emergency_contact_no.data.strip() or None
        member.notes = form.notes.data.strip() or None
        member.updated_by_id = current_user.id
        member.updated_at = datetime.utcnow()

        db.session.commit()
        flash(f'Profile for "{member.full_name}" updated successfully.', 'success')
        return redirect(url_for('members.view_member', member_id=member_id))

    return render_template('members/edit.html', form=form, member=member, title='Edit Member')


@members_bp.route('/<int:member_id>/archive', methods=['POST'])
@admin_or_manager_required
def archive_member(member_id):
    member = Member.query.get_or_404(member_id)

    member.is_archived = True
    member.updated_by_id = current_user.id
    member.updated_at = datetime.utcnow()

    # Also deactivate the user account
    member.user.is_active = False
    member.user.updated_by_id = current_user.id
    member.user.updated_at = datetime.utcnow()

    db.session.commit()
    flash(f'Member "{member.full_name}" has been archived.', 'secondary')
    return redirect(url_for('members.list_members'))


@members_bp.route('/<int:member_id>/restore', methods=['POST'])
@admin_or_manager_required
def restore_member(member_id):
    member = Member.query.get_or_404(member_id)

    member.is_archived = False
    member.updated_by_id = current_user.id
    member.updated_at = datetime.utcnow()

    member.user.is_active = True
    member.user.updated_by_id = current_user.id
    member.user.updated_at = datetime.utcnow()

    db.session.commit()
    flash(f'Member "{member.full_name}" has been restored.', 'success')
    return redirect(url_for('members.view_member', member_id=member_id))


@members_bp.route('/my-profile')
@login_required
def my_profile():
    """Member views their own profile."""
    if current_user.role != UserRole.MEMBER:
        return redirect(url_for('dashboard.home'))

    member = current_user.member_profile
    if not member:
        flash('Your member profile has not been set up yet. Please contact the gym.', 'warning')
        return redirect(url_for('dashboard.home'))

    return render_template('members/my_profile.html', member=member, title='My Profile')


@members_bp.route('/my-profile/edit', methods=['GET', 'POST'])
@login_required
def my_profile_edit():
    """Member self-service: mobile number, NIC, address, emergency contact.

    Name, username, email stay admin-managed. Date of birth and gender are
    not directly editable — they're re-derived from the NIC whenever it changes.
    """
    if current_user.role != UserRole.MEMBER:
        return redirect(url_for('dashboard.home'))

    member = current_user.member_profile
    if not member:
        flash('Your member profile has not been set up yet. Please contact the gym.', 'warning')
        return redirect(url_for('dashboard.home'))

    form = MemberSelfEditForm(user_id=current_user.id)
    if request.method == 'GET':
        form.phone.data = member.user.phone
        form.nic_no.data = member.user.nic_no
        form.address.data = member.address
        form.emergency_contact_name.data = member.emergency_contact_name
        form.emergency_contact_no.data = member.emergency_contact_no

    if form.validate_on_submit():
        mobile = form.phone.data.strip()
        member.user.phone = mobile
        member.contact_no = mobile  # keep account phone and profile contact in sync
        member.user.nic_no = clean_nic(form.nic_no.data)
        member.user.updated_by_id = current_user.id
        member.user.updated_at = datetime.utcnow()

        # NIC is authoritative for DOB/gender — re-derive whenever it changes
        nic_dob, nic_gender = parse_nic(form.nic_no.data)
        member.date_of_birth = nic_dob
        member.gender = Gender(nic_gender) if nic_gender else None

        member.address = form.address.data.strip() or None
        member.emergency_contact_name = form.emergency_contact_name.data.strip() or None
        member.emergency_contact_no = form.emergency_contact_no.data.strip() or None
        member.updated_by_id = current_user.id
        member.updated_at = datetime.utcnow()

        db.session.commit()
        flash('Your profile has been updated.', 'success')
        return redirect(url_for('members.my_profile'))

    return render_template('members/my_profile_edit.html', form=form, member=member, title='Edit My Profile')
