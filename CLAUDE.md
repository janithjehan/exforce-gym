# Exforce GMS — Implementation Patterns & Module Reference

---

## SRS 3.1 — Users Module (Completed)

### SRS Requirements Covered
- FR-USR-01: RBAC enforced on every route via decorators
- FR-USR-02: bcrypt password hashing
- FR-USR-03: 2hr session timeout (PERMANENT_SESSION_LIFETIME + before_request check)
- FR-USR-04: Admin activate/deactivate users

### Models
- `User` (users table): id, username, email, password_hash, first_name, last_name, phone, role (enum), is_active, is_archived, last_login, created_at, updated_at, created_by_id, updated_by_id
- `UserRole` enum: ADMIN, MANAGER, TRAINER, MEMBER
- `LoginActivityLog`: tracks LOGIN, LOGOUT, FAILED_LOGIN, PASSWORD_CHANGED, ACCOUNT_ACTIVATED, ACCOUNT_DEACTIVATED

### RBAC Decorators (app/utils/decorators.py)
- `@admin_required` — Admin only
- `@trainer_required` — Trainer only
- `@admin_or_trainer_required` — Admin or Trainer
- `@admin_or_manager_required` — Admin or Manager (operational routes)
- `@admin_manager_or_trainer_required` — Admin, Manager, or Trainer (attendance routes)
- `@roles_required(*roles)` — flexible role check
- `log_activity(action, details)` — write activity log

### Auth Blueprint (/auth)
- GET/POST `/auth/login` — username or email login
- GET `/auth/logout`
- GET/POST `/auth/register` — public, creates MEMBER by default + auto Member profile
- GET/POST `/auth/change-password` — authenticated, requires current password

### Users Blueprint (/users) — Admin Only
- GET `/users/` — list with search (name/email/username) + role/status filter + pagination (15/page)
- GET/POST `/users/create` — also auto-creates Member profile if role==MEMBER
- GET `/users/<id>`
- GET/POST `/users/<id>/edit`
- POST `/users/<id>/activate`
- POST `/users/<id>/deactivate` — guards: can't deactivate self, can't remove last admin
- POST `/users/<id>/archive` — soft delete, same guards
- GET/POST `/users/<id>/reset-password` — admin sets new password, audited

### Dashboard Blueprint (/dashboard)
- `/dashboard/` — redirects to role-specific dashboard
- `/dashboard/admin`, `/dashboard/trainer`, `/dashboard/member`

### Key Guards
- Cannot deactivate/archive self
- Cannot remove last active admin
- Cannot change last admin's role away from ADMIN
- Deactivated/archived users cannot log in (user_loader returns None)
- Archived users cannot be edited or have password reset

---

## SRS 3.2 — Members Module (Completed)

### SRS Requirements Covered
- FR-MEM-01: Full Name (from User), Contact No, Email (from User), Address, Join Date, Status
- FR-MEM-02: `is_active_member` property ready — lazy-imports Membership model; returns False until Membership module is built
- FR-MEM-03: Soft delete via `is_archived`; only Admin can archive; also deactivates the User account

### Model: Member (members table)
Fields: id, user_id (FK users, unique), contact_no, address, join_date, date_of_birth, gender (enum: MALE/FEMALE/OTHER), emergency_contact_name, emergency_contact_no, notes, is_archived, created_by_id, updated_by_id, created_at, updated_at
- One-to-one with User via `user.member_profile` backref (lazy='joined')
- `is_active_member` — lazy-imports Membership model; returns False until Membership module is built
- `is_profile_complete` — True if contact_no is non-empty
- `age` — computed from date_of_birth

### Auto-creation of Member profiles
- `auth/routes.py register()` — creates Member with contact_no=phone after User flush
- `users/routes.py create_user()` — creates Member when role==MEMBER after User flush

### Members Blueprint (/members)
- GET `/members/` — list with search (name/email/contact) + status filter + pagination (15/page); shows total + incomplete count
- GET/POST `/members/create` — creates User (MEMBER role) + Member profile in one two-panel form
- GET `/members/<id>` — view (admin sees all; member sees own only via 403 guard)
- GET/POST `/members/<id>/edit` — edits Member profile fields + user first_name/last_name/phone
- POST `/members/<id>/archive` — soft delete + deactivates User account
- POST `/members/<id>/restore` — un-archives + re-activates User account
- GET `/members/my-profile` — member-facing self-view (MEMBER role only)

