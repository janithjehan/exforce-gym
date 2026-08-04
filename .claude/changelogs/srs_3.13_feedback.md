# SRS 3.13 — Feedback From Members (2026-07-17)

## SRS Requirements
- **FR-FDB-01** — Feedback record: Member, Date (created_at), Category (optional: Service/Trainers/Facility/Equipment/Other), Rating (1–5), Comments.
- **FR-FDB-02** — Members view their own feedback history at `/feedback/my-feedback`, including admin responses.
- **FR-FDB-03** — Admin exports CSV reports at `/feedback/export`, honouring active list filters.
- **FR-FDB-04** — Only active members (valid ACTIVE membership) can submit; guarded server-side in the route and reflected in the UI.

## New Files
- `app/models/feedback.py` — `Feedback` + `FeedbackCategory` + `FeedbackStatus` enums
- `app/blueprints/feedback/__init__.py`, `forms.py`, `routes.py`
- `templates/feedback/list.html`, `submit.html`, `view.html`, `my_feedback.html`

## Routes
| Route | Method | Access |
|---|---|---|
| `/feedback/` | GET | Admin — status tabs (default "new") + category filter + search + stats |
| `/feedback/submit` | GET/POST | Member with active membership — JS star-rating picker |
| `/feedback/<id>` | GET | Admin or owning member; admin gets respond panel |
| `/feedback/<id>/respond` | POST | Admin — status + optional response (stamps responded_by/at) |
| `/feedback/my-feedback` | GET | Member — own history, 10/page |
| `/feedback/export` | GET | Admin — CSV `feedback_report_YYYYMMDD.csv` |

## Modified Files
- `app/models/__init__.py`, `app/__init__.py` — registrations (`/feedback`)
- `app/blueprints/dashboard/routes.py` — admin stats: `new_feedback` count
- `templates/base.html` — sidebar Feedback live for Admin (Gym Info) + Member (was "Soon")
- `templates/dashboard/admin.html` — "New Feedback" stat card + Feedback = Live in module status

## DB
- Table `feedbacks` created via `flask create-tables`.

## Verified
- All 6 routes register on the URL map
- `feedbacks` table present in Postgres
- All new/edited Jinja templates compile

## Status
This was the final SRS module — 3.1–3.14 are now all implemented.
