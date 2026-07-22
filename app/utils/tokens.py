"""Signed, self-invalidating tokens for password reset links.

Uses itsdangerous (bundled with Flask) rather than a DB-backed token table.
The signed payload embeds a short fingerprint of the user's current
password_hash, so the token stops verifying the moment the password
changes — no separate "used" flag or table needed.
"""
import hashlib
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import current_app

_SALT = 'password-reset'


def _serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


def _pwd_fingerprint(user):
    return hashlib.sha256(user.password_hash.encode('utf-8')).hexdigest()[:16]


def generate_reset_token(user):
    return _serializer().dumps(
        {'user_id': user.id, 'pwd_fp': _pwd_fingerprint(user)},
        salt=_SALT,
    )


def verify_reset_token(token, max_age=None):
    """Returns the User if the token is valid, unexpired, and the password
    hasn't changed since it was issued. Otherwise returns None."""
    from app.models.user import User

    if max_age is None:
        max_age = current_app.config.get('PASSWORD_RESET_MAX_AGE', 3600)

    try:
        data = _serializer().loads(token, salt=_SALT, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None

    user = User.query.get(data.get('user_id'))
    if not user or _pwd_fingerprint(user) != data.get('pwd_fp'):
        return None
    return user