### Admin Dashboard (updated for Members)
- Stats: total_members, incomplete_profiles, admins, trainers, total_users
- Table: recently joined members (linked to member profile view)
- Quick actions: Add Member, View All Members, Add User/Staff

---

## SRS 3.3 — Packages Module (Completed)

### SRS Requirements Covered
- FR-PKG-01: duration_months field supports 1, 3, 6, 12 month choices
- FR-PKG-02: All create/modify routes protected by `@admin_required`
- FR-PKG-03: `is_active` flag — inactive packages blocked at assignment time (enforced in Membership module)

### Model: Package (packages table)
Fields: id, name, duration_months (int), price (Numeric 10,2), description, is_active, is_archived, created_by_id, updated_by_id, created_at, updated_at
- `duration_label` — human-readable label from DURATION_CHOICES
- `status_label` / `status_badge_class` — for template badges

### Packages Blueprint (/packages) — Admin Only
- GET `/packages/` — list with active/inactive/all tab filter
- GET/POST `/packages/create`
- GET `/packages/<id>`
- GET/POST `/packages/<id>/edit` — blocked if archived
- POST `/packages/<id>/toggle-status` — activate/deactivate
- POST `/packages/<id>/archive` — soft delete, sets is_active=False

---

## Registered Blueprints (app/__init__.py)
| Prefix       | Blueprint      | Auth        |
|--------------|----------------|-------------|
| /auth        | auth_bp        | Public      |
| /users       | users_bp       | Admin only  |
| /members     | members_bp     | Admin/Member|
| /packages    | packages_bp    | Admin only  |
| /dashboard   | dashboard_bp   | Any logged-in|

---

## SRS 3.4 — Membership Module (Completed)

### SRS Requirements Covered
- FR-MSHIP-01: end_date calculated via `Membership.calculate_end_date(start_date, duration_months)`
- FR-MSHIP-02: Blocked at create time if member already has ACTIVE membership with end_date >= today
- FR-MSHIP-03: Renew sets new start_date = current.end_date + 1 day (extends from end, not today)

### Model: Membership (memberships table)
Fields: id, member_id (FK members), package_id (FK packages), start_date, end_date, status (enum), notes, created_by_id, updated_by_id, created_at, updated_at
- `MembershipStatus` enum: ACTIVE, EXPIRED, CANCELLED
- `is_currently_active` — status==ACTIVE and end_date >= today
- `days_remaining` — days until end_date (0 if not active)
- `expire_passed()` — class method, bulk-expires overdue ACTIVE memberships
- Member.is_active_member now resolves correctly via lazy import

### Memberships Blueprint (/memberships) — Admin Only (Members read-own)
- GET `/memberships/` — list with active/expired/cancelled/all tabs + member search + stats
- GET/POST `/memberships/create` — assign package to member; accepts `?member_id=` pre-fill
- GET `/memberships/<id>` — view; members can only view their own
- POST `/memberships/<id>/renew` — creates new membership extending from end_date
- POST `/memberships/<id>/cancel` — cancels membership

### CLI
- `flask expire-memberships` — bulk-expires passed memberships (run as a scheduled task)

### Other updates
- Admin dashboard: Active Memberships stat is now live; Assign Membership quick action added
- Member dashboard: shows current active membership card with days remaining

---

## SRS 3.5 — Payments Module (Completed)

### SRS Requirements Covered
- FR-PAY-01: Payment linked to Member (required FK) and Membership (optional FK)
- FR-PAY-02: PaymentMethod enum: CASH, CARD, BANK_TRANSFER, ONLINE — each with label, badge_class, icon
- FR-PAY-03: Editing restricted to Admin; every changed field logged to PaymentEditLog (who/when/old/new)

### Models
- `Payment` (payments table): id, member_id (FK), membership_id (FK nullable), amount (Numeric 10,2), method (enum), payment_date, reference_no, notes, created_by_id, updated_by_id, created_at, updated_at
- `PaymentMethod` enum: CASH/CARD/BANK_TRANSFER/ONLINE — has `.label`, `.badge_class`, `.icon`
- `PaymentEditLog` (payment_edit_logs table): id, payment_id, edited_by_id, field_name, old_value, new_value, created_at

