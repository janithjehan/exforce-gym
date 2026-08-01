# Exforce GMS — Implementation Patterns & Module Reference

---

## SRS 3.1 — Users Module (Completed)

### SRS Requirements Covered
- FR-USR-01: RBAC enforced on every route via decorators
- FR-USR-02: bcrypt password hashing
- FR-USR-03: 2hr session timeout (PERMANENT_SESSION_LIFETIME + before_request check)
- FR-USR-04: Admin activate/deactivate users

### Models
- `User` (users table) — see app/models/user.py for fields
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

### Model: Member (members table) — see app/models/member.py for fields
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

### Model: Package (packages table) — see app/models/package.py for fields
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

## SRS 3.4 — Membership Module (Completed)

### SRS Requirements Covered
- FR-MSHIP-01: end_date calculated via `Membership.calculate_end_date(start_date, duration_months)`
- FR-MSHIP-02: Blocked at create time if member already has ACTIVE membership with end_date >= today
- FR-MSHIP-03: Renew sets new start_date = current.end_date + 1 day (extends from end, not today)

### Model: Membership (memberships table) — see app/models/membership.py for fields
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

### Models — see app/models/payment.py for fields
- `PaymentMethod` enum: CASH/CARD/BANK_TRANSFER/ONLINE — has `.label`, `.badge_class`, `.icon`
- `PaymentEditLog` (payment_edit_logs table) — same file

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

### Model: Attendance (attendances table) — see app/models/attendance.py for fields
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

## SRS 3.7 — Trainer Module (Completed)

### SRS Requirements Covered
- FR-TRN-01: Trainer profile linked one-to-one to User (role=TRAINER) via `trainer_profile` backref
- FR-TRN-02: Profile fields: specialization, bio, experience_years, certifications, contact_no
- FR-TRN-03: Admin manages all profiles; Trainer can view own only (403 guard)
- FR-TRN-04: Auto-creation — when a TRAINER-role User is created via users/create, a basic Trainer profile is automatically generated

### Model: Trainer (trainers table) — see app/models/trainer.py for fields
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

### Models (app/models/notification.py) — see file for fields
- `NotificationLog` (notification_logs) — per-recipient in-app delivery record, read tracking
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

### Model: Workout (workouts table) — app/models/workout.py, see file for fields
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

### Models (app/models/schedule.py) — see file for fields
- `Schedule` (schedules)
  - `ScheduleStatus` enum: PLANNED/COMPLETED/CANCELLED (label + badge_class)
  - `is_current` — PLANNED and today within range; `date_range_label`
  - Member.schedules / Trainer.schedules dynamic backrefs
- `ScheduleItem` (schedule_items) — `rest_label` ("2 min"/"90 sec"); cascade delete-orphan from Schedule.items
- `ScheduleEditLog` (schedule_edit_logs)

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

### Model: Equipment (equipments table) — app/models/equipment.py, see file for fields
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

## SRS 3.11 — Supplement Module (Completed)

### SRS Requirements Covered
- FR-SUP-01: Name, Type (Creatine/Protein/Other), Brand, Price (optional), Stock Qty (optional), Status
- FR-SUP-02: Only Admin manages (Manager can view staff list); members view catalog when `SUPPLEMENTS_MEMBER_VIEW` config flag is enabled (default True; env-overridable, catalog 404s when disabled)

### Model: Supplement (supplements table) — app/models/supplement.py, see file for fields
- Enums: `SupplementType` (CREATINE/PROTEIN/OTHER), `SupplementStatus` (AVAILABLE/OUT_OF_STOCK/DISCONTINUED, has label + badge_class)
- `price_label` ('Rs. 4,500.00' or '—'), `stock_label`, `is_stock_tracked`, `status_label`/`status_badge_class` (Archived overrides)

### Supplements Blueprint (/supplements) — Admin manage, Manager view, Member catalog
- GET `/supplements/` — Admin+Manager; All/Available/Out of Stock/Discontinued tabs + name/brand search + type filter + stats + pagination (15/page)
- GET/POST `/supplements/create` — Admin only; unique-name validated (case-insensitive, excludes archived)
- GET `/supplements/<id>` — Admin+Manager; includes inline Update Stock form (admin)
- GET/POST `/supplements/<id>/edit` — Admin only; blocked if archived
- POST `/supplements/<id>/update-stock` — Admin only; sets stock_qty (InputRequired so 0 is valid); auto-syncs status: 0 → OUT_OF_STOCK, >0 → AVAILABLE, unless DISCONTINUED
- POST `/supplements/<id>/archive` — Admin only; soft delete
- GET `/supplements/catalog` — MEMBER role only; gated by SUPPLEMENTS_MEMBER_VIEW; lists non-archived, non-discontinued items with name/type/brand/price/availability (no stock counts shown)

### Other updates
- config.py: `SUPPLEMENTS_MEMBER_VIEW` flag (env `SUPPLEMENTS_MEMBER_VIEW`, default True)
- Sidebar: Supplements live for Admin (Gym Info) + Manager (Staff & Activity); Member section gets Supplements catalog link wrapped in `{% if config.SUPPLEMENTS_MEMBER_VIEW %}`
- Admin dashboard: Supplements = Live in module status

---

## SRS 3.12 — Measurements Module (Completed)

### SRS Requirements Covered
- FR-MEAS-01: Record = Member + Date + configurable value fields (weight, height, chest, waist, hips, arms, thighs — all optional, ≥1 required, validated in routes)
- FR-MEAS-02: Access = Admin + owning Member ONLY (no Manager/Trainer); enforced by `_can_access()` helper on view/edit
- FR-MEAS-03: No delete/archive routes exist; every edit logs changed fields to `MeasurementEditLog` (who/when/old/new), shown as Edit History on view page

### Models (app/models/measurement.py) — see file for fields
- `Measurement` (measurements)
  - `VALUE_FIELDS` class constant — list of (attr, label, unit); drives forms, diff detection, and template value grids
  - `recorded_values` — (label, value, unit) list of non-null fields; `bmi` — computed when weight+height present; `was_edited`
  - Member.measurements — dynamic backref ordered by measured_on desc
- `MeasurementEditLog` (measurement_edit_logs) — same pattern as PaymentEditLog

### Measurements Blueprint (/measurements) — Admin full, Member own-only
- GET `/measurements/` — Admin only; member name/email search + stats (total, members tracked, this month) + pagination (15/page)
- GET/POST `/measurements/create` — Admin (any member, `?member_id=` pre-fill) or Member (own profile forced, select hidden); measured_on defaults to today; rejects submission with zero values
- GET `/measurements/<id>` — Admin or owning member (403 otherwise); value grid + BMI + edit history
- GET/POST `/measurements/<id>/edit` — Admin or owning member; member_id locked to record; `_detect_changes()` diff → one MeasurementEditLog row per changed field; "No changes detected" no-op guard
- GET `/measurements/my-measurements` — Member; paginated history (10/page) + latest snapshot card + Chart.js weight trend line (chart only renders with ≥2 weight entries)

### Template notes
- `templates/measurements/_fields.html` — shared field partial (create + edit)
- Chart.js 4.4.3 via CDN, loaded only on my_measurements when trend has ≥2 points

### Other updates
- members/view.html: "Recent Measurements" card (admin-only via role check) with last 5 + Add button
- Member dashboard: "Latest Measurement" card in sidebar column (route passes latest_measurement)
- Sidebar: Measurements live for Admin (Operations) and Member (was "Soon")
- Admin dashboard: Measurements = Live in module status

---

## SRS 3.13 — Feedback Module (Completed)

### SRS Requirements Covered
- FR-FDB-01: Feedback = Member + Date (created_at) + Category (optional enum) + Rating (1–5) + Comments
- FR-FDB-02: `/feedback/my-feedback` — member's own history with status + admin responses
- FR-FDB-03: `/feedback/export` — Admin CSV report, honours current list filters (status/category/search)
- FR-FDB-04: `submit_feedback` blocked unless `member.is_active_member` (flash + redirect); submit button also hidden in UI when inactive

