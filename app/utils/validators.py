import re
from datetime import date

from wtforms.validators import ValidationError

# Sri Lankan NIC: old format 9 digits + V/X, new format 12 digits
NIC_PATTERN = re.compile(r'^(?:\d{9}[VvXx]|\d{12})$')

# NIC day-of-year always counts February as 29 days (per the NIC convention)
_NIC_MONTH_DAYS = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def clean_nic(value):
    """Normalize a NIC for storage/comparison: whitespace removed, uppercase, None if empty."""
    return re.sub(r'\s+', '', value or '').upper() or None


def _nic_year_days(nic):
    """(birth year, raw day-of-year) from a normalized NIC."""
    if len(nic) == 10:
        return 1900 + int(nic[0:2]), int(nic[2:5])
    return int(nic[0:4]), int(nic[4:7])


def validate_nic_format(form, field):
    """WTForms validator — same rules and messages as the client-side check."""
    if not field.data or not field.data.strip():
        return
    nic = clean_nic(field.data)

    if len(nic) == 10:
        if not re.fullmatch(r'\d{9}[VX]', nic):
            raise ValidationError("Old NIC format must be 9 digits followed by 'V' or 'X'.")
    elif len(nic) == 12:
        if not nic.isdigit():
            raise ValidationError('New NIC format must contain exactly 12 digits.')
    else:
        raise ValidationError('NIC must be either 10 characters (old format) or 12 digits (new format).')

    _, days = _nic_year_days(nic)
    if not (1 <= days <= 366 or 501 <= days <= 866):
        raise ValidationError('Invalid number of days in NIC.')


def parse_nic(nic):
    """Decode a NIC into (birth_date, gender) — ('male'/'female').

    Returns (None, None) if the NIC is invalid; birth_date may be None when
    the encoded day doesn't exist in the birth year (e.g. Feb 29 in a
    non-leap year).
    """
    nic = clean_nic(nic)
    if not nic or not NIC_PATTERN.match(nic):
        return None, None

    year, days = _nic_year_days(nic)
    gender = 'female' if days >= 500 else 'male'
    if days >= 500:
        days -= 500
    if not (1 <= days <= 366):
        return None, None

    month = 1
    for month_len in _NIC_MONTH_DAYS:
        if days <= month_len:
            break
        days -= month_len
        month += 1

    try:
        return date(year, month, days), gender
    except ValueError:
        return None, gender


def nic_taken(nic, exclude_user_id=None):
    """True if another user already holds this NIC (case-insensitive)."""
    from app.extensions import db
    from app.models.user import User

    nic = clean_nic(nic)
    if not nic:
        return False
    existing = User.query.filter(db.func.upper(User.nic_no) == nic).first()
    return bool(existing and existing.id != exclude_user_id)
