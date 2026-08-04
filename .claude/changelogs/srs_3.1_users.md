# SRS 3.1 — Users Module Changelog

## Requirements Implemented
- FR-USR-01: RBAC enforced on every route via decorators
- FR-USR-02: bcrypt password hashing via Flask-Bcrypt
- FR-USR-03: 2hr session timeout — PERMANENT_SESSION_LIFETIME + before_request check
- FR-USR-04: Admin can activate / deactivate user accounts

---

## [+] NEW FILES CREATED

app/models/user.py
  - UserRole enum: ADMIN / TRAINER / MEMBER  (each with .label, .value)
  - User model (users table)
      username (unique), email (unique), password_hash, first_name, last_name, phone
      role enum, is_active, is_archived, last_login
      audit: created_by_id, updated_by_id, created_at, updated_at
  - set_password(password) — bcrypt hash
  - check_password(password) — bcrypt verify
  - full_name property
  - LoginActivityLog model (login_activity_logs table)
      user_id FK, action (LOGIN/LOGOUT/FAILED_LOGIN/PASSWORD_CHANGED/
                          ACCOUNT_ACTIVATED/ACCOUNT_DEACTIVATED), details, ip_address, created_at

app/models/__init__.py
  - Initial exports: User, UserRole, LoginActivityLog

app/extensions.py
  - db — Flask-SQLAlchemy instance
  - login_manager — Flask-Login; user_loader blocks inactive/archived users (returns None)
  - bcrypt — Flask-Bcrypt instance
  - csrf — Flask-WTF CSRFProtect instance

app/utils/__init__.py
  - Empty package init

app/utils/decorators.py
  - @admin_required — Admin only; redirects with flash on deny
  - @trainer_required — Trainer only
  - @admin_or_trainer_required — Admin or Trainer
  - @roles_required(*roles) — flexible multi-role check
  - log_activity(action, details) — writes LoginActivityLog row

app/blueprints/auth/__init__.py
  - auth_bp Blueprint definition

app/blueprints/auth/forms.py
  - LoginForm: username_or_email, password, remember_me
  - ChangePasswordForm: current_password, new_password, confirm_password

app/blueprints/auth/routes.py
  - GET/POST /auth/login           login()           — accepts username or email; updates last_login; logs LOGIN/FAILED_LOGIN
  - GET      /auth/logout          logout()          — clears session; logs LOGOUT
  - GET/POST /auth/register        register()        — public; creates MEMBER role User + auto Member profile; logs LOGIN
  - GET/POST /auth/change-password change_password() — requires current password; logs PASSWORD_CHANGED

app/blueprints/users/__init__.py
  - users_bp Blueprint definition

app/blueprints/users/forms.py
  - UserCreateForm: username, email, password, first_name, last_name, phone, role
  - UserEditForm: first_name, last_name, phone, role, is_active
  - ResetPasswordForm: new_password, confirm_password

app/blueprints/users/routes.py
  - GET      /users/               list_users        — search (name/email/username) + role/status filter + pagination (15/page)
  - GET/POST /users/create         create_user       — auto-creates Member profile if role==MEMBER
  - GET      /users/<id>           view_user
  - GET/POST /users/<id>/edit      edit_user         — cannot change last admin's role away from ADMIN
  - POST     /users/<id>/activate  activate_user     — logs ACCOUNT_ACTIVATED
  - POST     /users/<id>/deactivate deactivate_user  — guard: cannot deactivate self; cannot remove last admin
  - POST     /users/<id>/archive   archive_user      — soft delete; same guards as deactivate
  - GET/POST /users/<id>/reset-password reset_password — admin sets new password; logs PASSWORD_CHANGED

app/blueprints/dashboard/__init__.py
  - dashboard_bp Blueprint definition

app/blueprints/dashboard/routes.py
  - GET /dashboard/         home()    — redirects to role-specific dashboard
  - GET /dashboard/admin    admin()   — admin stats + recent activity
  - GET /dashboard/trainer  trainer() — trainer placeholder
  - GET /dashboard/member   member()  — member placeholder

app/blueprints/errors/__init__.py
  - register_error_handlers(app) — 403, 404, 500 handlers

templates/auth/login.html
  - Login card: username or email + password + remember me
  - Link to register page

templates/auth/register.html
  - Registration form: username, email, password, confirm, first_name, last_name, phone
  - Link to login page

templates/auth/change_password.html
  - Current password + new password + confirm fields

templates/users/list.html
  - Search bar + role filter + status filter
  - Table: avatar initials, full name, username, email, role badge, status badge, actions

templates/users/create.html
  - Two-panel form: account fields (left) + role/status (right)

templates/users/view.html
  - User detail card: all fields, role badge, status badge
  - Login activity log table (last 10 events)
  - Admin action buttons: Edit, Activate/Deactivate, Archive, Reset Password

templates/users/edit.html
  - Edit form with role guard (cannot demote last admin)

templates/users/reset_password.html
  - Admin reset password form with confirmation

templates/dashboard/admin.html
  - Stat cards: Total Users, Active Users, Admins, Trainers
  - Quick actions: Add User/Staff
  - Module Status list

templates/dashboard/trainer.html
  - Placeholder dashboard for trainer role

templates/dashboard/member.html
  - Placeholder dashboard for member role

templates/errors/403.html
templates/errors/404.html
templates/errors/500.html

templates/base.html
  - Full sidebar layout: dark sidebar #1b2430 + light main content + orange accent #FF6B35
  - Role-gated sidebar sections: admin / trainer / member
  - Top bar with user dropdown (change password + sign out)
  - Flash message container (auto-dismiss after 5s)
  - Mobile sidebar toggle

app/static/css/style.css
  - Dark sidebar theme, stat cards, table cards, page header, badges, avatars
  - Orange accent #FF6B35 throughout
  - Responsive mobile sidebar

config.py
  - DevelopmentConfig, ProductionConfig, DefaultConfig
  - PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
  - DATABASE_URL from environment

run.py
  - Entry point: app.run(debug=True)
  - CLI: flask create-tables  — db.create_all()
  - CLI: flask create-admin   — interactive admin user creation
  - CLI: flask drop-tables    — destructive, requires confirmation

requirements.txt
  - Flask==3.0.3, Flask-SQLAlchemy==3.1.1, Flask-Login==0.6.3
  - Flask-Bcrypt==1.0.1, Flask-WTF==1.2.1, WTForms==3.1.2
  - psycopg2-binary==2.9.9, python-dotenv==1.0.1, email-validator==2.1.1

.env
  - FLASK_APP=run.py, SECRET_KEY, DATABASE_URL, SESSION_TIMEOUT_HOURS=2

app/__init__.py
  - create_app() factory
  - Session timeout enforcement via before_request hook
  - Registers: auth_bp, users_bp, dashboard_bp, errors
  - Root route: / → redirect to dashboard or login

CLAUDE.md
  - Initial implementation reference document

---

## [~] EXISTING FILES EDITED

(None — 3.1 is the foundation module; all files were newly created.)