### Models (app/models/feedback.py) — see file for fields
- Enums: `FeedbackCategory` (SERVICE/TRAINERS/FACILITY/EQUIPMENT/OTHER), `FeedbackStatus` (NEW/REVIEWED/RESOLVED — label + badge_class: primary/warning/success)
- `category_label` ('General' when category is None), `has_response`; Member.feedbacks dynamic backref

### Feedback Blueprint (/feedback) — Admin manage, Member submit/read-own
- GET `/feedback/` — Admin; status tabs (default **new**) + category filter + member search + stats (total, awaiting review, avg rating, this month) + pagination (15/page)
- GET/POST `/feedback/submit` — Member only; FR-FDB-04 active-membership guard; interactive JS star-rating picker over a hidden RadioField
- GET `/feedback/<id>` — Admin or owning member (403 otherwise); admin sees Respond & Update Status panel
- POST `/feedback/<id>/respond` — Admin; sets status + optional response; response stamps responded_by/responded_at (cleared if response emptied)
- GET `/feedback/my-feedback` — Member; own history 10/page, "Responded" badge, submit CTA hidden when membership inactive
- GET `/feedback/export` — Admin; CSV download `feedback_report_YYYYMMDD.csv` (shared `_filtered_query()` with list route)

### Other updates
- Sidebar: Feedback live for Admin (Gym Info) + Member (was "Soon" in both)
- Admin dashboard: "New Feedback" stat card added; Feedback = Live in module status

---

## NIC & Mobile Number (Added 2026-07-18)

### Rules
- `users.nic_no` column (String 20, nullable in DB; added via manual `ALTER TABLE`)
- Mobile number + NIC **required for every role except Admin**, enforced form-level on all paths: users create/edit (`_require_contact_fields`), auth register, members create/edit, trainers create/edit
- NIC format: 9 digits + V/X (old) or 12 digits (new); day-of-year must be 1–366 or 501–866; stored normalized uppercase; unique across users (case-insensitive, form-level check)

### Shared helpers (app/utils/validators.py)
- `validate_nic_format` — WTForms validator, granular messages (mirrors client JS)
- `parse_nic(nic)` → (birth_date, 'male'/'female') — decodes DOB (Feb always 29 days per NIC convention; +500 = female) or (None, None)
- `clean_nic`, `nic_taken(nic, exclude_user_id)`

### Behavior
- Member creation (register, users/create role=member, members/create): DOB + gender auto-derived from NIC via `parse_nic`; on /members/create the DOB/Age/Gender fields are readonly (client JS `OnchangeNic` fills them live; server value is authoritative; gender dropdown has no OTHER option)
- /users/create, /members/create, and /trainers/create have **no password fields** — initial password = NIC number (uppercase); flash message says so. Because of this, /users/create requires a NIC for ALL roles including Admin.
- Role change to MEMBER/TRAINER in users/edit auto-creates the missing Member/Trainer profile (was a bug — profile only existed via create paths)
- Client JS on members/create + trainers/create: NIC onchange → inline error div (`#nicClientError`); members version also fills date_of_birth/age/gender

### Self-registration is now a separate, lighter path (2026-07-19)
- `/auth/register` (public self-signup) collects **only** name/username/email/password — no phone, no NIC. `Member.contact_no` starts `''`, `date_of_birth`/`gender` start `None`. This is intentionally different from the admin-driven create forms above, which still require NIC as the initial password.
- New self-service edit pages let the member/trainer fill in the rest themselves after logging in:
  - `/members/my-profile/edit` (`MemberSelfEditForm`) — Mobile Number (required), NIC (required, format+uniqueness validated), Address, Emergency Contact Name/No. Saving keeps `member.user.phone` and `member.contact_no` in sync, and re-derives `date_of_birth`/`gender` from the NIC every time it changes (NIC is authoritative — no manual DOB/gender field exists). Name/username/email stay admin-only. Linked from `my_profile.html`.
  - `/trainers/my-profile/edit` (`TrainerSelfEditForm`) — Mobile Number + NIC only (mirrors the member page but trainers have no DOB/gender concept). Keeps `trainer.user.phone` and `trainer.contact_no` in sync. Linked from `trainers/view.html` when a trainer is viewing their own profile. Specialization/bio/certifications/etc. remain admin-only via `/trainers/<id>/edit`.
- Both self-edit routes are member/trainer-role-gated (redirect home otherwise) and 404-safe if the profile doesn't exist yet.

---

## Forgot Password (Added 2026-07-19)

### Flow
Login page → "Forgot password?" → `/auth/forgot-password` (enter email) → emails a reset link → `/auth/reset-password/<token>` (set new password) → redirect to login.

### Token design (app/utils/tokens.py)
- `itsdangerous.URLSafeTimedSerializer` (bundled with Flask, no new dependency) signs `{user_id, pwd_fp}` where `pwd_fp` is a short SHA-256 fingerprint of the current `password_hash`.
- **Self-invalidating**: once the password changes, the fingerprint changes and the old token stops verifying — no DB-backed "used" flag/table needed.
- Expires after `PASSWORD_RESET_MAX_AGE` seconds (config/`.env`, default 3600 = 1 hour).

