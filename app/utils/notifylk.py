"""Notify.lk SMS gateway client (https://notify.lk).

FR-NOT-04: SMS is an optional channel — everything degrades gracefully when
NOTIFYLK_ENABLED is off or credentials are missing.
"""
import re
import requests
from flask import current_app

NOTIFYLK_API_URL = 'https://app.notify.lk/api/v1/send'


def is_sms_configured():
    cfg = current_app.config
    return bool(
        cfg.get('NOTIFYLK_ENABLED')
        and cfg.get('NOTIFYLK_USER_ID')
        and cfg.get('NOTIFYLK_API_KEY')
    )


def normalize_phone(phone):
    """Convert a Sri Lankan number to Notify.lk's 94XXXXXXXXX format.
    Accepts 0771234567, +94771234567, 94771234567, 771234567.
    Returns None if the number can't be normalized."""
    digits = re.sub(r'\D', '', phone or '')
    if len(digits) == 10 and digits.startswith('0'):
        return '94' + digits[1:]
    if len(digits) == 11 and digits.startswith('94'):
        return digits
    if len(digits) == 9:
        return '94' + digits
    return None


def send_sms(to, message):
    """Send one SMS via Notify.lk. Returns (ok: bool, error: str | None)."""
    if not is_sms_configured():
        return False, 'SMS gateway not configured'

    number = normalize_phone(to)
    if not number:
        return False, f'Invalid phone number: {to or "(empty)"}'

    cfg = current_app.config
    try:
        resp = requests.post(
            NOTIFYLK_API_URL,
            data={
                'user_id': cfg['NOTIFYLK_USER_ID'],
                'api_key': cfg['NOTIFYLK_API_KEY'],
                'sender_id': cfg.get('NOTIFYLK_SENDER_ID') or 'NotifyDEMO',
                'to': number,
                'message': message,
            },
            timeout=15,
        )
        data = resp.json()
        if resp.ok and data.get('status') == 'success':
            return True, None
        return False, str(data.get('error') or data.get('message') or data)
    except (requests.RequestException, ValueError) as exc:
        return False, str(exc)