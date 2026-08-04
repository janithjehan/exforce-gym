# SRS 3.5 — Payments Module Changelog

## Requirements Implemented
- FR-PAY-01: Payment linked to Member (required FK) and Membership (optional FK)
- FR-PAY-02: PaymentMethod enum: CASH / CARD / BANK_TRANSFER / ONLINE
- FR-PAY-03: Editing restricted to Admin; every changed field logged to PaymentEditLog (who/when/old→new)

---

## [+] NEW FILES CREATED

app/models/payment.py
  - PaymentMethod enum: CASH / CARD / BANK_TRANSFER / ONLINE
      each has: .label, .badge_class, .icon
  - Payment model (payments table)
      member_id FK (required), membership_id FK (optional)
      amount Numeric(10,2), method enum, payment_date, reference_no, notes
      audit: created_by_id, updated_by_id, created_at, updated_at
  - PaymentEditLog model (payment_edit_logs table)
      payment_id, edited_by_id, field_name, old_value, new_value, created_at

app/blueprints/payments/__init__.py
  - payments_bp Blueprint definition

app/blueprints/payments/forms.py
  - PaymentCreateForm: member_id, membership_id (optional), amount, method, payment_date, reference_no, notes
  - PaymentEditForm: amount, method, payment_date, reference_no, notes

app/blueprints/payments/routes.py
  - GET  /payments/                             list_payments          — search + method filter + month filter + pagination; stats: total/revenue/this-month
  - GET/POST /payments/create                   create_payment         — ?member_id= and ?membership_id= pre-fill
  - GET  /payments/<id>                         view_payment           — payment details + edit audit log
  - GET/POST /payments/<id>/edit                edit_payment           — FR-PAY-03: diff-detects changes, writes PaymentEditLog per field
  - GET  /payments/memberships-for-member/<id>  memberships_for_member — AJAX JSON endpoint for dynamic membership dropdown

templates/payments/list.html
  - 4 stat cards: Total Payments / Total Revenue / This Month count / This Month Revenue
  - Filters: search (member name / ref no) + method dropdown + month picker
  - Paginated table: id, member, amount, method badge, date, membership link, ref, view button

templates/payments/create.html
  - Member dropdown → triggers AJAX to reload membership dropdown
  - Amount + method + payment_date + reference_no + notes
  - JS: memberSelect change event fetches /payments/memberships-for-member/<id>

templates/payments/view.html
  - Payment details card: member, amount, method badge+icon, date, reference, linked membership
  - Record info card: recorded by / at, last updated by
  - Edit history card: FR-PAY-03 audit log — field name, old→new values, editor, timestamp

templates/payments/edit.html
  - Warning banner: all changes are logged
  - Edit form: amount, method, payment_date, reference_no, notes

---

## [~] EXISTING FILES EDITED

app/models/__init__.py
  - Added exports: Payment, PaymentMethod, PaymentEditLog

app/__init__.py
  - Imported payments_bp
  - Registered blueprint: url_prefix='/payments'

templates/base.html
  - Activated Payments nav link in admin sidebar (was "Soon" placeholder)
  - Replaced disabled <a href="#"> with url_for('payments.list_payments')

templates/members/view.html
  - Membership section: replaced "Soon" placeholder with real membership list
      shows package name, date range, days remaining, status badge
      Assign Package button links to memberships.create_membership?member_id=
  - Payment History section: replaced empty placeholder with last 5 payments
      shows amount, method badge, date, reference; "View all N payments" link
      Record Payment button links to payments.create_payment?member_id=

app/blueprints/dashboard/routes.py
  - Imported Payment model
  - Added to admin stats: payments_this_month, revenue_this_month

templates/dashboard/admin.html
  - Added stat card: Revenue This Month (LKR)
  - Record Payment quick action: activated (was disabled "Soon")
  - Module Status: Payments badge changed from "Pending" to "Live"

CLAUDE.md
  - Added full SRS 3.5 module reference section
  - Updated Registered Blueprints table to include /payments
  - Updated Next Modules list (removed 3.5, starts at 3.6)
