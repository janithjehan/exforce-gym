# Exforce GMS — Modules, Relationships & Limitations

**Last updated:** 2026-07-24
**Purpose:** A map of what each module covers, how the modules relate to one another, and the known limitations / scope boundaries of each. For the current defect list see [`bugs.md`](./bugs.md); for implementation-level notes see [`CLAUDE.md`](./CLAUDE.md).

---

## 1. System overview

| Aspect | Detail |
|--------|--------|
| Framework | Flask 3.0 (application-factory pattern, `create_app` in `app/__init__.py`) |
| ORM / DB | Flask-SQLAlchemy over PostgreSQL |
| Schema management | **None** — tables via `flask create-tables` (`db.create_all()`); column/enum changes applied by hand-written `ALTER` statements. No Alembic/Flask-Migrate. |
| Auth | Flask-Login (session cookie), Flask-Bcrypt password hashing, 2-hour sliding idle timeout |
| Forms / CSRF | Flask-WTF (`CSRFProtect` app-wide; only PayHere `/notify` is exempt — it's hash-verified) |
| Templates | Jinja2 + Bootstrap 5; one shared `templates/base.html` (sidebar per role + topbar) |
| External services | PayHere (card gateway), Notify.lk (SMS — payment confirmations only), SMTP (password-reset email only) |
| Background jobs | APScheduler in-process (daily membership expiry + expiry reminders); same logic exposed as CLI |
| Roles | `ADMIN`, `MANAGER`, `TRAINER`, `MEMBER` (`UserRole` enum) |

### Role model (who owns what)
- **Admin** — owns the *system*: user accounts, roles, credentials, packages, configuration. Full access.
- **Manager** — owns the *gym floor* (operations): members, memberships, payments, attendance, payroll, trainer management (but **cannot** create user/trainer accounts or change roles, and has no `/users` access).
- **Trainer** — delivers training: own profile, workouts, schedules, equipment/attendance visibility.
- **Member** — self-service: own profile, buy/renew membership, view own attendance/measurements/schedules, submit feedback, receive notifications.

### Blueprint / route map (`app/__init__.py`)

| Prefix | Blueprint | Primary access |
|--------|-----------|----------------|
| `/auth` | auth | Public |
| `/users` | users | Admin only |
| `/members` | members | Admin + Manager / Member-own |
| `/packages` | packages | Admin + Manager |
| `/memberships` | memberships | Admin + Manager / Member-own |
| `/payments` | payments | Admin + Manager / Member self-service (buy, bank-transfer) |
| `/attendance` | attendance | Admin + Manager + Trainer / Member-own |
| `/trainers` | trainers | Admin + Manager / Trainer-own |
| `/workouts` | workouts | Admin + Trainer |
| `/schedules` | schedules | Admin + Trainer manage, Manager view, Member-own |
| `/equipment` | equipment | Admin manage, Manager + Trainer view |
| `/supplements` | supplements | Admin manage, Manager view, Member catalog (flag-gated) |
| `/measurements` | measurements | Admin + Member-own only |
| `/feedback` | feedback | Admin manage / Member submit + own |
| `/notifications` | notifications | Admin + Manager compose; **every role** has a personal inbox |
| `/payroll` | payroll | Admin + Manager (self-guarded); Manager/Trainer own history |
| `/expenses` | expenses | Admin only |
| `/reports` | reports | Admin + Manager |
| `/configuration` | configuration | Admin only |
| `/dashboard` | dashboard | Any logged-in (role-specific) |

---

## 2. Data model & relationships

`User` is the hub. `Member` and `Trainer` are 1:1 profile extensions of `User` (one `user_id`, unique). Almost every table carries `created_by_id` / `updated_by_id` → `users` for audit. Enum-typed status columns are stored as Postgres enum types.

```
User (users)  ─ role: ADMIN|MANAGER|TRAINER|MEMBER
 ├─1:1─ Member (members.user_id)
 │        ├─<─ Membership (member_id) ──>─ Package (package_id)
 │        │        └─<─ Payment (membership_id, nullable)
 │        ├─<─ Payment (member_id) ──<─ PaymentEditLog
 │        ├─<─ Attendance (member_id)
 │        ├─<─ Measurement (member_id) ──<─ MeasurementEditLog
 │        ├─<─ Feedback (member_id, responded_by_id→User)
 │        └─<─ Schedule (member_id)
 ├─1:1─ Trainer (trainers.user_id)
 │        └─<─ Schedule (trainer_id)
 ├─<─ Payroll (user_id = staff paid) ──<─ PayrollEditLog
 ├─<─ NotificationLog (recipient_id)          ← any role
 └─<─ LoginActivityLog (user_id)

Schedule (schedules)
 ├─<─ ScheduleItem (schedule_id) ──>─ Workout (workout_id)
 └─<─ ScheduleEditLog (schedule_id)

Notification (notifications, package_id nullable→Package)
 └─<─ NotificationLog (notification_id, recipient_id→User)

Standalone catalogs / records (audit FKs to User only):
  Package · Workout · Equipment · Supplement · Expense · AppConfiguration (singleton)
```

Key cardinalities: a Member has many Memberships (history); at most one should be currently ACTIVE (enforced in code, not by a DB constraint). A Payment optionally links to one Membership. A Schedule has one Member + one Trainer and many ScheduleItems, each referencing one Workout.

---

## 3. Module reference

Each entry: **Covers** (scope) · **Models** · **Relates to** · **Limitations** (scope boundaries & design constraints; discrete defects are in `bugs.md`).

### 3.1 Authentication (`/auth`)
- **Covers:** Login (username *or* email), logout, public self-registration (creates a MEMBER + empty Member profile), change-password, forgot-password → emailed reset link, token-based reset. Login-activity logging.
- **Models:** `User`, `LoginActivityLog`.
- **Relates to:** Users, Members (auto-creates a Member profile on register); Mailer util for reset email; Tokens util (`itsdangerous`, self-invalidating on password change).
- **Limitations:** No rate limiting anywhere (forgot-password and login are unthrottled — brute-force / reset-spam possible). Self-registration is intentionally minimal (name/username/email/password only — no NIC/phone), so a self-registered member must complete their profile later. Email delivery no-ops to the log when SMTP is unconfigured.

### 3.2 Users (`/users`) — Admin only
- **Covers:** Full staff/member account CRUD, activate/deactivate/archive, admin password reset, role assignment. Auto-creates a Member/Trainer profile when a user is created (or role-changed) to MEMBER/TRAINER. Initial password = NIC.
- **Models:** `User`, `LoginActivityLog`.
- **Relates to:** Members, Trainers (profile auto-creation); central to RBAC.
- **Limitations:** No migration path for the `userrole` enum (a new role needs a manual `ALTER TYPE`). Uniqueness (username/email/NIC) is enforced at the form layer, not always by DB constraints, so concurrent inserts can still collide. Several guard gaps exist on the edit path (see `bugs.md` #1, #2, #18).

### 3.3 Members (`/members`) — Admin + Manager / Member-own
- **Covers:** Member profile CRUD, archive/restore (also toggles the linked User's active state), member self-edit (`/my-profile/edit`), self-view. NIC drives DOB/gender derivation.
- **Models:** `Member` (1:1 `User`).
- **Relates to:** Memberships, Payments, Attendance, Measurements, Feedback, Schedules all hang off `Member`. `is_active_member` depends on Membership.
- **Limitations:** `contact_no` (Member) and `phone` (User) are two fields kept in sync in code — no single source of truth. Archiving is soft-delete only (no hard delete). See `bugs.md` #3 (Trainer can view any member).

### 3.4 Packages (`/packages`) — Admin + Manager
- **Covers:** Membership plan catalog (name, duration 1/3/6/12 months, price, active/archived flags).
- **Models:** `Package`.
- **Relates to:** Memberships (assignment), Notifications (package-targeted audience), Payments (indirectly via membership).
- **Limitations:** Duration limited to the fixed choice set. Inactive/archived packages are blocked at assignment time only; existing memberships on a since-deactivated package are unaffected. No price history — editing a package price changes it for all future assignments with no versioning.

### 3.5 Memberships (`/memberships`) — Admin + Manager / Member-own
- **Covers:** Assigning a package to a member, renew (extends from current end date), cancel, status tracking (ACTIVE / EXPIRED / CANCELLED / PENDING). Daily bulk-expiry job. PENDING is the "awaiting bank-transfer verification" state.
- **Models:** `Membership` (member_id, package_id).
- **Relates to:** Packages, Payments (a verified payment activates a PENDING membership; PayHere/bank-transfer create membership + payment together), Member dashboard.
- **Limitations:** "One active membership at a time" is a code-level rule, not a DB constraint, and doesn't account for PENDING (see `bugs.md` #7, #9). Renewal doesn't clamp to today for lapsed plans (#8). No proration, no partial refunds, no freeze/hold state.

### 3.6 Payments (`/payments`) — Admin + Manager + Member self-service
- **Covers:** Manual payment entry (cash/card/bank transfer/online) with full edit-audit; PayHere hosted-checkout self-service (buy → checkout → server `/notify` → return/cancel); member Bank-Transfer submission (reference no. → PENDING) with Admin/Manager verify/reject; payment confirmation SMS.
- **Models:** `Payment` (member_id, membership_id?), `PaymentEditLog`. Enums: `PaymentMethod`, `PaymentStatus` (PENDING/VERIFIED/REJECTED).
- **Relates to:** Members, Memberships (creation/activation), Configuration (bank details shown to members), Notifications (rejection notice), Reports/Dashboards (revenue), SMS util.
- **Limitations:** PayHere secret is per-domain and dev is `localhost`-only (needs ngrok for `/notify`). Notify idempotency is best-effort, not atomic (`bugs.md` #15). Manual membership-linking is currently broken (#4). Revenue is only correctly VERIFIED-filtered in the payments list, not in dashboards/reports (#5). No refund/void/chargeback flow — a wrong payment can only be edited or offset manually.

### 3.7 Attendance (`/attendance`) — Admin + Manager + Trainer / Member-own
- **Covers:** Manual check-in / check-out, auto-computed duration, list with date + name filters, member self-history.
- **Models:** `Attendance` (member_id).
- **Relates to:** Members; surfaced on Member dashboard + member view.
- **Limitations:** Entirely manual entry — no turnstile/RFID/biometric integration. No guard against a future check-in time (`bugs.md` #19). No concept of an open "currently in gym" session beyond "checked in, not yet out".

### 3.8 Trainers (`/trainers`) — Admin + Manager / Trainer-own
- **Covers:** Trainer profile CRUD (specialization, bio, experience, certifications, contact), archive/restore (toggles User active), trainer self-edit. Auto-created when a user is made a TRAINER.
- **Models:** `Trainer` (1:1 `User`).
- **Relates to:** Users, Schedules (trainer_id).
- **Limitations:** Trainer↔Member assignment ("my members") is not implemented (sidebar placeholder). Manager management is authorized server-side but hidden in the UI (`bugs.md` #13); edit form doesn't enforce the mobile-number requirement (#12).

### 3.9 Workouts (`/workouts`) — Admin + Trainer
- **Covers:** Exercise catalog (type, muscle group, difficulty, equipment-needed free text, instructions), active/archived.
- **Models:** `Workout`.
- **Relates to:** Schedules (each ScheduleItem references a Workout).
- **Limitations:** No media (images/video). `equipment_needed` is free text, not linked to the Equipment module. Archiving a workout doesn't affect schedules already referencing it.

### 3.10 Schedules (`/schedules`) — Admin + Trainer manage / Manager view / Member-own
- **Covers:** Training plans = Member + Trainer + date range + ordered ScheduleItems (workout, day label, sets, reps, rest, notes). Versioning with an edit log, complete/cancel, member "mark complete", reportlab PDF export.
- **Models:** `Schedule`, `ScheduleItem` (→ Workout), `ScheduleEditLog`.
- **Relates to:** Members, Trainers, Workouts.
- **Limitations:** Editing replaces all items wholesale (bumps version) rather than diffing per item. PDF export escaping is unsafe (`bugs.md` #14) and day-grouping is adjacency-based (#23). No calendar/recurrence — a plan is a static date range.

### 3.11 Equipment (`/equipment`) — Admin manage / Manager + Trainer view
- **Covers:** Inventory (name, category, quantity, available/out-of-service, notes, image upload), status toggle, archive.
- **Models:** `Equipment`.
- **Relates to:** Standalone; visible to trainers for planning (not linked to Workouts programmatically).
- **Limitations:** Images stored on the local filesystem (`app/static/uploads/equipment/`), not object storage — won't survive an ephemeral/multi-instance deploy; old-file deletion is best-effort. No maintenance schedule / service history. Quantity is a single number (no per-unit tracking).

### 3.12 Supplements (`/supplements`) — Admin manage / Manager view / Member catalog
- **Covers:** Product catalog (type, brand, price, stock qty, status), stock update with auto status-sync, member-facing catalog gated by the `SUPPLEMENTS_MEMBER_VIEW` config flag.
- **Models:** `Supplement`.
- **Relates to:** Standalone.
- **Limitations:** Catalog only — **no purchasing/ordering/POS**. Stock is a manual counter (`None` = untracked). No supplier or reorder management.

### 3.13 Measurements (`/measurements`) — Admin + Member-own only
- **Covers:** Body metrics per date (weight/height/chest/waist/hips/arms/thighs), BMI, edit-logged changes, member self-history with a weight trend chart.
- **Models:** `Measurement`, `MeasurementEditLog` (member_id).
- **Relates to:** Members; on Member dashboard.
- **Limitations:** Deliberately **no delete/archive** (edits are logged instead). Access excludes Manager and Trainer by design (a trainer cannot see their trainee's measurements). Fixed metric set (adding a metric is a schema change). Chart needs ≥2 weight entries.

### 3.14 Feedback (`/feedback`) — Admin manage / Member submit + own
- **Covers:** Member feedback (category, 1–5 rating, comments), admin respond + status (NEW/REVIEWED/RESOLVED), member history, CSV export honoring filters. Submission gated to active members.
- **Models:** `Feedback` (member_id, responded_by_id → User).
- **Relates to:** Members, Users (responder).
- **Limitations:** One admin response per item (no threaded conversation). No delete. No member notification when a response is posted (they must revisit `/feedback/my-feedback`).

### 3.15 Notifications (`/notifications`) — Admin + Manager compose / all roles receive
- **Covers:** In-app announcements to a chosen audience (all active members / by package / expiring-soon / **all admins / managers / trainers / staff**) plus system-generated single-member notices (e.g. payment rejection) and automated expiry reminders. Per-recipient read tracking; unread badge (sidebar + topbar bell) for every role.
- **Models:** `Notification`, `NotificationLog` (recipient_id → **User**). Enum `NotificationAudience`.
- **Relates to:** Users (recipients), Members/Memberships/Packages (member-audience resolution), Payments (rejection notice), the daily reminder job.
- **Limitations:** **In-app only** — never SMS/email (SMS is reserved for payment confirmations). No scheduling/expiry of announcements, no edit/recall after sending, no delete. Staff audiences send to *all* users of a role (no individual-staff picker in the compose UI). The `is_auto` flag is overloaded between reminders and rejection notices (`bugs.md` #6).

### 3.16 Payroll (`/payroll`) — Admin + Manager (self-guarded)
- **Covers:** Salary records for Admin/Manager/Trainer per pay period (gross/bonus/deductions → net), status PENDING/PAID/CANCELLED, mark-paid (method + date), cancel, edit-audit, single + bulk creation, staff self-history.
- **Models:** `Payroll` (user_id = staff), `PayrollEditLog`.
- **Relates to:** Users (staff), Reports (paid payroll = expense in profit report).
- **Limitations:** Manual per-period entry — **no recurring/auto-generation** and no "remembered base salary". Deductions is a single free number (no EPF/ETF/tax breakdown) and isn't capped (`bugs.md` #21). No payslip PDF. Members are never payroll subjects.

### 3.17 Expenses (`/expenses`) — Admin only
- **Covers:** Operational expense logging (category, amount, date, notes), archive; feeds the profit report.
- **Models:** `Expense`.
- **Relates to:** Reports (expense side of profit).
- **Limitations:** Admin-only (Manager can see expenses' effect via the Profit Report but cannot log or manage them, unlike most other operational modules). Flat single-entry expenses — no attachments/receipts, no approval workflow, no recurring expenses.

### 3.18 Reports (`/reports`) — Admin + Manager
- **Covers:** A single Profit Report: income (payments) − expenses (paid payroll + logged expenses) over a date range, with breakdowns by payment method / staff role / expense category.
- **Models:** reads `Payment`, `Payroll`, `Expense`, `User`.
- **Relates to:** Payments, Payroll, Expenses.
- **Limitations:** Only one report exists (profit). Income does **not** filter to VERIFIED payments, so pending/rejected transfers inflate it (`bugs.md` #5). No export (screen only), no charts, no membership/attendance analytics.

### 3.19 Configuration (`/configuration`) — Admin only
- **Covers:** Gym-wide settings singleton; currently one field — bank-transfer details shown to members on the bank-transfer payment page.
- **Models:** `AppConfiguration` (singleton).
- **Relates to:** Payments (bank-transfer flow reads it).
- **Limitations:** Single free-text field only (not structured bank fields). Get-or-create has a small duplicate-row race (`bugs.md` #22). Other app settings still live in `.env`/`config.py`, not here.

### 3.20 Dashboard (`/dashboard`)
- **Covers:** Role-specific landing pages (admin/manager/trainer/member) with stat cards + quick actions.
- **Relates to:** Aggregates across most modules.
- **Limitations:** Admin/Manager revenue & net-profit stats don't filter VERIFIED payments (`bugs.md` #5). Trainer/member dashboards are largely static cards (no analytics).

---

## 4. Cross-cutting concerns

- **RBAC** — decorators in `app/utils/decorators.py` (`admin_required`, `admin_or_manager_required`, `admin_or_trainer_required`, `admin_manager_or_trainer_required`, `roles_required`). Applied per-route; member/owner checks are inline in the routes. *Consistency of these checks is the single biggest correctness risk area* (see `bugs.md` #1–#3).
- **Audit logging** — two patterns: `LoginActivityLog` for auth events, and per-module `*EditLog` tables (Payment/Payroll/Measurement/Schedule) capturing field-level before/after on edits.
- **SMS (Notify.lk)** — `app/utils/notifylk.py`; used **only** for payment confirmations (`app/blueprints/payments/sms.py`). Degrades gracefully when unconfigured.
- **Email (SMTP)** — `app/utils/mailer.py`; used **only** for password-reset links. Logs to console when disabled.
- **Scheduling** — `app/scheduler.py` (APScheduler) runs daily membership expiry + expiry reminders, guarded against the Werkzeug reloader double-start; the same jobs are CLI commands in `run.py`.
- **Configuration/secrets** — `config.py` reads `.env` once at startup (PayHere, Notify.lk, SMTP, feature flags). Restart required after `.env` changes.

---

## 5. System-wide limitations

1. **No schema-migration framework.** All schema evolution is `db.create_all()` + hand-written `ALTER TABLE` / `ALTER TYPE`. New columns and new enum values must be applied manually to each environment; there's no version history, rollback, or automated parity check between code and DB. This is the highest-leverage operational risk.
2. **No rate limiting** anywhere (login, forgot-password, PayHere notify). Brute-force and reset-spam are unmitigated.
3. **Money integrity relies on application code, not DB constraints** — "one active membership", payment idempotency, and no-overlap rules are all enforceable only in Python, so races and alternate code paths can violate them (see `bugs.md` #7, #9, #15).
4. **Revenue reporting is inconsistent** about the payment VERIFIED filter across the payments list vs dashboards vs reports (`bugs.md` #5).
5. **Local-filesystem uploads** (equipment images) — not suitable for multi-instance or ephemeral-filesystem hosting without external object storage.
6. **Single-node assumptions** — in-process APScheduler and get-or-create singletons assume one app instance; running multiple workers would double-run jobs and risk duplicate rows.
7. **Search is comma-tokenised only** — natural full-name search fails across list views (`bugs.md` #11).
8. **Notifications are in-app only** and can't be scheduled, edited, recalled, or deleted after sending.
9. **No hard deletes** — everything is soft-delete/archive; there's no data-retention or purge tooling.
10. **PayHere dev constraints** — per-domain secret, `localhost`-only checkout, ngrok required for the `/notify` callback.

> For the actionable, code-level defect list (with locations, reproductions, and suggested fixes) see [`bugs.md`](./bugs.md).
