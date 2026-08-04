# SRS 3.4 — Memberships Module Changelog

## Requirements Implemented
- FR-MSHIP-01: `end_date` auto-calculated via `Membership.calculate_end_date(start_date, duration_months)`
- FR-MSHIP-02: Blocked at create time if member already has ACTIVE membership with `end_date >= today`
- FR-MSHIP-03: Renew sets `new_start = current.end_date + 1 day` (extends from end, not today)

---

## [+] NEW FILES CREATED

app/models/membership.py
  - MembershipStatus enum: ACTIVE / EXPIRED / CANCELLED
  - Membership model (memberships table)
  - _add_months() helper — calendar-safe month arithmetic, no dateutil dependency
  - calculate_end_date(start_date, duration_months) static method
  - expire_passed() classmethod — bulk-expires overdue ACTIVE memberships
  - is_currently_active property
  - days_remaining property
  - status_label / status_badge_class properties

app/blueprints/memberships/__init__.py
  - memberships_bp Blueprint definition

app/blueprints/memberships/forms.py
  - MembershipCreateForm: member_id, package_id, start_date, notes
  - validate_start_date: blocks future start dates

app/blueprints/memberships/routes.py
  - GET  /memberships/              list_memberships   — tabs: active/expired/cancelled/all + member search + stats
  - GET/POST /memberships/create    create_membership  — FR-MSHIP-02 guard; ?member_id= pre-fill
  - GET  /memberships/<id>          view_membership    — members can only view their own (403 guard)
  - POST /memberships/<id>/renew    renew_membership   — FR-MSHIP-03: new_start = end_date + 1 day
  - POST /memberships/<id>/cancel   cancel_membership  — sets status=CANCELLED

templates/memberships/list.html
  - Stats row: Active / Expiring in 30 Days / Expired
  - Status tabs + member search form
  - Paginated table: member, package, start, expires (warning if <=30d), status badge, view link

templates/memberships/create.html
  - Two-field form: member dropdown, package dropdown (active only), start date, notes
  - Form hint: end date calculated automatically

templates/memberships/view.html
  - Membership details card: member, package, dates, days remaining, status
  - Renew button (disabled if cancelled) + Cancel button
  - Membership history sidebar: all memberships for this member (highlights current)

---

## [~] EXISTING FILES EDITED

run.py
  - Added CLI command: flask expire-memberships  →  calls Membership.expire_passed()

app/models/__init__.py
  - Added exports: Membership, MembershipStatus

app/__init__.py
  - Imported memberships_bp
  - Registered blueprint: url_prefix='/memberships'

templates/base.html
  - Activated Memberships nav link in admin sidebar (was "Soon" placeholder)

app/blueprints/dashboard/routes.py
  - Added to admin stats: active_memberships, expiring_soon
  - Imported: Membership, MembershipStatus

templates/dashboard/admin.html
  - Added stat card: Active Memberships
  - Added quick action: Assign Membership → url_for('memberships.create_membership')

templates/dashboard/member.html
  - Added membership status card: package name, days remaining, start/end dates
  - Shows "no active plan" state when no membership found

CLAUDE.md
  - Added full SRS 3.4 module reference section
