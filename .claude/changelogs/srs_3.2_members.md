# SRS 3.2 — Members Module Changelog

## Requirements Implemented
- FR-MEM-01: Member profile fields — Full Name (from User), Contact No, Email (from User), Address, Join Date, Gender, DOB, Emergency Contact
- FR-MEM-02: `is_active_member` property — lazy-imports Membership model; resolves once Memberships module is built
- FR-MEM-03: Soft delete via `is_archived`; archive also deactivates the linked User account

---

## [+] NEW FILES CREATED

app/models/member.py
  - Gender enum: MALE / FEMALE / OTHER  (each with .label)
  - Member model (members table)
      user_id FK (unique one-to-one with User), contact_no, address, join_date
      date_of_birth, gender enum, emergency_contact_name, emergency_contact_no
      notes (admin-only), is_archived, audit fields
  - is_active_member property — lazy-imports Membership/MembershipStatus
  - is_profile_complete property — True if contact_no is non-empty
  - age property — computed from date_of_birth
  - full_name / email / username / contact_no proxied from User via relationship

app/blueprints/members/__init__.py
  - members_bp Blueprint definition

app/blueprints/members/forms.py
  - MemberCreateForm: username, email, password, first_name, last_name, phone (User fields)
                      contact_no, address, join_date, date_of_birth, gender, notes (Member fields)
  - MemberEditForm: first_name, last_name, phone (User), + all Member profile fields

app/blueprints/members/routes.py
  - GET  /members/               list_members    — search (name/email/contact) + status filter + pagination (15/page)
                                                   shows total count + incomplete profile count
  - GET/POST /members/create     create_member   — creates User (MEMBER role) + Member profile in one form
  - GET  /members/<id>           view_member     — admin sees all; member sees own only (403 guard)
  - GET/POST /members/<id>/edit  edit_member     — edits Member fields + user first_name/last_name/phone
  - POST /members/<id>/archive   archive_member  — soft delete + deactivates User account
  - POST /members/<id>/restore   restore_member  — un-archives + re-activates User account
  - GET  /members/my-profile     my_profile      — member-facing self-view (MEMBER role only)

templates/members/list.html
  - Page header with total count + incomplete profiles warning count
  - Search bar + active/all/archived tabs
  - Table: avatar initials, full name (linked), email, contact, join date, membership status badge, view button

templates/members/create.html
  - Two-panel form: left = User account fields, right = Member profile fields
  - Auto-generates username suggestion from first+last name

templates/members/view.html
  - Left sidebar: avatar, name, username, email, membership status badge
  - Profile info list: contact, joined, age, gender, address
  - Emergency contact card (shown if filled)
  - Right column: Membership placeholder, Payment History placeholder, Workout Schedule placeholder
  - Admin Notes card (admin only, shown if notes exist)
  - Action buttons: Edit Profile, User Account, Archive / Restore

templates/members/edit.html
  - Two-panel form: User fields (first_name, last_name, phone) + Member profile fields
  - Breadcrumb back to member view

templates/members/my_profile.html
  - Member-facing self-view: profile info, active membership card
  - Change Password link

---

## [~] EXISTING FILES EDITED

app/models/__init__.py
  - Added exports: Member, Gender

app/__init__.py
  - Imported members_bp
  - Registered blueprint: url_prefix='/members'

app/blueprints/auth/routes.py
  - register() — after User flush, auto-creates Member profile with contact_no=phone

app/blueprints/users/routes.py
  - create_user() — after User flush, if role==MEMBER auto-creates Member profile

templates/base.html
  - Admin sidebar: activated Members nav link (was "Soon")
  - Member sidebar: activated My Profile nav link → url_for('members.my_profile')

app/blueprints/dashboard/routes.py
  - Added to admin stats: total_members, incomplete_profiles
  - Added query: recent_members (5 most recently joined, ordered by join_date desc)

templates/dashboard/admin.html
  - Added stat cards: Total Members, Incomplete Profiles
  - Added Recently Joined Members table (linked to member profile view)
  - Added quick actions: Add New Member, View All Members

CLAUDE.md
  - Added full SRS 3.2 module reference section
  - Updated Registered Blueprints table to include /members
