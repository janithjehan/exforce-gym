import hashlib


def _md5upper(text):
    return hashlib.md5(text.encode()).hexdigest().upper()


def generate_hash(merchant_id, order_id, amount, currency, merchant_secret):
    """Generate the MD5 hash required for PayHere checkout initiation.
    The merchant secret is used verbatim as issued by PayHere — never decoded."""
    amount_str  = f'{float(amount):.2f}'
    secret_hash = _md5upper(merchant_secret)
    raw         = f'{merchant_id}{order_id}{amount_str}{currency}{secret_hash}'
    return _md5upper(raw)


def verify_notification(form_data, merchant_secret):
    """Verify a PayHere server-to-server notification. Returns True if hash is valid."""
    merchant_id      = form_data.get('merchant_id', '')
    order_id         = form_data.get('order_id', '')
    payhere_amount   = form_data.get('payhere_amount', '')
    payhere_currency = form_data.get('payhere_currency', '')
    status_code      = form_data.get('status_code', '')
    received_hash    = form_data.get('md5sig', '').upper()

    secret_hash = _md5upper(merchant_secret)
    raw         = f'{merchant_id}{order_id}{payhere_amount}{payhere_currency}{status_code}{secret_hash}'
    return _md5upper(raw) == received_hash