# SRS 3.6 — Attendance Module Changelog

## Requirements Implemented
- FR-ATT-01: Record check-in datetime for a member; check-out optional, recorded separately
- FR-ATT-02: Duration calculated automatically from check_out − check_in
- FR-ATT-03: Admin and Trainer can record/list all attendance; Members view own only (403 guard)
- FR-ATT-04: List with date filter, member name search, pagination (20/page)

---

## [+] NEW FILES CREATED

app/models/attendance.py
  - Attendance model (attendances table)
      member_id FK (required), check_in DateTime, check_out DateTime (nullable), notes
      audit: created_by_id, updated_by_id, created_at, updated_at
  - Properties:
      is_checked_out — bool
      duration_minutes — int or None
      duration_label — "2h 30m" / "45m" / "—"
      check_in_date — date portion of check_in
  - Backref on Member: member.attendances (lazy dynamic, ordered check_in desc)

app/blueprints/attendance/__init__.py
  - attendance_bp Blueprint definition

app/blueprints/attendance/forms.py
  - AttendanceCreateForm: member_id, check_in (DateTimeField %Y-%m-%dT%H:%M), check_out (optional), notes

app/blueprints/attendance/routes.py
  - GET  /attendance/                   list_attendance   — Admin+Trainer; search + date filter + pagination; 4 stats: today/this-week/in-gym/total
  - GET/POST /attendance/create         create_attendance — Admin+Trainer; ?member_id= pre-fill; validates check_out > check_in
  - GET  /attendance/<id>               view_attendance   — Members can only view own (403 otherwise)
  - POST /attendance/<id>/checkout      checkout          — Admin+Trainer; sets check_out = utcnow()
  - GET  /attendance/my-attendance      my_attendance     — Member role only; paginated own history

templates/attendance/list.html
  - 4 stat cards: Today's Check-ins / This Week / Currently In Gym / All-Time Records
  - Filters: member name search + date picker
  - Paginated table: id, member (linked), check-in, check-out, duration, status badge, view button

templates/attendance/create.html
  - Member dropdown with ?member_id= pre-fill
  - check_in datetime-local input; JS sets default to current local time if empty
  - check_out datetime-local input (optional); helper text "Leave blank to mark check-out later"
  - Notes textarea

templates/attendance/view.html
  - Attendance details card: member, check-in, check-out, duration, notes
  - Record info card: recorded by/at, checked out by
  - "Mark Check-Out (Now)" button for Admin+Trainer when not yet checked out

templates/attendance/my_attendance.html
  - Member-facing paginated table: date, check-in time, check-out time, duration, status badge, view button

---

## [~] EXISTING FILES EDITED

app/models/__init__.py
  - Added export: Attendance

app/__init__.py
  - Imported attendance_bp
  - Registered blueprint: url_prefix='/attendance'

templates/base.html
  - Admin sidebar: activated Attendance link (was "Soon"); url_for('attendance.list_attendance')
  - Trainer sidebar: activated Attendance link (was "Soon"); url_for('attendance.list_attendance')
  - Member sidebar: activated Attendance link (was "Soon"); url_for('attendance.my_attendance')

templates/members/view.html
  - Added Attendance History section (between Payment History and Workout Schedule)
      shows last 5 records via member.attendances.limit(5).all()
      columns: date, check-in/out times, duration, status badge, View button
      "View all N records" link to attendance list filtered by member name
      Admin: Record button links to attendance.create_attendance?member_id=

app/blueprints/dashboard/routes.py
  - Imported Attendance
  - Added to admin stats: today_checkins (attendance records where date == today)
  - Member dashboard: queries recent_attendance (last 5 for member) and passes to template

templates/dashboard/admin.html
  - Added stat card: Today's Check-ins (8th card)
  - Mark Attendance quick action added
  - Module Status: Attendance badge changed from "Pending" to "Live"

templates/dashboard/member.html
  - Replaced "More features coming soon" placeholder card with Recent Attendance card
      shows last 5 visits: date, check-in/out times, duration, status badge
      View All link to attendance.my_attendance

CLAUDE.md
  - Added full SRS 3.6 module reference section
  - Updated Registered Blueprints table to include /attendance
  - Updated Next Modules list (removed 3.6, starts at 3.7)