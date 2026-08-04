# SRS 3.12 — Member Measurement History (2026-07-17)

## SRS Requirements
- **FR-MEAS-01** — Measurement record includes Member, Date, and configurable value fields (weight, height, chest, waist, hips, arms, thighs). All value fields are individually optional; routes require at least one.
- **FR-MEAS-02** — Only the owning Member and Admin can view/edit a member's measurements. Manager and Trainer have no access (403).
- **FR-MEAS-03** — Historically preserved: no delete/archive routes exist at all; every edit writes one `MeasurementEditLog` row per changed field (editor, timestamp, old → new), displayed as Edit History.

## New Files
- `app/models/measurement.py` — `Measurement` + `MeasurementEditLog`
- `app/blueprints/measurements/__init__.py`, `forms.py`, `routes.py`
- `templates/measurements/list.html`, `create.html`, `view.html`, `edit.html`, `my_measurements.html`, `_fields.html` (shared partial)

## Routes
| Route | Method | Access |
|---|---|---|
| `/measurements/` | GET | Admin — search + stats + pagination (15/page) |
| `/measurements/create` | GET/POST | Admin (any member) / Member (self only, forced) |
| `/measurements/<id>` | GET | Admin or owning member |
| `/measurements/<id>/edit` | GET/POST | Admin or owning member — audited diff |
| `/measurements/my-measurements` | GET | Member — history + latest snapshot + Chart.js weight trend |

## Modified Files
- `app/models/__init__.py` — model registration
- `app/__init__.py` — blueprint registration (`/measurements`)
- `app/blueprints/dashboard/routes.py` — member dashboard passes `latest_measurement`
- `templates/base.html` — sidebar: Measurements live for Admin (Operations) + Member (was "Soon")
- `templates/dashboard/admin.html` — module status: Measurements = Live
- `templates/dashboard/member.html` — Latest Measurement card
- `templates/members/view.html` — Recent Measurements section (admin-only)

## DB
- Tables `measurements` and `measurement_edit_logs` created via `flask create-tables`.

## Verified
- All 5 routes register on the URL map
- Both tables present in Postgres
- All new/edited Jinja templates compile