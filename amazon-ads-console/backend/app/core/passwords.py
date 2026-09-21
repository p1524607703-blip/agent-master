import base64
import hashlib
import hmac
import secrets

_PBKDF2_ITERATIONS = 600_000
_SALT_BYTES = 16
_DKLEN = 32


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode('ascii').rstrip('=')


def _b64decode(value: str) -> bytes:
    padding = '=' * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    if not isinstance(password, str) or len(password) < 12:
        raise ValueError('password must be at least 12 characters')
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        _PBKDF2_ITERATIONS,
        dklen=_DKLEN,
    )
    return 'pbkdf2_sha256${}${}${}'.format(
        _PBKDF2_ITERATIONS, _b64encode(salt), _b64encode(digest)
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = encoded.split('$', 3)
        if algorithm != 'pbkdf2_sha256':
            return False
        salt = _b64decode(salt_b64)
        expected = _b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            int(iterations),
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except (TypeError, ValueError):
        return False
