"""Clerk session token verification helpers."""

from __future__ import annotations

from typing import Any

import jwt


def _normalize_key(raw_key: str) -> str:
    return raw_key.replace("\\n", "\n")


def decode_clerk_token(
    token: str,
    jwt_key: str,
    algorithms: tuple[str, ...],
    issuer: str | None = None,
    audience: str | None = None,
) -> dict[str, Any]:
    options = {"verify_aud": audience is not None}
    try:
        return jwt.decode(
            token,
            _normalize_key(jwt_key),
            algorithms=list(algorithms),
            issuer=issuer,
            audience=audience,
            options=options,
        )
    except jwt.PyJWTError as exc:
        raise ValueError("Invalid or expired Clerk token") from exc
