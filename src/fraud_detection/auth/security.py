"""Password hashing and token helpers without external auth dependencies."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str, iterations: int = 120_000) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    algorithm, raw_iterations, salt, expected = password_hash.split("$", 3)
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(raw_iterations))
    return hmac.compare_digest(digest.hex(), expected)


def create_access_token(subject: str, role: str, secret: str, ttl_seconds: int) -> str:
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    header = {"alg": "HS256", "typ": "JWT"}
    encoded_header = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    message = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    return f"{encoded_header}.{encoded_payload}.{_b64url_encode(signature)}"


def decode_access_token(token: str, secret: str) -> dict[str, str | int]:
    header_part, payload_part, signature_part = token.split(".", 2)
    message = f"{header_part}.{payload_part}".encode("utf-8")
    expected_signature = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    if not hmac.compare_digest(_b64url_decode(signature_part), expected_signature):
        raise ValueError("Invalid token signature")

    payload = json.loads(_b64url_decode(payload_part))
    if int(payload["exp"]) < int(datetime.now(tz=timezone.utc).timestamp()):
        raise ValueError("Token has expired")
    return payload
