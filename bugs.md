# Exforce GMS — Bug Report

**Audit date:** 2026-07-24
**Branch:** `branch_jg_07232026`
**Scope:** Full codebase (all blueprints, models, services, templates, CLI).
**Method:** Static read-through of every route/form/model plus targeted reproduction of the higher-risk findings. Each item below was confirmed against the actual source — false positives from the first pass were discarded (e.g. an initial claim that `TrainerEditForm` made NIC optional was wrong; NIC *is* required — only the mobile number is not).

> No code was changed as part of this audit. Every "Suggested fix" is a description only.

---

## Severity summary

| # | Severity | Area | One-line |
|---|----------|------|----------|
| 1 | High | Users / Auth | `edit_user` can deactivate self or the last active admin (no guard) — full admin lockout |
| 2 | High | Users / Auth | `edit_user` last-admin role guard counts non-archived, not active admins |
| 3 | High | Members | `view_member` lets a Trainer view any member's full profile (IDOR / PII exposure) |
| 4 | High | Payments | `/payments/create` can never link a payment to a membership (form validation always fails) |
| 5 | High | Dashboards / Reports | Revenue & net-profit count PENDING/REJECTED bank transfers as income |
| 6 | High | Notifications | Payment-rejection notice reuses `is_auto=True`, suppressing real expiry reminders |
| 7 | Medium | Payments / Memberships | Self-service purchase doesn't block overlap with an existing active membership (server-side) |
| 8 | Medium | Memberships | Renewing a long-expired membership creates an already-expired renewal |
| 9 | Medium | Memberships / Payments | Manual create + bank-transfer verify can produce two concurrent ACTIVE memberships |
| 10 | Medium | Payments | Editing a PENDING bank transfer's method strands it (unresolvable) |
| 11 | Medium | Search (multiple lists) | Full-name (space-separated) search returns zero results everywhere |
| 12 | Medium | Trainers | `TrainerEditForm` lets the mobile number be cleared (contradicts required-mobile rule) |
| 13 | Medium | Trainers (UI) | Manager can't edit/archive/restore/add trainers in the UI though authorized server-side |
| 14 | Medium | Schedules | PDF export 500s when any free-text field contains markup characters |
| 15 | Medium | Payments (PayHere) | `/notify` idempotency is a race (no unique constraint on `reference_no`) |
| 16 | Low | Auth | `RegisterForm` email uniqueness check is case-sensitive but storage is lowercased → 500 |
| 17 | Low | Auth | Inactive-account failed-login attempt is never committed to the audit log |
| 18 | Low | Users | NIC stored via `.strip().upper()` (keeps internal spaces) instead of `clean_nic()` |
| 19 | Low | Attendance | Future check-in is allowed → negative duration on checkout |
| 20 | Low | Payments (PayHere) | Notify stores amount via `float()` instead of `Decimal` |
| 21 | Low | Payroll | Deductions aren't capped → negative net pay possible |
| 22 | Low | Configuration | `AppConfiguration.get()` can create duplicate singleton rows under concurrency |
| 23 | Low | Schedules | PDF only merges *adjacent* same-day rows (duplicate day sections) |
| 24 | Low | CLI | `send-expiry-reminders` docstring falsely claims SMS delivery |

Items **4, 5, 6, 9, 10** are regressions/omissions introduced or exposed by the recent Bank-Transfer / Configuration / Notifications work.

---

## High severity

### 1. `edit_user` bypasses the self-deactivation and last-active-admin guards
- **Location:** `app/blueprints/users/routes.py:158` (`user.is_active = form.is_active.data`), form field in `templates/users/edit.html`.
- **Problem:** The dedicated `deactivate_user` route (`routes.py:215-232`) enforces "cannot deactivate self" and "cannot deactivate the last active admin". The general `edit_user` form sets `is_active` straight from the checkbox with **no such checks**. CLAUDE.md documents both guards as invariants — they only hold on the dedicated action routes.
- **Repro:** The sole active admin opens `/users/<own_id>/edit`, unchecks *Active*, saves. On the next request `load_user` returns `None` (inactive), logging them out; `login()` also refuses inactive accounts → nobody can log in as admin again.
- **Impact:** Total, self-inflicted admin lockout of the whole system.
- **Suggested fix:** Apply the same self-guard + active-admin-count guard in `edit_user` when `is_active` is being set to `False`; ideally centralize the check in one helper shared by `edit_user`/`deactivate_user`/`archive_user`.

