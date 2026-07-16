"""Payment confirmation SMS — the only SMS the system sends.

Fired after a payment is recorded (manual entry by staff or PayHere
success callback). Degrades gracefully: returns (False, reason) when
Notify.lk is unconfigured or the member has no usable phone number.
"""
from app.utils.notifylk import send_sms, is_sms_configured


def send_payment_confirmation(payment):
    """Send an SMS receipt to the paying member. Returns (ok, error)."""
    if not is_sms_configured():
        return False, 'SMS gateway not configured'

    member = payment.member
    phone = member.contact_no or (member.user.phone if member.user else None)
    if not phone:
        return False, 'Member has no contact number'

    parts = [
        f'Hi {member.user.first_name}, your payment of LKR {payment.amount:,.2f} '
        f'({payment.method.label}) to Exforce Gym has been received.'
    ]
    if payment.membership and payment.membership.package:
        ms = payment.membership
        parts.append(
            f'{ms.package.name} membership valid until '
            f'{ms.end_date.strftime("%d %b %Y")}.'
        )
    if payment.reference_no:
        parts.append(f'Ref: {payment.reference_no}.')
    parts.append('Thank you!')

    return send_sms(phone, ' '.join(parts))