### Payments Blueprint (/payments) — Admin Only
- GET `/payments/` — list with search (member name/ref) + method filter + month filter + pagination (20/page); stats: total, total revenue, this-month count + revenue
- GET/POST `/payments/create` — record payment; accepts `?member_id=` and `?membership_id=` pre-fill; membership dropdown populated via AJAX
- GET `/payments/<id>` — view payment details + edit audit log
- GET/POST `/payments/<id>/edit` — admin only; detects changed fields, inserts PaymentEditLog rows for each
- GET `/payments/memberships-for-member/<member_id>` — AJAX endpoint, returns JSON list of memberships for a member (used by create form JS)

### Other updates
- `templates/members/view.html`: Membership placeholder replaced with real membership list; Payment History placeholder replaced with last 5 payments + link to view all
- Admin dashboard: "Revenue This Month" stat card added; Record Payment quick action now live; Payments module status badge = Live
- Sidebar: Payments nav link activated (was "Soon")

---

## PayHere Payment Gateway (Member Self-Service, Completed)

### Flow
Member picks package + start date (`/payments/buy`) → order summary + hidden PayHere form (`/payments/checkout`) → PayHere hosted checkout → server-to-server callback (`/payments/notify`) creates Membership + Payment → browser returns to `/payments/return` (or `/payments/cancel`).

### Files
- `app/blueprints/payments/payhere.py` — `generate_hash()` (checkout initiation) and `verify_notification()` (notify callback hash check)
- PayHere routes at the bottom of `app/blueprints/payments/routes.py`
- `templates/payments/buy.html`, `checkout.html`, `return.html`, `cancel.html`
- Config: `config.py` (PAYHERE_* keys) + `.env`

### Hash Rules (critical — cause of "Unauthorized payment request" if wrong)
- Checkout hash: `MD5(merchant_id + order_id + amount('%.2f') + currency + MD5(merchant_secret).upper()).upper()`
- Notify hash: `MD5(merchant_id + order_id + payhere_amount + payhere_currency + status_code + MD5(merchant_secret).upper()).upper()` — compare to `md5sig`
- The merchant secret is used **verbatim** as shown in the PayHere dashboard. It looks like base64 — NEVER decode it.
- Secrets are **per-domain**: the secret in `.env` must be the one generated for the exact domain the checkout page is browsed from (Integrations page in the PayHere dashboard). `localhost` and `127.0.0.1` are different domains to PayHere — only `localhost` is registered; the checkout route redirects `127.0.0.1` requests to `localhost` as a guard.

### Config (.env)
- `PAYHERE_MERCHANT_ID` / `PAYHERE_MERCHANT_SECRET` — sandbox credentials, secret tied to the `localhost` domain entry
- `PAYHERE_SANDBOX=True` → posts to sandbox.payhere.lk; False → www.payhere.lk
- `PAYHERE_NOTIFY_BASE_URL` — public base (ngrok in dev) for `notify_url` only; PayHere's server must reach it
- `PAYHERE_APP_BASE_URL=http://localhost:5000` — base for `return_url`/`cancel_url`; MUST be set in dev, otherwise it falls back to the ngrok URL and the browser lands on an unregistered domain after payment (next purchase then fails)
- `.env` is read once at startup — restart Flask after changing it

### Notify Callback (`POST /payments/notify`, CSRF-exempt)
- Verifies `md5sig`; rejects with 400 on mismatch
- `order_id` format: `GMS-{package_id}-{member_id}-{YYYYMMDD}-{unix_ts}` — parsed to create the records
- On `status_code == 2` (success): creates ACTIVE Membership (end date from package duration) + Payment (method=ONLINE, reference_no=order_id). Idempotent — skips if a Payment with that reference_no exists.

### Buy Rules
- Members only (403 otherwise); requires member profile
- Only active, non-archived packages listed
- If an active membership exists, min start date = its end_date + 1 day (renewal extends, no overlap)

### Sandbox Testing
- Browse from `http://localhost:5000` only; ngrok tunnel must be running for notify to fire
- Test card: Visa 4916217501611292, any future expiry, any CVV

---

## SRS 3.6 — Attendance Module (Completed)

### SRS Requirements Covered
- FR-ATT-01: Record check-in datetime for a member; check-out optional, recorded separately
- FR-ATT-02: Duration calculated automatically from check-in/check-out difference
- FR-ATT-03: Admin and Trainer can record/list all attendance; Members view own only
- FR-ATT-04: List with date filter, member name search, pagination (20/page)

