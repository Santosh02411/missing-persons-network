import pyotp

ISSUER_NAME = "Reunification Network"


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def get_provisioning_uri(secret: str, account_email: str) -> str:
    """otpauth:// URI that authenticator apps (Google Authenticator, Authy,
    1Password, etc.) can scan as a QR code to add the account."""
    return pyotp.totp.TOTP(secret).provisioning_uri(name=account_email, issuer_name=ISSUER_NAME)


def verify_totp_code(secret: str, code: str) -> bool:
    """valid_window=1 tolerates the code from one 30-second step before/after
    the current one, to absorb minor clock drift between server and phone."""
    return pyotp.totp.TOTP(secret).verify(code, valid_window=1)
