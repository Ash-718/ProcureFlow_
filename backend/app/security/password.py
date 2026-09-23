"""
Password hashing, compatible with Spring's ``BCryptPasswordEncoder``.

The seeded accounts carry ``$2b$10$`` hashes. Those must keep verifying after
the migration or every demo login breaks, so this module uses ``bcrypt``
directly at **cost 10** — Spring's default strength.

`passlib` is deliberately not used: 1.7.4 is unmaintained and crashes against
`bcrypt` >= 4.1 while reading ``bcrypt.__about__.__version__``.

The 72-byte rule
----------------
bcrypt only considers the first 72 bytes of a password. Java's encoder
truncates silently; Python's ``bcrypt`` 4.x raises ``ValueError`` instead. Left
alone, a >72-byte password would work on the Java backend and return a 500 on
the Python one. Both paths here truncate first, matching Java's behaviour.
Truncation is on **bytes, not characters**, because that is the unit bcrypt
counts and a multi-byte character must not be split.
"""
from __future__ import annotations

import re

import bcrypt

#: Spring's `BCryptPasswordEncoder` default strength.
BCRYPT_ROUNDS = 10

_MAX_PASSWORD_BYTES = 72

#: A well-formed bcrypt digest: version tag, two-digit cost, then 53 chars of
#: bcrypt-alphabet base64 — 60 characters in total.
#:
#: Checked *before* calling into bcrypt because the 4.x Rust core does not
#: raise on a malformed digest, it **panics**: `pyo3_runtime.PanicException`
#: derives from `BaseException`, so an ordinary `except Exception` will not stop
#: it and one corrupt row would take down the request. Validating the shape
#: first means that path is never reached.
_BCRYPT_HASH_RE = re.compile(r"^\$2[abxy]\$\d{2}\$[./A-Za-z0-9]{53}$")


def _prepare(password: str) -> bytes:
    """UTF-8 encode and truncate to bcrypt's 72-byte limit, as Java does."""
    raw = password.encode("utf-8")
    if len(raw) <= _MAX_PASSWORD_BYTES:
        return raw
    truncated = raw[:_MAX_PASSWORD_BYTES]
    # Never hand bcrypt a partial multi-byte sequence.
    while truncated:
        try:
            truncated.decode("utf-8")
            break
        except UnicodeDecodeError:
            truncated = truncated[:-1]
    return truncated


def hash_password(password: str) -> str:
    """Hash a plaintext password. Produces a ``$2b$10$`` digest."""
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("ascii")


def is_valid_hash(password_hash: str | None) -> bool:
    """True when the string is a structurally valid bcrypt digest."""
    return bool(password_hash) and bool(_BCRYPT_HASH_RE.match(password_hash))


def verify_password(password: str, password_hash: str) -> bool:
    """
    Check a password against a stored hash.

    Returns ``False`` rather than raising on a malformed or non-bcrypt hash, so
    one corrupt row cannot turn a failed login into a 500. Accepts every bcrypt
    version tag — Spring has emitted both ``$2a$`` and ``$2b$`` over the years
    and they verify identically.
    """
    if not is_valid_hash(password_hash):
        return False
    try:
        return bcrypt.checkpw(_prepare(password), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False
    except BaseException as exc:  # noqa: BLE001 - see _BCRYPT_HASH_RE
        # Backstop for a bcrypt panic on input the regex judged well-formed.
        # Control-flow exceptions must still propagate.
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        return False


def needs_rehash(password_hash: str) -> bool:
    """
    True when a stored hash uses a weaker cost than the current setting.

    Not wired into the login path yet; it exists so a future opportunistic
    upgrade-on-login has the check it needs.
    """
    try:
        cost = int(password_hash.split("$")[2])
    except (IndexError, ValueError):
        return True
    return cost < BCRYPT_ROUNDS


__all__ = ["BCRYPT_ROUNDS", "hash_password", "verify_password", "needs_rehash"]
