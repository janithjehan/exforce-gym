# SRS 3.7 — Trainer Module Changelog

## Requirements Implemented
- FR-TRN-01: Trainer profile linked one-to-one to User (role=TRAINER) via trainer_profile backref
- FR-TRN-02: Profile fields: specialization, bio, experience_years, certifications, contact_no
- FR-TRN-03: Admin manages all profiles; Trainer can view own only (403 guard)
- FR-TRN-04: Auto-creation — when a TRAINER-role User is created via users/create, a basic Trainer profile is automatically generated

---

## [+] NEW FILES CREATED

app/models/trainer.py
  - Trainer model (trainers table)
      user_id FK (unique), specialization String(200), bio Text, experience_years Integer,
      certifications Text, contact_no String(20), is_archived Boolean
      audit: created_by_id, updated_by_id, created_at, updated_at
  - Properties:
      full_name / email / username — delegated to User
      is_profile_complete — True if specialization is set
      status_label / status_badge_class — based on is_archived + user.is_active
  - Backref on User: user.trainer_profile (uselist=False, lazy='joined')

app/blueprints/trainers/__init__.py
  - trainers_bp Blueprint definition

app/blueprints/trainers/forms.py
  - TrainerCreateForm: first_name, last_name, username, email, phone, password, confirm_password
      + specialization, bio, experience_years, certifications, contact_no (required)
      password strength validation (letter + number, min 8 chars)
      validate_username / validate_email uniqueness checks
  - TrainerEditForm: first_name, last_name, phone (user fields)
      + specialization, bio, experience_years, certifications, contact_no (all optional)

app/blueprints/trainers/routes.py
  - GET  /trainers/                      list_trainers   — Admin only; active/archived tabs + name/specialization search
  - GET/POST /trainers/create            create_trainer  — Admin only; two-panel form; creates User(TRAINER) + Trainer atomically via flush
  - GET  /trainers/<id>                  view_trainer    — Trainer can only view own (403 otherwise)
  - GET/POST /trainers/<id>/edit         edit_trainer    — Admin only; blocked if archived; updates both User and Trainer fields
  - POST /trainers/<id>/archive          archive_trainer — soft delete + deactivates User; guard: cannot archive self
  - POST /trainers/<id>/restore          restore_trainer — un-archives + re-activates User
  - GET  /trainers/my-profile            my_profile      — Trainer role; redirects to own view_trainer

templates/trainers/list.html
  - 2 stat cards: Active Trainers / Archived
  - Active/Archived tab buttons + name/specialization search
  - Paginated table: avatar + name/email, specialization, experience, contact, status badge, view button

templates/trainers/create.html
  - Two-panel form matching members/create.html pattern
  - Left: Account Details (name, username, email, phone, password, confirm)
  - Right: Trainer Profile (specialization, experience_years, contact_no, certifications, bio)

templates/trainers/view.html
  - Archived alert banner when is_archived
  - Left: Profile summary card (avatar, name, username, email, status badge, contact/experience/specialization)
  - Right: About (bio) card + Certifications card + Record Info card (admin only)
  - Admin action buttons: Edit Profile, User Account link, Archive/Restore

templates/trainers/edit.html
  - Two-panel form: Personal Info (name, phone, contact_no) + Trainer Details (specialization, experience, certifications, bio)

---

## [~] EXISTING FILES EDITED

app/models/__init__.py
  - Added export: Trainer

app/__init__.py
  - Imported trainers_bp
  - Registered blueprint: url_prefix='/trainers'

app/blueprints/users/routes.py
  - Imported Trainer model
  - Added auto-creation branch: when role=TRAINER after user flush, creates Trainer(user_id, contact_no=phone or '')
      mirrors existing Member auto-creation pattern (elif user.role == UserRole.TRAINER)

templates/base.html
  - Admin sidebar: activated Trainers link (was "Soon"); url_for('trainers.list_trainers')
  - Trainer sidebar: added My Profile link at top of section; url_for('trainers.my_profile')

templates/dashboard/admin.html
  - View Trainers quick action added
  - Module Status: Trainers entry added with "Live" badge

app/blueprints/dashboard/routes.py
  - trainer() route: queries current_user.trainer_profile and passes to template

templates/dashboard/trainer.html
  - Replaced "Trainer modules coming soon" placeholder with real profile card
      shows specialization, experience, contact, certifications, bio
      incomplete-profile warning alert if specialization not set
  - Account sidebar: added View My Profile button linking to view_trainer
  - Kept "Schedules & Workouts coming soon" placeholder for future modules

CLAUDE.md
  - Added full SRS 3.7 module reference section
  - Updated Registered Blueprints table to include /trainers
  - Updated Next Modules list (removed 3.7, starts at 3.8)