### Model: Attendance (attendances table)
Fields: id, member_id (FK members), check_in (DateTime), check_out (DateTime nullable), notes, created_by_id, updated_by_id, created_at, updated_at
- `is_checked_out` — bool
- `duration_minutes` — int or None
- `duration_label` — "2h 30m" format
- `check_in_date` — date portion of check_in
- Member.attendances — dynamic backref, ordered by check_in desc

### Attendance Blueprint (/attendance)
- GET `/attendance/` — list; Admin/Trainer; search + date filter + stats (today, week, in-gym, total)
- GET/POST `/attendance/create` — Admin/Trainer; `?member_id=` pre-fill; validates check_out > check_in
- GET `/attendance/<id>` — view; Members can only see own (403 otherwise)
- POST `/attendance/<id>/checkout` — Admin/Trainer; sets check_out = utcnow
- GET `/attendance/my-attendance` — Member-facing paginated history

### Other updates
- Admin dashboard: "Today's Check-ins" stat card added; Mark Attendance quick action added; Attendance = Live
- Member dashboard: "Recent Attendance" card replaces "coming soon" placeholder
- members/view.html: Attendance History section added (last 5 + count link)
- Sidebar: Attendance nav links activated for Admin, Trainer, and Member sections

---

## Registered Blueprints (app/__init__.py)
| Prefix         | Blueprint        | Auth                     |
|----------------|------------------|--------------------------|
| /auth          | auth_bp          | Public                   |
| /users         | users_bp         | Admin only               |
| /members       | members_bp       | Admin/Member             |
| /packages      | packages_bp      | Admin only               |
| /memberships   | memberships_bp   | Admin/Member-own         |
| /payments      | payments_bp      | Admin only               |
| /attendance    | attendance_bp    | Admin+Trainer / Member-own |
| /dashboard     | dashboard_bp     | Any logged-in            |

---

## SRS 3.7 — Trainer Module (Completed)

### SRS Requirements Covered
- FR-TRN-01: Trainer profile linked one-to-one to User (role=TRAINER) via `trainer_profile` backref
- FR-TRN-02: Profile fields: specialization, bio, experience_years, certifications, contact_no
- FR-TRN-03: Admin manages all profiles; Trainer can view own only (403 guard)
- FR-TRN-04: Auto-creation — when a TRAINER-role User is created via users/create, a basic Trainer profile is automatically generated

### Model: Trainer (trainers table)
Fields: id, user_id (FK users, unique), specialization, bio, experience_years, certifications, contact_no, is_archived, created_by_id, updated_by_id, created_at, updated_at
- `full_name`, `email`, `username` — delegated to User
- `is_profile_complete` — True if specialization is set
- `status_label` / `status_badge_class` — based on is_archived + user.is_active

### Trainers Blueprint (/trainers) — Admin (Trainer view-own)
- GET `/trainers/` — list; active/archived tabs + name/specialization search
- GET/POST `/trainers/create` — two-panel form (Account + Trainer Profile); creates User (TRAINER) + Trainer atomically
- GET `/trainers/<id>` — view; Trainer can only view own (403 otherwise)
- GET/POST `/trainers/<id>/edit` — Admin only; blocked if archived
- POST `/trainers/<id>/archive` — soft delete + deactivates User; guard: cannot archive self
- POST `/trainers/<id>/restore` — un-archives + re-activates User
- GET `/trainers/my-profile` — Trainer role; redirects to own view_trainer

### Other updates
- `users/routes.py create_user()` — auto-creates Trainer profile when role=TRAINER (parallel to Member auto-creation)
- Admin dashboard: Trainers = Live in module status; View Trainers quick action added
- Trainer dashboard: replaced placeholder with real profile card (specialization, bio, experience, certifications); account sidebar updated
- Sidebar: Trainers nav link activated for Admin; My Profile link added for Trainer section

---

## Registered Blueprints (app/__init__.py)
| Prefix         | Blueprint        | Auth                              |
|----------------|------------------|-----------------------------------|
| /auth          | auth_bp          | Public                            |
| /users         | users_bp         | Admin only                        |
| /members       | members_bp       | Admin+Manager / Member-own        |
| /packages      | packages_bp      | Admin+Manager                     |
| /memberships   | memberships_bp   | Admin+Manager / Member-own        |
| /payments      | payments_bp      | Admin+Manager                     |
| /attendance    | attendance_bp    | Admin+Manager+Trainer / Member-own |
| /trainers      | trainers_bp      | Admin+Manager / Trainer-own       |
| /workouts      | workouts_bp      | Admin+Trainer                     |
| /schedules     | schedules_bp     | Admin+Trainer manage, Manager view, Member-own |
| /dashboard     | dashboard_bp     | Any logged-in                     |

