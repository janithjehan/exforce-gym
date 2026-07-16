import click
from app import create_app
from app.extensions import db

app = create_app()


@app.cli.command('create-tables')
def create_tables():
    """Create all database tables."""
    with app.app_context():
        db.create_all()
        click.echo('Database tables created successfully.')


@app.cli.command('create-admin')
@click.option('--username', prompt=True, help='Admin username')
@click.option('--email', prompt=True, help='Admin email')
@click.option('--password', prompt=True, hide_input=True,
              confirmation_prompt=True, help='Admin password')
@click.option('--first-name', prompt=True, help='First name')
@click.option('--last-name', prompt=True, help='Last name')
def create_admin(username, email, password, first_name, last_name):
    """Create the initial admin user."""
    from app.models.user import User, UserRole

    with app.app_context():
        if User.query.filter_by(username=username).first():
            click.echo(f'Error: Username "{username}" already exists.')
            return
        if User.query.filter_by(email=email).first():
            click.echo(f'Error: Email "{email}" already exists.')
            return

        admin = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=UserRole.ADMIN,
            is_active=True,
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f'Admin user "{username}" created successfully.')


@app.cli.command('expire-memberships')
def expire_memberships():
    """Mark passed ACTIVE memberships as EXPIRED."""
    from app.models.membership import Membership
    with app.app_context():
        Membership.expire_passed()
        click.echo('Expired memberships updated.')


@app.cli.command('send-expiry-reminders')
def send_expiry_reminders():
    """FR-NOT-03: notify members whose membership expires within 30 days
    (in-app + SMS when Notify.lk is configured). Run as a scheduled task."""
    from app.blueprints.notifications.service import send_expiry_reminders as run_job
    with app.app_context():
        notified, skipped = run_job()
        click.echo(f'Expiry reminders: {notified} notified, {skipped} already reminded recently.')


@app.cli.command('drop-tables')
@click.confirmation_option(prompt='Are you sure you want to drop all tables?')
def drop_tables():
    """Drop all database tables."""
    with app.app_context():
        db.drop_all()
        click.echo('All tables dropped.')


if __name__ == '__main__':
    app.run(debug=True)
