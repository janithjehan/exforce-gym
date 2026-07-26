from datetime import datetime, date
from calendar import monthrange
from flask import render_template, redirect, url_for, flash, request
from flask_login import current_user

from app.blueprints.expenses import expenses_bp
from app.blueprints.expenses.forms import ExpenseForm
from app.extensions import db
from app.models.expense import Expense, ExpenseCategory
from app.utils.decorators import admin_required
from app.utils.search import parse_search_terms, multi_term_filter

EXPENSES_PER_PAGE = 15


@expenses_bp.route('/')
@admin_required
def list_expenses():
    """List non-archived expenses with search, category/month filter, and pagination."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    category_filter = request.args.get('category', '')
    month_filter = request.args.get('month', '')  # YYYY-MM

    query = Expense.query.filter_by(is_archived=False)

    terms = parse_search_terms(search)
    if terms:
        query = query.filter(multi_term_filter(terms, [Expense.description]))

    if category_filter:
        try:
            query = query.filter(Expense.category == ExpenseCategory(category_filter))
        except ValueError:
            pass

    if month_filter:
        try:
            year, month = map(int, month_filter.split('-'))
            last_day = monthrange(year, month)[1]
            query = query.filter(
                Expense.expense_date >= date(year, month, 1),
                Expense.expense_date <= date(year, month, last_day),
            )
        except (ValueError, AttributeError):
            pass

    expenses = query.order_by(Expense.expense_date.desc(), Expense.id.desc()).paginate(
        page=page, per_page=EXPENSES_PER_PAGE, error_out=False
    )

    today = date.today()
    month_start = date(today.year, today.month, 1)
    stats = {
        'total_this_month': db.session.query(db.func.sum(Expense.amount)).filter(
            Expense.is_archived == False,
            Expense.expense_date >= month_start,
        ).scalar() or 0,
        'total_all_time': db.session.query(db.func.sum(Expense.amount)).filter(
            Expense.is_archived == False,
        ).scalar() or 0,
        'count': Expense.query.filter_by(is_archived=False).count(),
    }

    return render_template(
        'expenses/list.html',
        expenses=expenses,
        search=search,
        category_filter=category_filter,
        month_filter=month_filter,
        categories=ExpenseCategory,
        stats=stats,
        title='Expenses',
    )


@expenses_bp.route('/create', methods=['GET', 'POST'])
@admin_required
def create_expense():
    """Log a new business expense."""
    form = ExpenseForm()
    if request.method == 'GET' and not form.expense_date.data:
        form.expense_date.data = date.today()

    if form.validate_on_submit():
        expense = Expense(
            category=ExpenseCategory(form.category.data),
            amount=form.amount.data,
            expense_date=form.expense_date.data,
            description=form.description.data.strip() or None,
            created_by_id=current_user.id,
        )
        db.session.add(expense)
        db.session.commit()
        flash('Expense recorded successfully.', 'success')
        return redirect(url_for('expenses.view_expense', expense_id=expense.id))

    return render_template('expenses/create.html', form=form, title='Log Expense')


@expenses_bp.route('/<int:expense_id>')
@admin_required
def view_expense(expense_id):
    """Show a single expense's details."""
    expense = Expense.query.get_or_404(expense_id)
    return render_template('expenses/view.html', expense=expense, title=f'Expense #{expense.id}')


@expenses_bp.route('/<int:expense_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_expense(expense_id):
    """Edit an existing expense's fields; blocked if archived."""
    expense = Expense.query.get_or_404(expense_id)

    if expense.is_archived:
        flash('Archived expenses cannot be edited.', 'warning')
        return redirect(url_for('expenses.view_expense', expense_id=expense_id))

    form = ExpenseForm()

    if request.method == 'GET':
        form.category.data = expense.category.value
        form.amount.data = expense.amount
        form.expense_date.data = expense.expense_date
        form.description.data = expense.description

    if form.validate_on_submit():
        expense.category = ExpenseCategory(form.category.data)
        expense.amount = form.amount.data
        expense.expense_date = form.expense_date.data
        expense.description = form.description.data.strip() or None
        expense.updated_by_id = current_user.id
        expense.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Expense updated successfully.', 'success')
        return redirect(url_for('expenses.view_expense', expense_id=expense_id))

    return render_template('expenses/edit.html', form=form, expense=expense, title='Edit Expense')


@expenses_bp.route('/<int:expense_id>/archive', methods=['POST'])
@admin_required
def archive_expense(expense_id):
    """Soft-delete an expense record."""
    expense = Expense.query.get_or_404(expense_id)
    expense.is_archived = True
    expense.updated_by_id = current_user.id
    expense.updated_at = datetime.utcnow()
    db.session.commit()
    flash('Expense has been archived.', 'secondary')
    return redirect(url_for('expenses.list_expenses'))


@expenses_bp.route('/<int:expense_id>/restore', methods=['POST'])
@admin_required
def restore_expense(expense_id):
    """Un-archive an expense record."""
    expense = Expense.query.get_or_404(expense_id)
    expense.is_archived = False
    expense.updated_by_id = current_user.id
    expense.updated_at = datetime.utcnow()
    db.session.commit()
    flash('Expense has been restored.', 'success')
    return redirect(url_for('expenses.list_expenses'))