### Email (app/utils/mailer.py)
- Plain `smtplib` client (mirrors `notifylk.py`'s pattern), not Flask-Mail.
- `MAIL_ENABLED` config flag — when off/unconfigured, `send_email()` logs the message (incl. the reset link) to console/log instead of sending, so the whole flow is testable without real SMTP creds.
- Config keys: `MAIL_ENABLED`, `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER`. Needs real SMTP credentials (Gmail App Password, SendGrid, etc.) in `.env` to actually send in production.

### Routes (app/blueprints/auth/routes.py)
- `GET/POST /auth/forgot-password` — looks up by email. **Always shows the same generic flash** regardless of whether the email matched an account (prevents account enumeration). Silently no-ops for archived/inactive accounts.
- `GET/POST /auth/reset-password/<token>` — invalid/expired token → flash + redirect to forgot-password; valid → set new password, log `PASSWORD_CHANGED` to `LoginActivityLog`.

### Known gap
No rate-limiting on `/auth/forgot-password` (no rate-limit infra exists anywhere in this app yet) — repeated requests aren't throttled. Add `Flask-Limiter` if this becomes a concern.

---

## Payroll Module (Added 2026-07-19)

### Scope
Salary records for **Admin, Manager, and Trainer** — Members are not payroll subjects. Manual entry per pay period (no auto-recurring salary/generation); a "remembered base salary" field would be a natural v2 addition.

### Model (app/models/payroll.py) — see file for fields
- `Payroll` (payroll table) — `pay_period` normalized to the 1st of the month; `status` PENDING/PAID/CANCELLED; `method` set only when marked paid
- `net_amount` property = gross + bonus − deductions; `period_label` = e.g. "July 2026"
- No DB-level unique constraint on (user_id, pay_period) — duplicate PENDING/PAID records for the same staff+month are blocked at the route level instead, so a CANCELLED record doesn't permanently block that month
- `PayrollEditLog` — same audit pattern as `PaymentEditLog` (one row per changed field on edit)

### Access (app/utils/decorators.admin_or_manager_required)
- Admin and Manager have **full CRUD** — same trust level Manager already has on Payments
- **Self-guard**: neither Admin nor Manager can create, edit, mark-paid, or cancel their *own* payroll record (`user_id == current_user.id` blocked on all four mutating routes) — prevents self-approval of compensation. Enforced per-action, not via a separate role tier.
- Records are only editable/mark-paid/cancellable while `status == PENDING` (mirrors Schedule's "only editable while PLANNED" pattern)
- Staff (any role) can view their **own** record directly (`/payroll/<id>`) even without list access; `/payroll/my-payroll` (Manager, Trainer only — not Admin, matching the no-"my-profile"-for-Admin precedent) gives a paginated self-service history

### Routes (app/blueprints/payroll/routes.py)
- `GET /payroll/` — list, filter by staff/status/month, stats (pending count, paid this month, staff count)
- `GET/POST /payroll/create` — staff dropdown = active non-archived Admin/Manager/Trainer users
- `GET /payroll/<id>` — full detail for Admin/Manager or the owning staff member; edit history only shown to Admin/Manager
- `GET/POST /payroll/<id>/edit`, `GET/POST /payroll/<id>/mark-paid`, `POST /payroll/<id>/cancel` — all PENDING-only + self-guarded
- `GET /payroll/my-payroll` — Manager/Trainer own history

### Nav/dashboard wiring
- Sidebar: "Payroll" (management) for Admin+Manager; "My Payroll" for Manager+Trainer
- Admin & Manager dashboards: "Pending Payroll" stat card + "Record Payroll" quick action
- Trainer dashboard: "My Payroll" quick-access button

### Bulk creation (Added 2026-07-19)
`GET/POST /payroll/bulk-create` — select any number of Managers/Trainers and create one payroll record each for the same pay period in a single submit, with per-person Gross/Bonus/Deductions.
- No schema change — still one `Payroll` row per staff member; this is purely a multi-row entry screen (checkbox + inputs per staff row), same "dynamic row" convention as Schedule's item rows, but parsed as `selected_<id>`/`gross_<id>`/`bonus_<id>`/`deductions_<id>` per staff id rather than parallel arrays (the staff list is fixed from the DB, not freely added/removed like Schedule items).
- **Self is structurally excluded** from the staff list (`_selectable_staff_for_bulk()` filters out `current_user.id`) — no per-row self-guard needed, unlike the single-create route.
- Each row is independently validated and skipped (not fail-the-whole-batch) for: no/invalid gross amount, or a duplicate non-cancelled record already existing for that staff+month. Result flashed as "Created N records" / "Skipped: name (reason); ...".
- Only checked rows are processed — an unchecked row with a filled-in amount is silently ignored.
- "Fill Gross Amount for Checked Rows" is a client-side JS convenience (copies one typed value into every ticked row's Gross input) — still editable per row before submit, not a separate uniform-amount mode.

### Out of scope for v1
Payslip PDF export (reportlab already a dependency, Schedule module has a copyable PDF pattern), itemized statutory deductions (EPF/ETF/tax) — `deductions` is a single free-entry number.

---

## Configuration Module + Bank Transfer Payments (Added 2026-07-23)

### Design decision
Bank transfers are held for verification, not trusted on submission — a member enters a reference number, but the Membership only activates once Admin/Manager confirms the transfer actually landed. This matches how the rest of the app treats staff-confirmed state changes (e.g. Payroll's PENDING → mark-paid) rather than PayHere's instant-trust callback model, since anyone could type a fake reference number.

### Configuration Module (app/models/configuration.py, /configuration blueprint) — Admin only
- `AppConfiguration` — singleton settings row (`AppConfiguration.get()` creates it on first access if missing). Currently holds one field: `bank_transfer_details` (free-text, shown verbatim with `white-space:pre-line`).
- `GET/POST /configuration/` — single edit page, no list (it's a singleton). Sidebar entry under Admin → Administration, right after Expenses.
- Deliberately DB-backed (editable in-app) rather than `.env`-based like the PayHere/NIC/mail config keys, so gym staff can update bank details themselves without a deploy/restart.

### Payment model changes (app/models/payment.py)
- New `PaymentStatus` enum: PENDING / VERIFIED / REJECTED (badge_class: warning/success/danger). Column `status` defaults to **VERIFIED** — every existing payment path (staff-entered CASH/CARD/BANK_TRANSFER via `/payments/create`, PayHere's `/notify`) is unaffected and stays implicitly "final" the moment it's created. Only the new member-facing bank-transfer submission explicitly sets `PENDING`.
- New `verified_by_id` / `verified_at` — stamped by whichever of `verify_payment`/`reject_payment` resolves the record (both set these fields regardless of outcome).
- Revenue stats in `/payments` list (`total_revenue`, `this_month_revenue`) now filter `status == VERIFIED` — a pending bank transfer no longer inflates reported revenue until confirmed.

### Membership model changes (app/models/membership.py)
- New `MembershipStatus.PENDING` ("Pending Verification", badge_class warning) — a Membership row is created immediately alongside the PENDING Payment (holds the intended package/start/end dates), but grants no access: `is_currently_active` stays False until the status flips to ACTIVE.
- Renew/Cancel (both the routes and the `view.html` buttons) are blocked while a membership is PENDING — resolving it goes through the linked Payment's Verify/Reject instead, not the membership's own actions, to keep Payment/Membership status in lock-step. `cancel_membership` redirects to the payment view with an explanatory flash if someone tries anyway.

### Member flow (app/blueprints/payments/routes.py)
- `buy.html` now offers two buttons once a package + date are chosen: "Pay Online with PayHere" (existing) and "Pay by Bank Transfer" (new) — both wired by the same `updateSummary()` JS that already builds the PayHere checkout URL.
- `GET/POST /payments/bank-transfer?package_id=&start_date=` — re-validates package/date exactly like `payhere_checkout` (shared via `_validate_package_and_date()`), shows the configured bank details + a reference-number form (`BankTransferSubmitForm`: reference_no required, notes optional). On submit, creates the PENDING Membership + PENDING Payment atomically (`db.session.flush()` between them, same pattern as PayHere's `/notify`), amount = package price, method=BANK_TRANSFER.
- **Duplicate-submission guard**: both `/payments/buy`'s "already has a plan" logic and `payhere_checkout`/`bank_transfer` check for an existing PENDING membership for the member and block/redirect to it — a member can't stack multiple unresolved bank-transfer submissions.
- Member dashboard (`dashboard/member.html`) and `buy.html` both surface an "awaiting verification" notice when a PENDING membership exists, linking to `/memberships/<id>`.

### Staff verification (app/blueprints/payments/routes.py) — Admin+Manager
- `POST /payments/<id>/verify` — only valid for `method=BANK_TRANSFER` + `status=PENDING`; flips Payment to VERIFIED and the linked Membership to ACTIVE in the same commit, then fires the existing `send_payment_confirmation` SMS (same as any other payment).
- `POST /payments/<id>/reject` — same guard; **requires a non-empty `rejection_reason`** (form field, validated server-side — a modal-only `required` attribute isn't trusted). Stores it on `Payment.rejection_reason`, flips Payment to REJECTED and the linked Membership to CANCELLED, then calls `_notify_member_of_rejection()` to send the member an in-app notice quoting the reason (see below). No SMS — SMS stays payment-confirmation-only per the existing design note.
- Verify/Reject actions are surfaced in **two** places, both needed: `payments/view.html` (via `payment.is_pending_verification`) and — since staff normally land on the *membership* page first, not the payment page — `memberships/view.html` (via a `pending_payment = membership.payments.first()` lookup computed once at the top of the template). Reject opens a Bootstrap modal (`#rejectPaymentModal`, Bootstrap JS already loaded in `base.html`) with a required textarea instead of a bare `confirm()`, since the reason has to be typed, not just confirmed.
- `payments/list.html` and `memberships/list.html` both gained a "Pending" tab + count badge, with an alert banner linking to it when the count is non-zero.
- **Payments list default = VERIFIED only (Added 2026-07-25):** `list_payments` filters `status == VERIFIED` on the default tab (`status != 'pending'`); the "All" tab was renamed **"Verified"**. The "Pending" tab still shows PENDING for the verification queue; REJECTED payments are not listed anywhere (reachable only by direct `/payments/<id>` URL). The `total` and `this_month` count stats were also narrowed to VERIFIED so the headline numbers match the list (revenue stats were already VERIFIED-only).

### Rejection notice → member (`_notify_member_of_rejection()` in app/blueprints/payments/routes.py)
- Reuses the existing in-app Notifications system (`app/blueprints/notifications/service.py: dispatch_notification()`) rather than building a new channel — `dispatch_notification()` only ever iterates whatever `members` iterable it's given, so passing `[payment.member]` targets exactly one member without touching `resolve_audience()`.
- Added `NotificationAudience.SINGLE_MEMBER` ("Direct Notice") for this system-generated case. The manual notification-create form (`notifications/forms.py: NotificationCreateForm.audience`) uses a **hardcoded** choices list (not `[(a.value, a.label) for a in NotificationAudience]`), so this new enum value does not appear as a selectable option in the admin's "Send Notification" form — it's only ever set programmatically.
- The Notification's `message` embeds the reference no., package name, and the admin's typed reason; shows up in the member's `/notifications/my-notifications` inbox exactly like any other announcement (unread badge etc.).

### DB note (manual, no migration framework in this project — see "no Alembic" precedent from the MANAGER enum / nic_no fixes)
Applied directly against the dev DB after adding the model fields:
```sql
ALTER TABLE payments ADD COLUMN status paymentstatus NOT NULL DEFAULT 'VERIFIED';
ALTER TABLE payments ADD COLUMN verified_by_id INTEGER REFERENCES users(id);
ALTER TABLE payments ADD COLUMN verified_at TIMESTAMP;
ALTER TABLE payments ADD COLUMN rejection_reason TEXT;
ALTER TYPE membershipstatus ADD VALUE 'PENDING';        -- must run outside an explicit transaction block
ALTER TYPE notificationaudience ADD VALUE 'SINGLE_MEMBER';  -- same
```
`app_configuration` is a brand-new table, so `flask create-tables` (`db.create_all()`) picked it up without any manual DDL — same as any other new module's first deploy.

---

## Notifications — Extended to All Roles + Topbar Bell (Added 2026-07-24)

### Design change
The Notifications module originally only delivered to Members (`NotificationLog.member_id` was a FK to `members`; Admin/Manager only ever composed broadcasts, Trainer had zero access). Recipients are now **Users**, so every role — Admin, Manager, Trainer, Member — can receive a notification and has a personal inbox + unread count.

### Model (app/models/notification.py)
- `NotificationLog.member_id` (FK `members.id`) → `NotificationLog.recipient_id` (FK `users.id`), relationship renamed `member` → `recipient` (backref `User.notification_logs`).
- `NotificationAudience` gained four staff values: `ALL_ADMINS`, `ALL_MANAGERS`, `ALL_TRAINERS`, `ALL_STAFF` (Admin+Manager+Trainer) — alongside the existing member-oriented ones (`ALL_ACTIVE`, `PACKAGE`, `EXPIRING_SOON`, `SINGLE_MEMBER`).

### Service (app/blueprints/notifications/service.py)
- `resolve_audience()` now **always returns a list of `User` objects**, regardless of audience type: staff audiences query `User` directly by role (active, non-archived); member audiences run the original Member/Membership query then map each result to `.user`. This keeps `dispatch_notification()` and `send_expiry_reminders()` uniform — they only ever deal in `User.id`.
- `dispatch_notification(notification, users)` — param renamed `members`→`users`; writes `recipient_id=user.id`.

### Routes (app/blueprints/notifications/routes.py)
- `my_notifications` (`GET /notifications/my-notifications`) — the Member-only gate (`role != MEMBER` → 403, requires `member_profile`) was removed. Any authenticated role now gets their own inbox filtered by `recipient_id == current_user.id`. `list_notifications`/`create_notification`/`view_notification` stay `@admin_or_manager_required` (composing/managing broadcasts is unchanged).
- `_notify_member_of_rejection()` (app/blueprints/payments/routes.py) — updated to pass `payment.member.user` instead of `payment.member`, matching the new User-based `dispatch_notification` signature.

### Forms/templates
- `NotificationCreateForm.audience` choices gained the four staff options (`notifications/forms.py`) — form choices are a hardcoded list, not an enum-iteration, so this is the only place staff audiences need to be added for the compose UI.
- `notifications/view.html` delivery log: recipient cell now checks `log.recipient.member_profile` — links to `members.view_member` for member recipients, otherwise shows the name + a role badge (staff recipients have no Member profile to link to).
- `notifications/my.html` needed no changes (already recipient-agnostic, only reads `log.notification.*`).

### Sidebar + topbar bell (templates/base.html)
- Admin and Manager sections each gained a second nav-item, **"My Notifications"** (unread badge), alongside their existing "Notifications" (compose/manage) link — the two are disambiguated by exact-endpoint active-state checks (`request.endpoint in (...)` for the manage list vs. `== 'notifications.my_notifications'` for the inbox), same pattern as Payroll's list vs. my-payroll links.
- Trainer section gained a "Notifications" nav-item (previously had none at all).
- **Topbar bell** — a bell icon + unread-count badge sits in `#topbar .topbar-right`, immediately before the user avatar/dropdown, visible to **every** authenticated role. Always links to `notifications.my_notifications` (the personal inbox), regardless of role.
- `inject_unread_notifications()` context processor (`app/__init__.py`) generalized from `member_profile`-gated to `NotificationLog.filter_by(recipient_id=current_user.id, is_read=False)` for any authenticated user — this single count now drives both the sidebar badges and the topbar bell badge.

### DB migration (manual — no Alembic in this project)
Existing `notification_logs` data (recipients were Member rows) was backfilled, not dropped:
```sql
ALTER TABLE notification_logs ADD COLUMN recipient_id INTEGER;
UPDATE notification_logs nl SET recipient_id = m.user_id
    FROM members m WHERE nl.member_id = m.id;
ALTER TABLE notification_logs ALTER COLUMN recipient_id SET NOT NULL;
ALTER TABLE notification_logs ADD CONSTRAINT notification_logs_recipient_id_fkey
    FOREIGN KEY (recipient_id) REFERENCES users(id);
ALTER TABLE notification_logs DROP COLUMN member_id;
ALTER TYPE notificationaudience ADD VALUE 'ALL_ADMINS';
ALTER TYPE notificationaudience ADD VALUE 'ALL_MANAGERS';
ALTER TYPE notificationaudience ADD VALUE 'ALL_TRAINERS';
ALTER TYPE notificationaudience ADD VALUE 'ALL_STAFF';
```

---

## Membership Request → Staff Notification (Added 2026-07-24)

### Behavior
When a member submits a bank-transfer membership request (`POST /payments/bank-transfer` → creates the PENDING Membership + PENDING Payment), an in-app notification is fired to **every active Admin and Manager**. It surfaces in each staff member's topbar bell (unread badge) and `/notifications/my-notifications` inbox exactly like any other notification — no template changes were needed, since the bell already renders `unread_notifications` for any authenticated user.

### Implementation
- New `NotificationAudience.ADMINS_MANAGERS` ('admins_managers', label "Admins & Managers") — the same role set as `admin_or_manager_required`. Added to `STAFF_ROLES_BY_AUDIENCE` in `notifications/service.py`, so `resolve_audience()` handles it as a first-class staff audience. **Not** added to `NotificationCreateForm.audience`'s hardcoded choices — it's only ever set programmatically, same as `SINGLE_MEMBER`.
- `_notify_staff_of_membership_request(membership, payment)` in `payments/routes.py` (mirrors `_notify_member_of_rejection`): builds a Notification (`is_auto=False` — a member triggered it, not the scheduler; `created_by_id = requesting member's user`, message quotes member name / package / amount / reference / period), then `dispatch_notification()` to the resolved Admin+Manager users and commits. Called from `bank_transfer()` right after the membership+payment commit.
- Only the bank-transfer flow notifies — PayHere purchases create an instant ACTIVE membership (a completed purchase, not a pending request awaiting staff action), so they don't fire this.
- **`is_auto` is reserved for the scheduled expiry-reminder job only.** All person-triggered notices (membership request, request cancellation, payment rejection) are `is_auto=False`, so they don't inflate the "Auto reminders" stat (`notifications/routes.py`) and don't count toward the 30-day "already reminded" dedup in `send_expiry_reminders()` — meaning a rejected member is no longer wrongly skipped from expiry reminders.

### Deep link from the notification (Added 2026-07-25)
- `Notification.link_url` (String 255, nullable) — an optional relative in-app URL. When set, the recipient's inbox (`notifications/my.html`) renders a "View request" button under the message.
- `_notify_staff_of_membership_request` sets `link_url=url_for('memberships.view_membership', membership_id=membership.id)` so an Admin/Manager can jump straight from the bell/inbox to the pending membership (where the Verify/Reject actions live). `url_for` is safe here — the helper runs inside the `bank_transfer` request context.
- Generic column, reusable by any future notification that wants a deep link; unset (`None`) notifications render as before (no button).

### DB migration (manual — no Alembic)
```sql
ALTER TYPE notificationaudience ADD VALUE IF NOT EXISTS 'ADMINS_MANAGERS';  -- outside a txn block
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS link_url VARCHAR(255);
```

### Member self-cancel of a pending request (Added 2026-07-24)
- `POST /payments/<id>/cancel-request` (`payments/routes.py: cancel_request`) — member-facing, member-role + owner-guarded, only valid while the payment is `BANK_TRANSFER` + `PENDING` (i.e. before staff verify/reject). Flips the Payment → REJECTED (`rejection_reason='Cancelled by the member before verification.'`) and the linked Membership → CANCELLED in one commit, then redirects to `/payments/buy` so they can submit a fresh request. Lives next to `verify_payment`/`reject_payment` since all three resolve the same PENDING payment.
- No new `PaymentStatus` value — reuses REJECTED (with a distinguishing reason) so the withdrawn request drops out of staff's Pending queue exactly like a staff rejection; `verified_by_id` stays null (member-initiated, not staff-resolved).
- `_notify_staff_of_request_cancellation(payment)` fires an ADMINS_MANAGERS in-app notice so the earlier "New Membership Request" bell alert doesn't go stale.
- "Cancel Request" button surfaced on all three member-facing pending surfaces: `memberships/view.html` (member section, when `pending_payment` set), `payments/buy.html` (pending banner), `dashboard/member.html` (pending notice) — each a POST form with a confirm() guard, resolving the payment via `pending_membership.payments.first()`.

---

## Timezone Handling — Local Display (Added 2026-07-24)

### Problem
Timestamps are stored as naive UTC (`datetime.utcnow()` everywhere — correct), but templates rendered that UTC value directly, so times showed ~5h30m behind Sri Lanka wall-clock (e.g. a notification created at 16:06 local displayed as 10:36).

### Fix — store UTC, display local (Asia/Colombo, UTC+5:30)
- `app/utils/timezones.py`:
  - `to_local(dt)` — naive-UTC → aware local (display). `to_utc(dt)` — naive-local → naive-UTC (form input → storage). `now_local()`.
  - Resolves `Asia/Colombo` via `zoneinfo` (tzdata present), falls back to a fixed `timezone(+05:30)` if the IANA db is missing (SL has no DST).
- `app/__init__.py` registers a Jinja filter **`localdt`**: `{{ dt | localdt }}` (default `'%d %b %Y, %H:%M'`) or `{{ dt | localdt('%H:%M') }}`. Returns `''` for None.
- **Convention going forward:** any **datetime** displayed in a template must go through `| localdt('...')`, never `.strftime(...)`. **Date-only** fields (`payment_date`, `start_date`, `end_date`, `join_date`, `date_of_birth`, `measured_on`, `pay_period`) are plain `date` objects with no tz component — keep using `.strftime()` on those.
- Swept all 42 existing time-bearing datetime displays (created_at/updated_at/sent_at/read_at/verified_at/responded_at/check_in/check_out/last_login/timestamp) across 22 templates from `.strftime` → `| localdt`. Date-only `.strftime` calls were deliberately left alone.

### Attendance form input (the one round-trip case)
`attendance/create.html` check-in/out use `<input type="datetime-local">` — staff type **local** time. `create_attendance` now wraps both in `to_utc(...)` before persisting, so manual entries are stored UTC like `checkout` (which already used `utcnow()`) and render back correctly via `localdt`. The form prefill (only shown on validation-error re-render) stays raw `.strftime` — it's the just-typed local value, not a stored UTC one.

### Caveat
Any attendance rows created manually **before** this fix were stored as local-as-typed (not UTC); they'll now display +5:30 off. New rows are correct. All `utcnow()`-based fields (notifications, payments, audit logs, etc.) were always UTC, so they're simply correct now.

---

## Member "My Membership" page (Added 2026-07-25)

Members previously could only see their membership on the dashboard. Added a dedicated self-service page mirroring the `my-attendance`/`my-schedules`/`my-notifications` pattern.
- `GET /memberships/my-memberships` (`memberships/routes.py: my_memberships`) — MEMBER-only (non-members redirect to `dashboard.home`, 403 if no `member_profile`). Runs `Membership.expire_passed()` first, then paginates `member.memberships` (10/page, already ordered start_date desc) and computes `current` (ACTIVE + not expired) and `pending` (PENDING) for the top summary card.
- `templates/memberships/my_memberships.html` — top card shows the active plan (days remaining, dates) / a pending "awaiting verification" banner / or a "no plan" CTA, followed by a paginated history table (package, period, status badge, View → `view_membership`).
- Sidebar: "My Membership" nav-item added to the member section (`base.html`, after My Profile, icon `fa-id-card`, active on any `memberships.*` endpoint — safe since members only reach `my_memberships`/`view_membership`).
- `memberships/view.html` breadcrumb gained a member branch linking back to `my_memberships`.

---

## User Profile Photos (Added 2026-07-25)

Every user (Admin/Manager/Trainer/Member) can have a profile photo. **Admin-managed only for now** — set/changed/removed by Admin via the user create/edit screens; no self-service upload. Users without a photo keep showing their initials everywhere.

### Model + storage
- `User.avatar_filename` (String 255, nullable) + `User.avatar_url` property (`uploads/avatars/<file>` or None, mirrors `Equipment.image_path`) + `User.initials` helper.
- Files in `app/static/uploads/avatars/` (committed `.gitkeep`). DB: `ALTER TABLE users ADD COLUMN avatar_filename VARCHAR(255);` (manual, no Alembic).
- `config.MAX_CONTENT_LENGTH` = `MAX_UPLOAD_MB` (default 3) × 1MB — caps every upload (avatars + equipment).

### Shared upload helper (app/utils/uploads.py)
- `save_image(file, subdir)` / `delete_image(filename, subdir)` — uuid filename, `secure_filename`, best-effort delete. Generalized out of the Equipment blueprint; `equipment/routes.py` now delegates to it (its `_save_image`/`_delete_image` are thin wrappers passing `'equipment'`). `ALLOWED_IMAGE_EXTENSIONS` lives here now.

### Upload UI (Admin only)
- `UserCreateForm.photo` (FileField + FileAllowed); `UserEditForm.photo` + `remove_photo` checkbox (`_photo_field()` factory in `users/forms.py`).
- `users/create.html` + `users/edit.html`: `enctype="multipart/form-data"`; edit page shows current photo/initials preview + the remove checkbox (only when a photo exists).
- `users/routes.py` `create_user`/`edit_user`: save on upload, replace-and-delete-old on change, delete on remove (same pattern as Equipment).

### Display — one Jinja global, initials fallback
- `avatar(user, classes)` registered in `app/__init__.py` (`@app.template_global`) → renders `<img class="avatar-img {classes}">` when `avatar_url` is set, else `<div class="{classes}">{initials}</div>`. `classes` is applied to both branches so each call site keeps its existing sizing/utility classes. No per-template import needed.
- CSS `.avatar-img { object-fit:cover; border-radius:50%; }` in `style.css` — sizing comes from the companion class (`.avatar` topbar / `.user-avatar` / `.user-avatar-lg`).
- Swapped all render sites: `base.html` topbar, `users`/`members`/`trainers` list+view, `members/my_profile`, and the admin/manager/member/trainer dashboards.

---

## Trainer Requests — Member ↔ Trainer assignment (Added 2026-07-26)

### Behavior
A member requests a specific trainer; that trainer (or an Admin) accepts/rejects. An accepted request IS the member↔trainer assignment that drives the trainer's "My Members". Design decisions (confirmed with the user):
- **One open request at a time** — a PENDING *or* ACCEPTED request blocks a new one (`TrainerRequest.open_for_member()`). REJECTED/CANCELLED/ENDED do not block, so a member can re-request.
- **Member can leave** an accepted trainer (→ ENDED, frees them to re-request); a Trainer/Admin can also remove a member (→ ENDED).
- **Accept/Reject = Admin or the owning Trainer only** (Manager cannot act). **Manager gets read-only** oversight (list + detail, no action buttons) — needed so the new-request bell notification they receive isn't a dead link.
- **New request notifies** the chosen trainer (direct, deep-links to the request) **and** all admins/managers (deep-links to the oversight list).

### Model (app/models/trainer_request.py)
- `TrainerRequest` (trainer_requests): member_id (FK members), trainer_id (FK trainers), status (enum), message (member's note), response_note (trainer/admin note, esp. reject reason), requested_at, responded_at/responded_by_id, ended_at/ended_by_id, audit fields. Member.trainer_requests / Trainer.trainer_requests dynamic backrefs.
- `TrainerRequestStatus` enum: PENDING/ACCEPTED/REJECTED/CANCELLED/ENDED (label + badge_class). `OPEN_STATUSES = (PENDING, ACCEPTED)`; `open_for_member(member_id)` classmethod.
- `NotificationAudience.SINGLE_TRAINER` added (directed one-trainer notice, same programmatic-only pattern as SINGLE_MEMBER — NOT in the compose form's hardcoded choices).

### Blueprint (/trainer-requests) — app/blueprints/trainer_requests/routes.py
- Member: GET `/find` (trainer directory + request), POST `/request` (create; guards one-open-request + trainer availability), GET `/my` (current + history), POST `/<id>/cancel` (withdraw PENDING), POST `/<id>/leave` (end ACCEPTED).
- Trainer: GET `/incoming` (pending inbox + recent), GET `/my-members` (accepted), POST `/<id>/remove` (staff-side end of ACCEPTED).
- Shared: GET `/<id>` (detail + **member's full details** — profile/membership/recent attendance; `_can_view` = admin/manager/owning-trainer/owning-member), POST `/<id>/accept`, POST `/<id>/reject` (`_can_act` = admin or owning trainer; reject reason optional via modal).
- Admin oversight: GET `/` (`@admin_or_manager_required`; status tabs default **pending** + search + stats; Manager view-only — "Review" button only for `current_user.is_admin`).
- Notification helpers mirror the payments/membership pattern: `_notify_new_request` (trainer SINGLE_TRAINER + staff ADMINS_MANAGERS, both with `link_url`), `_notify_member_of_response` (accept/reject → SINGLE_MEMBER), `_notify_trainer_of_member_action` (cancel/leave → trainer), `_notify_member_of_removal` (staff removed → member). All `is_auto=False`.

### Wiring
- `app/__init__.py`: blueprint registered; `inject_trainer_request_counts` context processor → `trainer_pending_requests` (trainer's PENDING count) for the sidebar badge.
- Sidebar (base.html): Trainer section — activated the old "My Members (Soon)" placeholder into live **Requests** (red pending badge) + **My Members**; Member section — **My Trainer** (after My Schedule); Admin + Manager — **Trainer Requests** (after Trainers).
- Templates under `templates/trainer_requests/`: find, my, incoming, my_members, detail, list.
- `my_members.html` links each member to `schedules.create_schedule?member_id=` (trainer can jump straight to scheduling an accepted member).

### DB migration (manual — no Alembic)
`flask create-tables` (`db.create_all()`) created the new `trainer_requests` table + its `trainerrequeststatus` enum type. The one existing-type change:
```sql
ALTER TYPE notificationaudience ADD VALUE IF NOT EXISTS 'SINGLE_TRAINER';  -- outside a txn block
```

### Not done (possible follow-ups)
- Member dashboard / My Profile still don't surface the assigned trainer (only the new My Trainer page does).
- Schedules aren't restricted to a trainer's accepted members (any trainer can still schedule any member) — the assignment is informational, not an access gate.

---

## Payroll → Expenses Link (Added 2026-07-27)

### Design decision
Marking a Payroll record PAID now auto-creates a matching Expense record, so the Expenses module (and the Profit Report) reflect the real cost of running the gym — salaries are a cash outflow like rent/utilities and were previously invisible to both. Trigger point is **mark-paid**, not creation, since that's the moment money actually left the business (mirrors how Payment/Membership verification already treats staff-confirmed state changes over trust-on-submission).

### Model changes (app/models/expense.py)
- New `ExpenseCategory.SALARY` value (label "Salary", badge_class `success`).
- `Expense.payroll_id` — nullable, unique FK to `payroll.id`; set only on auto-generated rows. `payroll` relationship with `backref='expense'` (one-to-one, `uselist=False`). `Expense.is_payroll_generated` property (`payroll_id is not None`).
- **Locked**: `edit_expense`/`archive_expense` (`app/blueprints/expenses/routes.py`) both reject payroll-generated expenses with a flash + redirect back to the view page — keeps the two records from drifting apart. Since a PAID Payroll record can't itself be edited/cancelled (PENDING-only guard, pre-existing), there's no reversal path to build.

### Payroll routes (app/blueprints/payroll/routes.py)
`mark_paid()` — after flipping the record to PAID, creates one `Expense(category=SALARY, amount=record.net_amount, expense_date=record.payment_date, payroll_id=record.id, ...)` in the same commit.

### Reports (app/blueprints/reports/routes.py) — double-counting guard
`profit_report()` already summed PAID payroll separately (`payroll_expense_total`) from all Expenses (`other_expense_total`). Both `other_expense_total` and `expense_by_category` now filter `Expense.payroll_id.is_(None)` — without this, every payroll payout would be counted twice in `expense_total` (once as payroll, once as an Expense row). The "Other Expenses by Category" panel is unaffected in meaning — it already excluded payroll conceptually, this just keeps it true in practice.

### Templates
- `expenses/view.html` — Edit/Archive buttons hidden for payroll-generated rows; shows a "View Payroll Record" button + an info alert linking back to the source Payroll record instead.
- `expenses/list.html` — lock icon next to the description for payroll-generated rows; subtitle updated to mention salaries are now included.
- `payroll/view.html` — PAID records show a link to the generated Expense record (admin-only — Expenses stays `@admin_required`, so the link is gated on `current_user.is_admin`, not the broader `has_list_access` which also covers Manager).

### DB migration (manual — no Alembic)
```sql
ALTER TABLE expenses ADD COLUMN payroll_id INTEGER REFERENCES payroll(id);
ALTER TABLE expenses ADD CONSTRAINT expenses_payroll_id_key UNIQUE (payroll_id);
ALTER TYPE expensecategory ADD VALUE 'SALARY';  -- outside a txn block
```
**Gotcha:** this project's `db.Enum(PythonEnum)` columns store the Python enum **member name** (e.g. `RENT`, `SALARY`), not `.value` (`rent`, `salary`) — confirmed from existing rows. A stray lowercase `'salary'` value was mistakenly added to the `expensecategory` Postgres enum type before catching this; it's harmless (the app only ever writes `'SALARY'`) but Postgres has no `DROP VALUE` for enums, so it's permanently there as dead label. Double-check casing against existing enum rows before adding new Postgres enum values by hand.

### Payroll-paid notification (Added 2026-07-27)
`mark_paid()` also fires an in-app notice to the staff member being paid (Admin/Manager/Trainer — whoever the record belongs to), so they know their salary landed, not just that it's logged internally. Mirrors the `_notify_member_of_rejection`/`_notify_member_of_activation` pattern in `payments/routes.py`: build `Notification`, flush, `dispatch_notification(notification, [record.user])`, commit — fired after the payroll+expense commit succeeds, not inside the same transaction.
- New `NotificationAudience.SINGLE_STAFF` ('single_staff', label "Direct Notice (Staff)") — programmatic-only, same as `SINGLE_MEMBER`/`SINGLE_TRAINER`; not added to the compose form's hardcoded audience choices.
- `_notify_staff_of_payroll_paid(record)` in `app/blueprints/payroll/routes.py` — message quotes period, net amount, method, payment date; `link_url` points at `payroll.view_payroll` (the staff member can view their own record even without list access, per the existing `is_staff_self` guard on that route).
- DB: `ALTER TYPE notificationaudience ADD VALUE IF NOT EXISTS 'SINGLE_STAFF';` (outside a txn block).

---

## Package Installments (Added 2026-07-27)

### Design decision
Installments are opt-in per Package from a global menu, and collected exclusively through the
existing bank-transfer-held-for-verification flow — not PayHere, which has no recurring/split
API in use here. Membership access is granted in full for the entire package duration the moment
installment #1 is verified (mirrors the existing "full access upfront" bank-transfer behavior);
later installments are purely a collection/reminder concern and never gate or suspend access.

### Configuration (app/models/configuration.py)
- `AppConfiguration.installment_options` — CSV string of globally allowed installment counts, e.g.
  `"2,3,4,6,12"`. A count of 1 is never stored (that's just paying in full).
- `AppConfiguration.parse_installment_options(raw)` (staticmethod) — parses/validates/sorts a CSV
  string into a list of ints >= 2; shared by the Configuration form and `Package.installment_options_list`.
- `/configuration/` gained an "Installment Options" field in the same form/page as Bank Transfer Details.

### Package model (app/models/package.py)
- `allow_installments` (Boolean) + `installment_options` (CSV subset of the global list, e.g. `"2,4"`).
- `installment_options_list` property — this package's offered counts (empty if `allow_installments` is off).
- `PackageForm` (packages/forms.py) — `allow_installments` checkbox + `installment_options`
  `SelectMultipleField` (coerce=int) rendered as a checkbox group; choices populated from
  `AppConfiguration.get().installment_options_list` in `__init__`. Validates at least one count is
  selected when `allow_installments` is checked. If the global list is empty, create/edit show a
  message linking to Configuration instead of an empty checkbox group.

### Models (app/models/installment.py)
- `InstallmentPlan` (installment_plans table) — one per Membership sold on installments:
  `membership_id` (unique FK), `member_id`, `package_id`, `total_amount`, `installment_count`,
  `status` (`InstallmentPlanStatus`: ACTIVE/COMPLETED/CANCELLED). `paid_count`, `paid_amount`,
  `remaining_amount`, `next_due` (earliest non-PAID installment), `progress_label` ("2 of 4 paid").
  - `InstallmentPlan.split_amount(total, count)` (staticmethod) — splits into 2dp amounts that sum
    back exactly to the total (Decimal, `ROUND_HALF_UP`); the **last** installment absorbs the
    rounding remainder so e.g. 100,000 / 3 → 33333.33, 33333.33, 33333.34.
  - `InstallmentPlan.build_due_dates(start_date, end_date, count)` (staticmethod) — evenly spaces
    `count` due dates across the membership's day-span (day-based, not calendar-month-based, so it
    works regardless of whether `duration_months` divides evenly by `count`); installment #1 is
    always due on `start_date`. E.g. a 12-month package (Jan 1 → Dec 31) split 4 ways lands on
    ~Jan 1 / Apr 2 / Jul 2 / Oct 1 — "every ~3 months" as specified, computed from the actual day span.
- `Installment` (installments table) — one row per due slot: `plan_id`, `sequence_no` (1-based),
  `amount`, `due_date`, `status` (`InstallmentStatus`: PENDING/SUBMITTED/PAID — SUBMITTED mirrors
  `PaymentStatus.PENDING`, i.e. "awaiting staff verification"), `paid_at`, `last_reminded_at`
  (dedup marker for the reminder job). `is_overdue`, `active_payment` (most recent non-REJECTED
  Payment against this slot).
- `Payment.installment_id` (nullable FK) — set only when a Payment is collecting one specific
  installment slot; `Payment.installment` relationship (backref `Installment.payments`, dynamic).

### Bank-transfer flow (app/blueprints/payments/routes.py)
- `buy()` — package cards carry `data-installments="2,4"`; after picking a package+date, a
  "Payment Plan" radio group appears (Pay in Full / Nx Installments) built client-side from that
  package's data attribute. Selecting an installment count >1 disables/hides the PayHere button
  (no recurring support) and appends `&installments=N` to the Bank Transfer button's URL; the
  summary shows "amount × N" instead of the flat total.
- `_resolve_installment_count(package, raw)` — validates the `installments` query/form param
  against `package.installment_options_list`; returns 0 (pay in full) if missing/invalid/not offered.
- `bank_transfer()` — when `installment_count` is resolved: creates the PENDING Membership (full
  term, same as today) + an `InstallmentPlan` + all `Installment` rows (via `split_amount`/
  `build_due_dates`) in the same transaction, marks installment #1 `SUBMITTED`, and the submitted
  Payment's `amount` is installment #1's amount (not the full package price) with `installment_id`
  set. `bank_transfer.html` shows the "amount to transfer now" + the full schedule table when an
  installment plan is being created.
- `GET/POST /payments/installment/<id>/pay` (new route, `pay_installment()`) — member-facing,
  reused for installment #2 onward: same reference-number submission pattern as `bank_transfer()`,
  creates a Payment (PENDING, `installment_id` set, `amount` = that slot's amount) and flips the
  Installment to SUBMITTED. Guards: owning member only, plan must be ACTIVE, installment must not
  already be PAID/SUBMITTED, and **installments must be paid in order** (blocks paying #3 while #2
  is still outstanding) — enforced via `plan.next_due`. Template: `payments/pay_installment.html`.

### Verify/Reject — installment-aware branching (`verify_payment`/`reject_payment`/`cancel_request`)
The key asymmetry: **installment #1 IS the thing that grants access** (same as a plain bank
transfer), so verifying/rejecting it activates/cancels the whole Membership+Plan exactly like
before. **Installment #2+ is just a collection event** on an already-active membership — verifying
it only marks that slot PAID (and completes the plan if it was the last one); rejecting or
member-cancelling it only reverts that slot back to PENDING (so the member can resubmit) and never
touches the Membership or the Plan. Distinguished via `payment.installment.sequence_no > 1`.
- `verify_payment()` — additionally sets `Installment.status = PAID` + `paid_at`; completes the
  `InstallmentPlan` (→ COMPLETED) once `paid_count >= installment_count`. Notifies via the new
  `_notify_member_of_installment_verified()` instead of `_notify_member_of_activation()` when
  `payment.installment` is set (message differs for "membership now active" vs. "installment X of N
  received, next due...").
- `reject_payment()` / `cancel_request()` — both gained the `is_later_installment` branch described
  above. `_notify_member_of_rejection()` and `_notify_staff_of_request_cancellation()` messages
  adapt their wording (installment-specific vs. whole-membership) based on the same check.
- New notify helper `_notify_staff_of_installment_submission()` — ADMINS_MANAGERS notice when a
  member submits installment #2+ (mirrors `_notify_staff_of_membership_request()` for #1).

### Reminders (app/blueprints/notifications/service.py)
- `send_installment_reminders()` — notifies members whose next installment is due within
  `INSTALLMENT_LOOKAHEAD_DAYS` (3) or already overdue; skipped if reminded within the last
  `INSTALLMENT_REMINDER_COOLDOWN_DAYS` (7, tracked via `Installment.last_reminded_at` — a per-row
  dedup marker rather than the log-scan approach `send_expiry_reminders()` uses, since amounts/dates
  differ per member so each gets its own `Notification` rather than one shared broadcast). No SMS
  (SMS stays payment-confirmation-only). `link_url` is a hardcoded relative path
  (`/payments/installment/<id>/pay`) rather than `url_for(...)`, since this job runs outside a
  request context (CLI/scheduler, only `app.app_context()`) where `url_for` would fail.
- `flask send-installment-reminders` CLI command (run.py) + wired into the existing daily
  `run_daily_expiry_job` in `app/scheduler.py` (runs right after the expiry-reminder job).

### Templates
- `memberships/view.html` — new "Installment Plan" card (progress bar, per-slot table with a Pay
  button on the member's own next-due row) shown whenever `membership.installment_plan` exists.
- `memberships/my_memberships.html` + `dashboard/member.html` — the active-plan card gets a compact
  "Installment X of N due <date> [Pay Now]" banner when a next-due PENDING installment exists.
- `payments/view.html` / `payments/list.html` — installment badge ("Inst. 2/4") next to the
  reference number; the verify-modal wording adapts for installment #2+.
- `packages/list.html` / `packages/view.html` — installment-count badges shown when offered.

### DB migration (manual — no Alembic in this project)
`installment_plans` and `installments` are brand-new tables, so `flask create-tables`
(`db.create_all()`) picked them up without manual DDL. Existing tables needed manual `ALTER TABLE`:
```sql
ALTER TABLE app_configuration ADD COLUMN IF NOT EXISTS installment_options VARCHAR(100);
ALTER TABLE packages ADD COLUMN IF NOT EXISTS allow_installments BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE packages ADD COLUMN IF NOT EXISTS installment_options VARCHAR(100);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS installment_id INTEGER REFERENCES installments(id);
```
Both `installmentplanstatus` and `installmentstatus` are brand-new Postgres enum types (created by
`create_all()` alongside their tables), so no `ALTER TYPE ... ADD VALUE` was needed this time.

### Not done (possible follow-ups)
- No grace-period/auto-suspend if an installment goes unpaid — access was deliberately never gated
  on staying current (see Design decision above); this is enforced only by convention.
- No cap on how long installment #2+ can stay overdue before staff manually cancel the plan by hand.
- Payments list revenue stats (`total_revenue`, `this_month_revenue`) already sum by `amount`
  regardless of installment — an installment plan's revenue naturally trickles in per verified slot
  rather than all at once, which matches actual cash received.

---

## QR-Based Attendance Scan (Added 2026-07-29)

### Design decision
Fully offline — no internet, no cloud, no external CDN calls at runtime. The scanning
kiosk is meant to be a dedicated reception PC/tablet with the browser open at
`http://localhost:5000/attendance/scan` (logged in once as staff, left open all day),
because browsers only grant camera access (`getUserMedia`) on a "secure context" —
`https://` or `http://localhost` — and a plain LAN address (e.g. `http://192.168.1.20:5000`)
gets silently blocked regardless of whether the internet is up. Using `localhost` sidesteps
that entirely with zero certificate setup. The QR encodes the member's **plain numeric ID**
(a deliberate simplicity-over-forgery-resistance tradeoff — low risk since this only affects
attendance records, not payments/access).

### No schema changes
Reuses the existing `Attendance` model (`member_id`, `check_in`, `check_out` nullable) as-is.
The scan endpoint just toggles: the member's most recent Attendance row today with no
`check_out` yet → this scan sets `check_out`; otherwise → a new row is created with
`check_in = now`. First scan of the day naturally becomes check-in, and whichever scan ends
up last for the day is the checkout (or stays open if they forgot to scan out — same as the
existing manual-entry behavior).

### Two input paths into the same endpoint (app/blueprints/attendance/routes.py)
- **Camera scanning** — `templates/attendance/scan.html` captures the video feed to a
  canvas every animation frame and decodes with **jsQR**, vendored locally at
  `app/static/vendor/jsQR.min.js` (Apache-2.0, see `jsQR.LICENSE.txt` in the same folder) —
  fetched once during development and committed, so the kiosk page has zero CDN/internet
  dependency at runtime. On a decode, POSTs `{code}` to `/attendance/scan`.
- **Handheld USB/Bluetooth barcode scanner (or manual typing)** — an auto-focused text
  input on the same page; a "keyboard wedge" scanner types the decoded text + Enter into
  it with no camera/JS decoding involved at all, sidestepping the secure-context requirement
  completely. Works with QR or 1D barcodes equally since it's just keystrokes. Recommended
  as the more robust option for a fixed reception station — a $15–30 device with no browser
  permission fuss.
- Both paths call the same client-side `submitCode()` → same `POST /attendance/scan` JSON API.

### Routes (app/blueprints/attendance/routes.py) — `@admin_manager_or_trainer_required`
- `GET /attendance/scan` (`scan_kiosk`) — renders the kiosk page.
- `POST /attendance/scan` (`scan_submit`) — JSON `{code}` in, JSON `{ok, action, member,
  message, time}` out. Validates the code is a plain int, resolves `Member.query.get(id)`,
  rejects archived members / inactive user accounts. `SCAN_DEBOUNCE_SECONDS = 8` — if the
  member's last attendance event (check-in or check-out) was less than 8s ago, the scan is
  treated as a duplicate decode of the same card still in front of the camera and returns the
  existing state without toggling again (client-side also debounces per decoded code for 4s,
  to avoid hammering the endpoint every ~16ms while a card sits in view — belt and suspenders).
- CSRF: the JSON POST carries the token via the `X-CSRFToken` header (Flask-WTF's
  `CSRFProtect` checks this header by default for AJAX requests — no `@csrf.exempt` needed,
  unlike the PayHere notify webhook).

### Member QR cards (app/blueprints/members/routes.py)
- `GET /members/<id>/qr-card` (`qr_card`) — Admin/Manager; generates a QR PNG (via the
  `qrcode` package, encoding `str(member.id)`) as a base64 data URI, rendered in
  `templates/members/qr_card.html` — a printable card (`window.print()` button) with
  `@media print` CSS hiding the sidebar/topbar/buttons so only the card prints.
  `qrcode`'s default PIL image backend needs Pillow, already present transitively via
  reportlab — no explicit Pillow pin added to requirements.txt to avoid fighting that
  existing resolution.
- Linked from `members/view.html` next to the existing Edit/Archive buttons ("Print QR Card").

### Sidebar (templates/base.html)
Admin/Manager/Trainer sections each gained a **"Scan Attendance"** nav-item (icon
`fa-qrcode`) right after the existing "Attendance" link, `active` on the exact
`attendance.scan_kiosk` endpoint (the existing "Attendance" link's `startswith('attendance.')`
check was narrowed to exclude it, so the two links don't both highlight at once).

### Hardware/setup notes (from the feasibility study this was built from)
- **Chosen setup**: dedicated reception PC/tablet, not members' own phones — avoids the
  self-signed-cert-per-device onboarding friction that BYOD phone scanning over LAN would need.
- QR over 1D barcode for camera decoding specifically — QR's error correction handles a
  webcam's angle/lighting/distance variance far better; 1D really wants a dedicated scanner
  (which the USB-wedge path already provides either symbology for, camera-free).
- Not done: no signed/opaque per-member token (plain ID chosen for simplicity — see Design
  decision above); no bulk "print all QR cards" page (per-member only for now); no rate-limit
  beyond the 8s debounce.

---

## All SRS modules complete
3.1–3.14 are all implemented. Remaining SRS work: none (optional polish/reports only).