---

## Manager Role (Added)

### Design Principle
Manager owns the **gym floor** (operations). Admin owns the **system** (accounts, roles, credentials). Manager cannot access `/users` (account management), cannot create trainer accounts, and cannot change user roles.

### User Model
- `UserRole` enum value: `MANAGER = 'manager'`
- `User.is_manager` property added

### Route-Level Access

| Module       | Manager Access                                     |
|--------------|----------------------------------------------------|
| Users        | None — `/users` stays Admin only                  |
| Members      | Full CRUD (list, create, view, edit, archive, restore) |
| Packages     | Full CRUD (list, create, view, edit, toggle, archive) |
| Memberships  | Full CRUD (list, create, view, renew, cancel)      |
| Payments     | Full CRUD (list, create, view, edit — audited)     |
| Attendance   | Full access (list, create, view, checkout)         |
| Trainers     | list, view, edit, archive, restore — **not create** |
| Dashboard    | `/dashboard/manager` with ops stats + quick actions |

### Dashboard
- Stats: total_members, active_memberships, expiring_soon, incomplete_profiles, revenue_this_month, today_checkins
- Quick actions: Add Member, View Members, Assign Membership, Record Payment, Mark Attendance, View Trainers, Manage Packages
- Template: `templates/dashboard/manager.html`

### Sidebar
- Section "Operations": Members, Packages, Memberships, Payments
- Section "Staff & Activity": Attendance, Trainers, Schedules (Soon), Notifications (Soon)
- Role badge color: `bg-primary` (blue)

---

## SRS 3.14 — Notifications Module (Completed, in-app only)

**Design note:** Notifications are internal (in-app) announcements ONLY. SMS is reserved exclusively for payment confirmations (`app/blueprints/payments/sms.py`). The earlier per-notification SMS channel (NotificationChannel/DeliveryStatus enums, send_sms/sms_*_count columns) was removed from the model, blueprint, templates, and DB schema.

### SRS Requirements Covered
- FR-NOT-01: Audience always restricted to Active Members (not archived + account active + ACTIVE membership with end_date >= today)
- FR-NOT-02: Audience filters: All Active / By Package / Expiring Within 30 Days
- FR-NOT-03: `flask send-expiry-reminders` CLI — auto-notifies members expiring within 30 days (skips anyone reminded in the last 30 days); run as a scheduled task
- FR-NOT-04: In-app delivery, always sent to every resolved recipient

### Models (app/models/notification.py)
- `Notification` (notifications): id, title, message, audience (enum), package_id (FK nullable), is_auto, recipient_count, sent_at, created_by_id, created_at
- `NotificationLog` (notification_logs): per-recipient in-app delivery record — notification_id, member_id, is_read, read_at, created_at
- Enum: `NotificationAudience` (ALL_ACTIVE/PACKAGE/EXPIRING_SOON)

### Service Layer (app/blueprints/notifications/service.py)
- `resolve_audience(audience, package_id)` — FR-NOT-01/02 member query
- `dispatch_notification(notification, members)` — creates one in-app log per recipient; caller commits
- `send_expiry_reminders()` — FR-NOT-03 job logic, shared with CLI

### Notifications Blueprint (/notifications) — Admin+Manager (Member reads own)
- GET `/notifications/` — list + stats (total, this month, members reached, auto reminders); pagination 15/page
- GET/POST `/notifications/create` — title/message/audience/package form; package select shown via JS only for package audience
- GET `/notifications/<id>` — message + delivery summary + per-recipient delivery log (delivered/read), paginated 30/page
- GET `/notifications/my-notifications` — member inbox, 10/page; viewing marks items read; unread items highlighted with "New" badge

---

## Payment Confirmation SMS (Notify.lk — the only SMS the system sends)

### Notify.lk Client (app/utils/notifylk.py)
- `send_sms(to, message)` → (ok, error); POSTs to https://app.notify.lk/api/v1/send
- `normalize_phone()` — converts 07XXXXXXXX / +94… / 9 digits → 94XXXXXXXXX; returns None if invalid
- `is_sms_configured()` — NOTIFYLK_ENABLED + user id + API key all present
- Config keys (config.py + .env): NOTIFYLK_ENABLED (default False), NOTIFYLK_USER_ID, NOTIFYLK_API_KEY, NOTIFYLK_SENDER_ID (default NotifyDEMO — replace with approved sender ID in production)
- Dependency: `requests` (in requirements.txt)