### 2. Last-admin role-change guard counts the wrong population
- **Location:** `app/blueprints/users/routes.py:143-146`.
- **Problem:** The guard blocking demotion of the last admin counts `role=ADMIN, is_archived=False` — i.e. *non-archived* admins, including deactivated ones. The analogous guard in `deactivate_user` (`routes.py:226-229`) correctly counts `is_active=True, is_archived=False`. `edit_user` also has no block on an admin changing **their own** role.
- **Repro:** Admin A (active) + Admin B (role ADMIN, `is_active=False`, not archived) exist. A edits their own role to MANAGER: the guard sees count 2 and allows it. Now the only ADMIN-role account is the inactive B → zero usable admins.
- **Impact:** Same lockout class as #1, via role change.
- **Suggested fix:** Filter on `is_active == True, is_archived == False` (matching `deactivate_user`) and block self-demotion when the actor is the last active admin.

### 3. `view_member` — any Trainer can view any member's full profile (IDOR)
- **Location:** `app/blueprints/members/routes.py:108-119`.
- **Problem:** Only `UserRole.MEMBER` is restricted to "own profile". Every sibling route (`list/create/edit/archive/restore`) is `@admin_or_manager_required`, but `view_member` is only `@login_required` with a member-only ownership check, so a **Trainer** (authenticated, not a member) falls through and can open any `/members/<id>`. CLAUDE.md documents the module as "Admin+Manager / Member-own" — Trainer is not authorized.
- **Repro:** Log in as a trainer, visit `/members/1`, `/members/2`, … → full profile: contact no, address, DOB/gender, emergency contact, membership + last-5 payments (amounts) + attendance history. Member IDs are readily visible to trainers via Schedules.
- **Impact:** Unauthorized PII + financial disclosure to a lower-privilege role; trivial enumeration by incrementing the id.
- **Suggested fix:** `if current_user.role not in (ADMIN, MANAGER) and not owns_this_profile: abort(403)`.

### 4. `/payments/create` can never link a payment to a membership
- **Location:** `app/blueprints/payments/routes.py:116, 128-130`.
- **Problem:** `form.membership_id.choices` is reset to just `[(0, '— None / General Payment —')]` on every request. The real membership list is only loaded via `_populate_memberships()` **after** `form.validate_on_submit()`. WTForms `SelectField.pre_validate` runs *inside* `validate_on_submit()` against the current choices — which only contain `0` — so any real membership id submitted fails with "Not a valid choice". (Reproduced directly against the live `PaymentCreateForm`.)
- **Repro:** Record Payment → pick a member → the AJAX-populated membership dropdown lists real memberships → select one → submit → validation fails silently; only "None / General Payment" ever saves.
- **Impact:** The documented ability (SRS 3.5) to link a payment to a specific membership is completely broken from the manual entry form.
- **Suggested fix:** Populate `form.membership_id.choices` from `request.form.get('member_id', type=int)` **before** `validate_on_submit()`.

