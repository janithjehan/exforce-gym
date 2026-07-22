"""Outbound email via SMTP (smtplib) — currently used for password reset links.

Mirrors app/utils/notifylk.py's pattern: a thin client with graceful
degradation when unconfigured. When MAIL_ENABLED is off (the dev default),
send_email() logs the message instead of sending it, so the reset flow is
fully testable without real SMTP credentials.
"""
import smtplib
import logging
from email.message import EmailMessage
from flask import current_app

logger = logging.getLogger(__name__)


def is_mail_configured():
    cfg = current_app.config
    return bool(
        cfg.get('MAIL_ENABLED')
        and cfg.get('MAIL_SERVER')
        and cfg.get('MAIL_USERNAME')
        and cfg.get('MAIL_PASSWORD')
    )


def send_email(to, subject, body):
    """Send one plain-text email. Returns (ok: bool, error: str | None).

    When mail isn't configured, logs the message to the console/log instead
    of failing — lets the reset-password flow be exercised in dev without
    a real mail server.
    """
    if not is_mail_configured():
        logger.info(
            "MAIL_ENABLED is off or incomplete — logging email instead of sending.\n"
            "To: %s\nSubject: %s\n%s", to, subject, body,
        )
        print(f"\n--- [DEV] Email not sent (MAIL_ENABLED=False) ---\nTo: {to}\nSubject: {subject}\n\n{body}\n---\n")
        return True, None

    cfg = current_app.config
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = cfg['MAIL_DEFAULT_SENDER']
    msg['To'] = to
    msg.set_content(body)

    try:
        with smtplib.SMTP(cfg['MAIL_SERVER'], cfg['MAIL_PORT'], timeout=15) as server:
            if cfg.get('MAIL_USE_TLS'):
                server.starttls()
            server.login(cfg['MAIL_USERNAME'], cfg['MAIL_PASSWORD'])
            server.send_message(msg)
        return True, None
    except (smtplib.SMTPException, OSError) as exc:
        return False, str(exc)
