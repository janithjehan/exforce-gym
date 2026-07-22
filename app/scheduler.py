from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()


def init_scheduler(app):
    """Runs FR-MSHIP daily expiry + FR-NOT-03 expiry reminders in-process,
    replacing the flask expire-memberships / send-expiry-reminders CLI commands
    as the way these jobs actually get triggered on a schedule."""

    def run_daily_expiry_job():
        with app.app_context():
            from app.models.membership import Membership
            from app.blueprints.notifications.service import send_expiry_reminders

            Membership.expire_passed()
            notified, skipped = send_expiry_reminders()
            app.logger.info(
                f'[scheduler] expiry job: {notified} notified, {skipped} skipped'
            )

    scheduler.configure(timezone=app.config['TIMEZONE'])
    scheduler.add_job(
        run_daily_expiry_job, 'cron', hour=0, minute=30,
        id='daily_expiry_job', replace_existing=True,
    )
    scheduler.start()
