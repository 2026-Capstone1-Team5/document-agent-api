import base64
import hashlib
import hmac
import json
import secrets
from binascii import Error as BinasciiError
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from src.auth.exceptions import ExpiredAccessTokenError, InvalidAccessTokenError, InvalidApiKeyError

PBKDF2_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = 600_000
PBKDF2_SALT_BYTES = 16
API_KEY_PREFIX = "dagk_"
API_KEY_TOKEN_BYTES = 32
API_KEY_DISPLAY_PREFIX_LENGTH = len(API_KEY_PREFIX) + 12


@dataclass(slots=True)
class AccessTokenPayload:
    user_id: str
    email: str
    expires_at: datetime


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(PBKDF2_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return (
        f"pbkdf2_{PBKDF2_ALGORITHM}$"
        f"{PBKDF2_ITERATIONS}$"
        f"{_base64url_encode(salt)}$"
        f"{_base64url_encode(derived)}"
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt_encoded, expected_hash_encoded = password_hash.split("$")
        if algorithm != f"pbkdf2_{PBKDF2_ALGORITHM}":
            return False
        iterations_value = int(iterations)
        salt = _base64url_decode(salt_encoded)
        expected_hash = _base64url_decode(expected_hash_encoded)
    except (BinasciiError, TypeError, ValueError):
        return False

    candidate_hash = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt,
        iterations_value,
    )
    return hmac.compare_digest(candidate_hash, expected_hash)


def create_access_token(
    *,
    user_id: str,
    email: str,
    secret_key: str,
    expires_in_seconds: int,
) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    expires_at = datetime.now(UTC) + timedelta(seconds=expires_in_seconds)
    payload = {
        "sub": user_id,
        "email": email,
        "exp": int(expires_at.timestamp()),
    }
    encoded_header = _base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _base64url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8"),
    )
    message = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    signature = hmac.new(secret_key.encode("utf-8"), message, hashlib.sha256).digest()
    encoded_signature = _base64url_encode(signature)
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


def create_api_key() -> tuple[str, str]:
    raw_api_key = f"{API_KEY_PREFIX}{secrets.token_urlsafe(API_KEY_TOKEN_BYTES)}"
    return raw_api_key, raw_api_key[:API_KEY_DISPLAY_PREFIX_LENGTH]


def hash_api_key(api_key: str) -> str:
    normalized_api_key = normalize_api_key(api_key)
    return hashlib.sha256(normalized_api_key.encode("utf-8")).hexdigest()


def is_probable_api_key(value: str) -> bool:
    return value.startswith(API_KEY_PREFIX)


def decode_access_token(*, token: str, secret_key: str) -> AccessTokenPayload:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
    except ValueError as exc:
        raise InvalidAccessTokenError from exc

    message = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    expected_signature = hmac.new(secret_key.encode("utf-8"), message, hashlib.sha256).digest()
    actual_signature = _base64url_decode_safe(encoded_signature)
    if actual_signature is None or not hmac.compare_digest(actual_signature, expected_signature):
        raise InvalidAccessTokenError

    payload_bytes = _base64url_decode_safe(encoded_payload)
    if payload_bytes is None:
        raise InvalidAccessTokenError

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise InvalidAccessTokenError from exc

    user_id = payload.get("sub")
    email = payload.get("email")
    exp = payload.get("exp")
    if not isinstance(user_id, str) or not user_id:
        raise InvalidAccessTokenError
    if not isinstance(email, str) or not email:
        raise InvalidAccessTokenError
    if not isinstance(exp, int):
        raise InvalidAccessTokenError

    expires_at = datetime.fromtimestamp(exp, tz=UTC)
    if expires_at <= datetime.now(UTC):
        raise ExpiredAccessTokenError

    return AccessTokenPayload(
        user_id=user_id,
        email=email,
        expires_at=expires_at,
    )


def normalize_api_key(api_key: str) -> str:
    normalized = api_key.strip()
    if not normalized.startswith(API_KEY_PREFIX) or len(normalized) <= len(API_KEY_PREFIX):
        raise InvalidApiKeyError
    return normalized


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _base64url_decode_safe(value: str) -> bytes | None:
    try:
        return _base64url_decode(value)
    except (BinasciiError, TypeError, ValueError):
        return None
