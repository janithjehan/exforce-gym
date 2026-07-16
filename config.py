import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 'postgresql://postgres:password@localhost/exforce_gym'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERMANENT_SESSION_LIFETIME = timedelta(
        hours=int(os.environ.get('SESSION_TIMEOUT_HOURS', 2))
    )
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    WTF_CSRF_ENABLED = True
    GYM_NAME = 'Exforce Gym'
    TIMEZONE = 'Asia/Colombo'

    # PayHere
    PAYHERE_MERCHANT_ID = os.environ.get('PAYHERE_MERCHANT_ID', '')
    PAYHERE_MERCHANT_SECRET = os.environ.get('PAYHERE_MERCHANT_SECRET', '')
    PAYHERE_SANDBOX = os.environ.get('PAYHERE_SANDBOX', 'True') == 'True'
    PAYHERE_BASE_URL = (
        'https://sandbox.payhere.lk/pay/checkout'
        if os.environ.get('PAYHERE_SANDBOX', 'True') == 'True'
        else 'https://www.payhere.lk/pay/checkout'
    )
    # Override callback base URLs for local dev with ngrok (e.g. https://abc123.ngrok-free.app)
    # PAYHERE_NOTIFY_BASE_URL  — used for notify_url (server-to-server, must be public)
    # PAYHERE_APP_BASE_URL     — used for return_url and cancel_url (browser redirect)
    #                            defaults to PAYHERE_NOTIFY_BASE_URL if not set separately
    PAYHERE_NOTIFY_BASE_URL = os.environ.get('PAYHERE_NOTIFY_BASE_URL', '')
    PAYHERE_APP_BASE_URL    = os.environ.get(
        'PAYHERE_APP_BASE_URL',
        os.environ.get('PAYHERE_NOTIFY_BASE_URL', ''),  # fall back to notify base
    )

    # Notify.lk SMS gateway (FR-NOT-04: SMS channel optional)
    NOTIFYLK_ENABLED = os.environ.get('NOTIFYLK_ENABLED', 'False') == 'True'
    NOTIFYLK_USER_ID = os.environ.get('NOTIFYLK_USER_ID', '')
    NOTIFYLK_API_KEY = os.environ.get('NOTIFYLK_API_KEY', '')
    NOTIFYLK_SENDER_ID = os.environ.get('NOTIFYLK_SENDER_ID', 'NotifyDEMO')


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