### Payment SMS (app/blueprints/payments/sms.py)
- `send_payment_confirmation(payment)` → (ok, error) — SMS receipt with amount, method, package validity, reference no
- Fired from payments/routes.py after manual payment entry and after the PayHere success callback
- Degrades gracefully: returns (False, reason) when unconfigured or member has no phone

### Other updates
- app/__init__.py: notifications_bp registered; `inject_unread_notifications` context processor → `unread_notifications` available in all templates (member unread count)
- Sidebar: Notifications live for Admin + Manager; member section gets Notifications link with red unread-count badge
- Admin dashboard: Send Notification quick action live; Notifications = Live in module status
- run.py: `flask send-expiry-reminders` CLI command

---

## SRS 3.8 — Workout Module (Completed)

### SRS Requirements Covered
- FR-WRK-01: Metadata — difficulty level (enum) + equipment_needed (free text, empty = bodyweight)
- FR-WRK-02: All routes protected by `@admin_or_trainer_required` (create/update restricted to Admin/Trainer per SRS)

### Model: Workout (workouts table) — app/models/workout.py
Fields: id, name, workout_type (enum), muscle_group (enum), difficulty (enum), equipment_needed (200, nullable), instructions (Text), is_active, is_archived, created_by_id, updated_by_id, created_at, updated_at
- Enums: `WorkoutType` (STRENGTH/CARDIO/FLEXIBILITY/BALANCE/ENDURANCE), `MuscleGroup` (CHEST/BACK/SHOULDERS/BICEPS/TRICEPS/LEGS/GLUTES/CORE/FULL_BODY), `DifficultyLevel` (BEGINNER/INTERMEDIATE/ADVANCED, has badge_class)
- `equipment_label` — equipment_needed or 'None (bodyweight)'
- `status_label` / `status_badge_class` — same pattern as Package

### Workouts Blueprint (/workouts) — Admin + Trainer only
- GET `/workouts/` — list; active/inactive/all tabs + name search + type/muscle/difficulty filters + pagination (15/page)
- GET/POST `/workouts/create` — unique-name validated (case-insensitive, excludes archived)
- GET `/workouts/<id>`
- GET/POST `/workouts/<id>/edit` — blocked if archived
- POST `/workouts/<id>/toggle-status`
- POST `/workouts/<id>/archive` — soft delete, sets is_active=False

### Other updates
- Sidebar: Workouts nav link activated for Admin and Trainer sections
- Admin dashboard: Workouts = Live in module status
- Trainer dashboard: Workout Library quick-access card added (Schedules still "coming soon")
- **DB fix (2026-07-17):** Postgres `userrole` enum was missing the `MANAGER` value (type predated the Manager role) — added via `ALTER TYPE userrole ADD VALUE 'MANAGER'`. Creating manager accounts works now.

---

## SRS 3.9 — Schedule Module (Completed)

### SRS Requirements Covered
- FR-SCH-01: Schedule = Member + Trainer + date range + 1..n ScheduleItems (workout, day_label, sets, reps, rest_seconds, notes)
- FR-SCH-02: Versioning — every edit bumps `Schedule.version` and writes a `ScheduleEditLog` row (editor, version, change summary); shown as Edit History on the view page (staff only)
- FR-SCH-03: Members view-only + can mark own schedule completed; PDF download for assigned member

### Models (app/models/schedule.py)
- `Schedule` (schedules): id, member_id (FK), trainer_id (FK), title, start_date, end_date, status (enum), notes, version, audit fields
  - `ScheduleStatus` enum: PLANNED/COMPLETED/CANCELLED (label + badge_class)
  - `is_current` — PLANNED and today within range; `date_range_label`
  - Member.schedules / Trainer.schedules dynamic backrefs
- `ScheduleItem` (schedule_items): schedule_id, workout_id (FK workouts), day_label (e.g. "Monday"/"Day 1"), sets, reps (string, allows "8-12"), rest_seconds, notes, sort_order; `rest_label` ("2 min"/"90 sec"); cascade delete-orphan from Schedule.items
- `ScheduleEditLog` (schedule_edit_logs): schedule_id, edited_by_id, version, summary, created_at

