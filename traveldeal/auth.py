"""Email + password accounts: hashing, validation and session tokens.

Passwords are hashed with scrypt (Python standard library, no extra dependency) and a
per-password random salt. Session tokens are random; only their SHA-256 hash is stored,
so a copy of the database can't be used to sign in as anyone.

Reset a forgotten password from the server (there's no email sending in personal mode):

    python -m traveldeal.auth reset-password you@example.com
"""

from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import hmac
import re
import secrets
import sys

# scrypt cost parameters: ~16 MB and ~50 ms per hash. Stored in each hash so they can change later.
_N, _R, _P = 2**14, 8, 1
_DKLEN = 32
MIN_PASSWORD_LEN = 8
MAX_PASSWORD_LEN = 128
SESSION_DAYS = 30
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthError(ValueError):
    """A message that is safe to show to the person signing in."""


def normalize_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not _EMAIL_RE.match(email) or len(email) > 320:
        raise AuthError("Enter a valid email address.")
    return email


def check_password_rules(password: str) -> None:
    if len(password or "") < MIN_PASSWORD_LEN:
        raise AuthError(f"Use at least {MIN_PASSWORD_LEN} characters for your password.")
    if len(password) > MAX_PASSWORD_LEN:
        raise AuthError(f"Passwords can be at most {MAX_PASSWORD_LEN} characters.")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN)
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return f"scrypt${_N}${_R}${_P}${b64(salt)}${b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_b64, digest_b64 = stored.split("$")
        if algo != "scrypt":
            return False
        salt, expected = base64.b64decode(salt_b64), base64.b64decode(digest_b64)
        digest = hashlib.scrypt(password.encode(), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest, expected)


# A real hash to compare against when the email doesn't exist, so a wrong email and a
# wrong password take the same time and give the same message.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def burn_time(password: str) -> None:
    verify_password(password or "", _DUMMY_HASH)


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def subject_for(email: str) -> str:
    """auth_subject for email/password users (Google users are 'https://accounts.google.com|<sub>')."""
    return f"local|{email}"


def main(argv: list[str] | None = None) -> int:
    from .db import init_db, make_engine, session_factory
    from .repository import Repository

    parser = argparse.ArgumentParser(description="Manage email/password accounts.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    reset = sub.add_parser("reset-password", help="set a new password and sign the account out everywhere")
    reset.add_argument("email")
    args = parser.parse_args(argv)

    engine = make_engine()
    init_db(engine)
    repo = Repository(session_factory(engine))
    password = getpass.getpass("New password: ")
    if password != getpass.getpass("Repeat it: "):
        print("Passwords don't match.", file=sys.stderr)
        return 1
    try:
        repo.reset_password(args.email, password)
    except AuthError as e:
        print(e, file=sys.stderr)
        return 1
    print(f"Password updated for {normalize_email(args.email)}; existing sign-ins were ended.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
