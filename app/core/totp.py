import pyotp

ISSUER_NAME = "Reunification Network"


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def get_provisioning_uri(secret: str, account_email: str) -> str:
    """otpauth:// URI that authenticator apps (Google Authenticator, Authy,
    1Password, etc.) can scan as a QR code to add the account."""
    return pyotp.totp.TOTP(secret).provisioning_uri(name=account_email, issuer_name=ISSUER_NAME)


def verify_totp_code(secret: str, code: str) -> bool:
    """valid_window=4 tolerates codes from up to 4 time-steps (120 seconds)
    before/after the current one, to absorb clock drift between the server
    and the phone's authenticator app -- the single most common cause of
    "I scanned the QR code but the code is always rejected" reports, since
    TOTP codes are time-based and a server clock even a couple minutes off
    invalidates every code. If codes still fail at this window, the server's
    system clock is very likely wrong -- check it before assuming a bug."""
    return pyotp.totp.TOTP(secret).verify(code, valid_window=4)