### Schedules Blueprint (/schedules)
- GET `/schedules/` — Admin+Manager+Trainer; planned/completed/cancelled/all tabs + member/title search + stats + pagination (15/page)
- GET/POST `/schedules/create` — Admin+Trainer; `?member_id=` pre-fill; trainer's own profile is forced as trainer (select locked); dynamic item rows (plain inputs `item_*` parsed by `parse_item_rows()` in forms.py, header fields via ScheduleForm)
- GET `/schedules/<id>` — staff any; member own only (403)
- GET/POST `/schedules/<id>/edit` — Admin any, Trainer own only; blocked unless PLANNED; replaces items, bumps version, writes edit log; no-op edits detected ("No changes detected")
- POST `/schedules/<id>/complete` — Admin, own Trainer, or assigned Member; PLANNED only
- POST `/schedules/<id>/cancel` — Admin / own Trainer; PLANNED only
- GET `/schedules/<id>/pdf` — same access as view; reportlab-generated A4 PDF, items grouped by day (`pdf.py: build_schedule_pdf`)
- GET `/schedules/my-schedules` — Member; own schedules, 10/page, PDF buttons

### Template notes
- `templates/schedules/_form.html` — shared by create/edit; JS `<template>` row cloning, day label carried to next row, existing items injected via `existing_items | tojson`
- Trainer ownership helper `_can_manage()` in routes.py; view passes `can_manage` to template

### Other updates
- Dependency: `reportlab==4.2.2` added to requirements.txt (PDF export)
- Sidebar: Schedules live for Admin, Manager, Trainer; "My Schedule" live for Member
- Admin dashboard: Schedules = Live in module status
- Trainer dashboard: Schedules card with New Schedule / View All buttons

---

## SRS 3.10 — Equipment Module (Completed)

### SRS Requirements Covered
- FR-EQP-01: Equipment has Name, Category (enum), Image (upload), Quantity, Status (Available/Out of Service), Notes
- FR-EQP-02: Admin+Manager+Trainer can view; only Admin can create/update/archive
- FR-EQP-03: Equipment library visible to Trainers for schedule planning

### Model: Equipment (equipments table) — app/models/equipment.py
Fields: id, name, category (enum), image_filename (nullable), quantity (int, default 1), status (enum), notes (Text), is_archived, created_by_id, updated_by_id, created_at, updated_at
- Enums: `EquipmentCategory` (CARDIO/STRENGTH_MACHINE/FREE_WEIGHTS/FUNCTIONAL/ACCESSORIES/OTHER), `EquipmentStatus` (AVAILABLE/OUT_OF_SERVICE, has label + badge_class)
- `image_path` — static-relative path (`uploads/equipment/<file>`) for url_for('static', ...); None if no image
- `is_available`, `status_label`, `status_badge_class` — same pattern as Workout (Archived overrides)

### Image Upload
- Files stored in `app/static/uploads/equipment/` (dir auto-created; `.gitkeep` committed)
- Saved as `<uuid4hex>.<ext>`; allowed: jpg/jpeg/png/gif/webp (FileAllowed validator)
- Edit: new upload replaces + deletes old file; `remove_image` checkbox deletes without replacing; deletion is best-effort (never fails the request)
- Forms use `enctype="multipart/form-data"`

### Equipment Blueprint (/equipment) — Admin manage, Manager+Trainer view
- GET `/equipment/` — list; all/available/out_of_service tabs + name search + category filter + stats (types, total units, out-of-service) + pagination (15/page); thumbnails in table
- GET/POST `/equipment/create` — Admin only; unique-name validated (case-insensitive, excludes archived)
- GET `/equipment/<id>` — view (image, details, notes, audit info)
- GET/POST `/equipment/<id>/edit` — Admin only; blocked if archived
- POST `/equipment/<id>/toggle-status` — Admin only; flips AVAILABLE ↔ OUT_OF_SERVICE
- POST `/equipment/<id>/archive` — Admin only; soft delete

### Other updates
- Sidebar: Equipment nav link live for Admin (Gym Info), Manager (Staff & Activity), Trainer (My Work); admin/manager/trainer templates hide New/Edit/status buttons from non-admins via `current_user.is_admin`
- Admin dashboard: Equipment = Live in module status

---

## Next Modules (SRS order)
3.11 Supplement → 3.12 Measurements → 3.13 Feedback
