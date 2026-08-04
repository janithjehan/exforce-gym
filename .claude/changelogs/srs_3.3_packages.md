# SRS 3.3 — Packages Module Changelog

## Requirements Implemented
- FR-PKG-01: `duration_months` field — supports 1, 3, 6, 12 month choices via DURATION_CHOICES constant
- FR-PKG-02: All create/modify routes protected by `@admin_required`
- FR-PKG-03: `is_active` flag — inactive packages blocked at membership assignment time (enforced in Memberships module)

---

## [+] NEW FILES CREATED

app/models/package.py
  - DURATION_CHOICES constant: [(1,'1 Month'), (3,'3 Months'), (6,'6 Months'), (12,'12 Months')]
  - Package model (packages table)
      name, duration_months (int), price Numeric(10,2), description
      is_active, is_archived, audit fields
  - duration_label property — human-readable string from DURATION_CHOICES
  - status_label property — 'Active' / 'Inactive'
  - status_badge_class property — 'success' / 'secondary'

app/blueprints/packages/__init__.py
  - packages_bp Blueprint definition

app/blueprints/packages/forms.py
  - PackageForm (used for both create and edit)
      name, duration_months (SelectField from DURATION_CHOICES), price, description
  - Validators: name unique check on create; price > 0

app/blueprints/packages/routes.py
  - GET  /packages/                  list_packages     — tabs: active / inactive / all
  - GET/POST /packages/create        create_package    — admin only
  - GET  /packages/<id>              view_package      — shows linked memberships count
  - GET/POST /packages/<id>/edit     edit_package      — blocked if archived
  - POST /packages/<id>/toggle-status  toggle_status   — activate ↔ deactivate
  - POST /packages/<id>/archive      archive_package   — soft delete, sets is_active=False

templates/packages/list.html
  - Active / Inactive / All tab filter
  - Table: name, duration label, price (LKR), status badge, active memberships count, actions

templates/packages/create.html
  - Single-panel form: name, duration (select), price, description
  - Breadcrumb navigation

templates/packages/view.html
  - Package details card: name, duration, price, description, status
  - Toggle status button + Archive button (admin only)
  - Linked active memberships list

templates/packages/edit.html
  - Same form as create, pre-filled with current values
  - Blocked with alert if package is archived

---

## [~] EXISTING FILES EDITED

app/models/__init__.py
  - Added export: Package

app/__init__.py
  - Imported packages_bp
  - Registered blueprint: url_prefix='/packages'

templates/base.html
  - Admin sidebar: activated Packages nav link (was "Soon")

templates/dashboard/admin.html
  - No stat changes in 3.3 (packages count not on dashboard)
  - Quick action "Add User / Staff" was already present from 3.1

CLAUDE.md
  - Added full SRS 3.3 module reference section
  - Updated Registered Blueprints table to include /packages
  - Updated Next Modules list