### 5. Dashboards and Profit Report count unverified/rejected payments as revenue
- **Location:** `app/blueprints/dashboard/routes.py:55-62` (admin) and `132-139` (manager); `app/blueprints/reports/routes.py:41-53`.
- **Problem:** These `SUM(Payment.amount)` queries filter only by date — no `Payment.status == PaymentStatus.VERIFIED`. The payments list route was updated to require VERIFIED (`payments/routes.py:69-71, 79-82`) but the dashboards and Profit Report were not (reports doesn't even import `PaymentStatus`). A member-submitted bank transfer starts PENDING and, if rejected, is only status-flipped (never deleted).
- **Repro:** A member submits a bank transfer (or one is later rejected). "Revenue This Month" / "Net Profit This Month" on both dashboards and "Total Income"/"Net Profit" on the Profit Report include that amount — before verification and even after rejection.
- **Impact:** Overstated revenue/profit in the primary management views; fake/pending transfers permanently inflate reports.
- **Suggested fix:** Add `Payment.status == PaymentStatus.VERIFIED` to the revenue sums/counts in both dashboard routes and both report queries.

### 6. Payment-rejection notice reuses `is_auto=True`, poisoning expiry-reminder dedup
- **Location:** `app/blueprints/payments/routes.py:664-665` (`_notify_member_of_rejection`) vs `app/blueprints/notifications/service.py` `send_expiry_reminders()` dedup query.
- **Problem:** `is_auto` is documented as "automated expiry reminder", and `send_expiry_reminders()` builds its 30-day "already reminded" suppression set from *any* `NotificationLog` whose `Notification.is_auto == True`. The bank-transfer rejection notice also sets `is_auto=True`, so it lands in that set.
- **Repro:** A member's transfer is rejected today; within 30 days their membership becomes expiring-soon. The next reminder run finds their `recipient_id` in `already_reminded` (recent + `is_auto`) and skips them → they never get the expiry reminder. Also inflates the "Auto Expiry Reminders" stat on `/notifications`.
- **Impact:** Members silently starved of renewal reminders; corrupted reminder stat.
- **Suggested fix:** Add `Notification.audience == EXPIRING_SOON` to the dedup query (and stat), or use a dedicated marker for expiry reminders instead of the generic `is_auto`.

---

## Medium severity

### 7. Self-service purchase doesn't enforce no-overlap with an active membership (server-side)
- **Location:** `app/blueprints/payments/routes.py` — `payhere_checkout` and `bank_transfer` / `_validate_package_and_date`; `min_date` is computed only in `buy()` for the HTML `min=` attribute.
- **Problem:** CLAUDE.md's "Buy Rules" say a new plan must start at `current end_date + 1 day` when an active membership exists. That rule exists only as a client-side date-input `min`. Neither checkout path re-validates it server-side (they only check `start_date >= today` and the PENDING-duplicate guard).
- **Repro:** A member with an active plan browses to `/payments/checkout?package_id=1&start_date=<today>` (or edits the date field) and pays → a second overlapping ACTIVE membership is created via `/notify` or bank transfer.
- **Impact:** Overlapping/duplicate active memberships; member effectively loses paid time or double-pays.
- **Suggested fix:** In `_validate_package_and_date` (and `payhere_checkout` before hashing) re-check `start_date >= active_membership.end_date + 1 day`.

### 8. Renewing a long-expired membership creates an already-expired renewal
- **Location:** `app/blueprints/memberships/routes.py:189` (`new_start = membership.end_date + timedelta(days=1)`), template button in `templates/memberships/view.html`.
- **Problem:** `renew_membership` blocks only CANCELLED and PENDING; EXPIRED is renewable, and `new_start` is always `end_date + 1 day` with no clamp to today.
- **Repro:** A 1-month membership that ended 2026-01-15, renewed on 2026-07-24 → `new_start=2026-01-16`, `new_end=2026-02-15`, both in the past. Created ACTIVE, then the next `expire_passed()` (runs at the top of `list_memberships`) flips it to EXPIRED — a renewal that's dead on arrival despite payment.
- **Suggested fix:** `new_start = max(date.today(), membership.end_date + timedelta(days=1))`, or force a fresh create once the gap is large.

### 9. Manual create + bank-transfer verify can produce two concurrent ACTIVE memberships
- **Location:** `app/blueprints/memberships/routes.py:117-121` (dup-active check ignores PENDING); `app/blueprints/payments/routes.py` `verify_payment` (activates unconditionally).
- **Problem:** `create_membership`'s FR-MSHIP-02 guard only checks for an existing `ACTIVE` membership, not a `PENDING` one; `verify_payment` flips its linked PENDING membership to ACTIVE without checking for an already-active one.
- **Repro:** Member submits a bank transfer (PENDING membership) → before staff verify, an admin records a payment via `/memberships/create` (passes, nothing ACTIVE yet) → staff verify the transfer → member now has two ACTIVE memberships.
- **Suggested fix:** Have `create_membership` also block on an existing PENDING membership; have `verify_payment` check for a pre-existing active membership and warn/merge instead of blindly activating.

### 10. Editing a PENDING bank transfer's method strands it
- **Location:** `app/blueprints/payments/routes.py:188-232` (`edit_payment` — no status/method guard) vs `verify_payment`/`reject_payment` (require `method == BANK_TRANSFER and status == PENDING`).
- **Problem:** `edit_payment` never checks status, and `PaymentEditForm` lets `method` change to any value. Changing a still-PENDING bank transfer's method to e.g. CASH leaves it `status == PENDING` but no longer `BANK_TRANSFER`, so verify/reject both refuse it. `renew_membership`/`cancel_membership` also refuse a PENDING membership and defer to verify/reject — now unreachable.
- **Impact:** The payment and its membership are stuck PENDING with no in-app resolution path.
- **Suggested fix:** Block `edit_payment` (or at least the `method` field / the whole record) while `status == PENDING`.

### 11. Full-name search returns zero results across every list view
- **Location:** `app/utils/search.py:4-22`; consumed by members, payments, memberships, attendance, trainers, schedules, feedback list routes.
- **Problem:** `parse_search_terms` splits only on commas; `multi_term_filter` ORs each whole term against `first_name` and `last_name` separately. A natural `"John Smith"` becomes one term and matches neither column (each holds only one name part).
- **Repro:** On `/attendance/`, `/trainers/`, `/members/`, etc., search `John Smith` → 0 results though the person exists. (The "(comma-separated)" placeholder hints at the workaround but the common input silently fails.)
- **Suggested fix:** Split each comma-term further on whitespace and AND the sub-tokens across name columns, or match against a concatenated `first || ' ' || last`.

### 12. `TrainerEditForm` lets the mobile number be cleared
- **Location:** `app/blueprints/trainers/forms.py:75` (`phone` Optional) and `:99-103` (`contact_no` Optional).
- **Problem:** CLAUDE.md states mobile + NIC are required on trainer create/edit. NIC **is** correctly `DataRequired` here (line 78), but both phone fields are `Optional`, so an edit can null out the mobile number — contradicting the invariant and diverging from `MemberEditForm` (which requires it).
- **Repro:** Admin/Manager edits a trainer, clears Phone + Contact No, saves → no error; `user.phone=None`, `trainer.contact_no=''`.
- **Suggested fix:** Make `phone`/`contact_no` `DataRequired` in `TrainerEditForm`.

### 13. Manager can't manage trainers in the UI though authorized server-side
- **Location:** `templates/trainers/view.html:19` (Edit/Archive/Restore block gated `role == 'admin'`); `templates/trainers/list.html` (Add Trainer button shown unconditionally).
- **Problem:** Backend matches the documented matrix (`edit/archive/restore_trainer` = `admin_or_manager_required`; `create` = `admin_required`), but the view template hides all trainer actions from Manager, and the list shows "Add Trainer" to Manager (who then hits a 403). So Manager has no working in-app path to edit/archive/restore, and a misleading one for create.
- **Suggested fix:** Extend the action block condition to `role in ('admin','manager')`; hide "Add Trainer" from non-admins.

### 14. Schedule PDF export 500s on markup characters in free text
- **Location:** `app/blueprints/schedules/pdf.py:74, 78, 83, 100`.
- **Problem:** `day_label`, workout `name`, item `notes`, and `schedule.notes` are passed unescaped into reportlab `Paragraph`, which parses a mini-markup subset. Unbalanced/`<`-containing text (e.g. a note like `warm up < 5 min` or `<b>`) raises `ValueError` (reproduced).
- **Repro:** Create a schedule with an item note containing `<` or `<b>`, open `/schedules/<id>/pdf` → 500 for every viewer (member/trainer/admin) until the text is edited.
- **Suggested fix:** `xml.sax.saxutils.escape()` each field before wrapping in `Paragraph`.

### 15. PayHere `/notify` idempotency is a race
- **Location:** `app/blueprints/payments/routes.py` `payhere_notify`; `app/models/payment.py:72` (`reference_no`, no unique constraint).
- **Problem:** Idempotency is a read-then-write (`Payment.query.filter_by(reference_no=order_id).first()`) with no unique index or lock. `send_payment_confirmation` (a synchronous SMS network call) runs before the `200 OK`, lengthening the window and making PayHere retries more likely; two concurrent deliveries can both pass the check and both insert.
- **Impact:** Duplicate ACTIVE membership + payment for one transaction.
- **Suggested fix:** Add a unique index on `reference_no` and catch `IntegrityError` to no-op the duplicate (and/or return `200` before sending SMS).

---

## Low severity

### 16. Register email uniqueness check is case-sensitive; storage is lowercased
- **Location:** `app/blueprints/auth/forms.py:79` vs `app/blueprints/auth/routes.py:79`.
- **Problem:** `validate_email` checks raw `field.data`; the row is stored `.lower()`. A case-variant of an existing email passes validation then hits the unique constraint → uncaught `IntegrityError`/500 (no rollback/IntegrityError handler).
- **Suggested fix:** Compare `field.data.strip().lower()` in the validator (as `users`/`members` forms already do).

### 17. Inactive-account failed login isn't committed to the audit log
- **Location:** `app/blueprints/auth/routes.py:33-36`.
- **Problem:** The "correct password but inactive account" branch calls `_log_failed(user)` then returns without `db.session.commit()`; the wrong-password branch (`:51-53`) commits. The log row is discarded at teardown. (The archived branch above logs nothing at all.)
- **Suggested fix:** Commit after `_log_failed` in the inactive branch.

### 18. `users` route stores NIC with `.strip().upper()` instead of `clean_nic()`
- **Location:** `app/blueprints/users/routes.py:76` and `:156` (vs `clean_nic()` used everywhere else, and used for the derived password at `:81`).
- **Problem:** `.strip().upper()` keeps internal whitespace, so a NIC typed with an embedded space is stored un-normalized (violating the "stored normalized" invariant) and can defeat the cleaned-value `nic_taken()` duplicate check. The create path even derives the initial password from `clean_nic()` while storing the un-cleaned NIC — the two can differ.
- **Suggested fix:** Use `clean_nic(form.nic_no.data)` in both spots.

### 19. Attendance allows a future check-in → negative duration
- **Location:** `app/blueprints/attendance/routes.py:90-94, 138`; `app/models/attendance.py` `duration_minutes`/`duration_label`.
- **Problem:** Creation validates `check_out > check_in` only when both are given; `check_in` itself isn't bounded to "not future". A later `/checkout` sets `check_out = utcnow()`, which can precede a future `check_in`, yielding a negative `duration_minutes` and a garbled label (`-1h 30m`).
- **Suggested fix:** Reject future `check_in`; have `checkout` verify `utcnow() > check_in`.

### 20. PayHere notify stores amount as `float()` not `Decimal`
- **Location:** `app/blueprints/payments/routes.py` (`amount=float(payhere_amount)` in `payhere_notify`).
- **Problem:** A string amount is converted with `float()` before assignment to a `Numeric(10,2)` column. Postgres rounds on insert so no wrong value was demonstrated, but it's an avoidable float-precision risk.
- **Suggested fix:** `Decimal(payhere_amount)`.

### 21. Payroll deductions aren't capped → negative net pay
- **Location:** `app/blueprints/payroll/forms.py` (deductions `NumberRange(min=0)` only); `app/models/payroll.py` `net_amount`.
- **Problem:** No upper bound relative to `gross + bonus`; a typo produces a negative `net_amount` that passes create/edit/mark-paid unwarned.
- **Suggested fix:** Cross-field validator `deductions <= gross_amount + bonus` (or a warning).

### 22. `AppConfiguration.get()` can create duplicate singleton rows
- **Location:** `app/models/configuration.py:20-28`.
- **Problem:** Get-or-create with `query.first()` + insert, no unique/lock. Two concurrent first accesses (e.g. the config page and a bank-transfer buy) before the row exists can both insert. Afterward `.first()` may return a different row than an edit updated → admin's bank-detail edits could stop showing to members.
- **Suggested fix:** Pin to a fixed PK (`id=1`) or add a unique constraint + upsert/retry-on-IntegrityError.

### 23. Schedule PDF only merges adjacent same-day rows
- **Location:** `app/blueprints/schedules/pdf.py:67-71`.
- **Problem:** Grouping only merges consecutive items with the same `day_label`; non-contiguous rows (Mon, Tue, Mon) render two separate "Monday" sections. Cosmetic.
- **Suggested fix:** Group into an ordered dict keyed by `day_label`.

### 24. `send-expiry-reminders` CLI docstring falsely claims SMS
- **Location:** `run.py:60-61`.
- **Problem:** Docstring says "in-app + SMS when Notify.lk is configured", but the service sends in-app only (SMS is reserved for payment confirmations per the design note). Misleading to operators.
- **Suggested fix:** Update the docstring to "in-app only".

---

## Areas checked and found sound
- `user_loader` returns `None` for inactive/archived accounts; login blocks archived/inactive.
- Sliding 2-hour session timeout works as designed.
- Password-reset tokens self-invalidate on password change and respect expiry; forgot-password avoids account enumeration.
- NIC format/day-of-year parsing (incl. female +500 offset, Feb-29 edge case) is correct; `nic_taken()` is case-insensitive.
- Dedicated `deactivate_user`/`archive_user` guards (self + last active admin) are correct.
- Measurements access ("Admin + owning member only") is correctly enforced against Manager/Trainer.
- Feedback active-membership submit gate (FR-FDB-04), rating range, and filtered CSV export are correct.
- Schedule versioning / edit-log / "no changes detected" logic is correct; measurement and payment/payroll edit-logs capture every form field.
- Payroll self-guards (create/edit/mark-paid/cancel + bulk-create structural exclusion) are correct.
- `Membership.calculate_end_date` inclusive math is correct.
- The Notifications Member→User refactor itself is clean (no dangling `member_id`/`.member`, no cross-user info leak in `my_notifications`, staff-audience resolution correct).
