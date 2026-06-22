"""Admin authentication for the FastAPI panel.

Primary mechanism: **Telegram WebApp initData** — a payload signed by Telegram
with an HMAC derived from the bot token. The panel sends it on every request,
so no secret is ever stored in the browser. We verify the signature, check the
``auth_date`` freshness, and require the Telegram ``user.id`` to be in
``ADMIN_IDS``.

A dev-only ``X-API-Key`` fallback exists for local work (``ADMIN_AUTH_MODE=devkey``)
and is rejected in production by config validation.

Cookie-based sessions are intentionally NOT used: the panel runs inside a
Telegram WebApp iframe (third-party context), where browsers partition/block
cookies — a per-request signed header is the robust pattern for this platform.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from typing import Annotated
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException

from src.utils.config import settings

logger = logging.getLogger(__name__)

# Tolerate small clock skew for auth_date values dated slightly in the future.
_FUTURE_SKEW_SECONDS = 300


class InitDataError(Exception):
    """Raised when Telegram WebApp initData fails validation."""


@dataclass(frozen=True)
class AdminPrincipal:
    """The authenticated admin behind a request (used for audit logging)."""

    admin_id: int
    username: str | None
    auth_method: str  # "initdata" | "devkey"


def validate_init_data(init_data: str, bot_token: str, *, max_age_seconds: int) -> dict[str, str]:
    """Verify Telegram WebApp initData and return its parsed fields.

    Raises ``InitDataError`` on an empty payload, missing/invalid ``hash``, or a
    stale/future ``auth_date``. Pure (stdlib only) so it is unit-testable.
    """
    if not init_data:
        raise InitDataError("empty initData")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise InitDataError("missing hash")

    # data-check-string: every remaining field, sorted, joined as key=value\n
    data_check_string = "\n".join(f"{key}={pairs[key]}" for key in sorted(pairs))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise InitDataError("hash mismatch")

    auth_date = pairs.get("auth_date")
    if auth_date is None or not auth_date.isdigit():
        raise InitDataError("missing or invalid auth_date")

    age = time.time() - int(auth_date)
    if age > max_age_seconds:
        raise InitDataError("initData expired")
    if age < -_FUTURE_SKEW_SECONDS:
        raise InitDataError("auth_date is in the future")

    return pairs


def resolve_admin(fields: dict[str, str], admin_ids: list[int]) -> AdminPrincipal:
    """Map validated initData fields to an admin principal or raise HTTP 401/403."""
    user_raw = fields.get("user")
    if not user_raw:
        raise HTTPException(status_code=401, detail="initData has no user")
    try:
        user = json.loads(user_raw)
        admin_id = int(user["id"])
    except (ValueError, KeyError, TypeError) as error:
        raise HTTPException(status_code=401, detail="initData user is malformed") from error

    if admin_id not in admin_ids:
        raise HTTPException(status_code=403, detail="Not an admin")

    return AdminPrincipal(
        admin_id=admin_id,
        username=user.get("username"),
        auth_method="initdata",
    )


def _extract_init_data(authorization: str | None, x_init_data: str | None) -> str | None:
    if x_init_data:
        return x_init_data
    if authorization and authorization.lower().startswith("tma "):
        return authorization[4:].strip()
    return None


def _extract_api_key(x_api_key: str | None, authorization: str | None) -> str | None:
    if x_api_key:
        return x_api_key
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


async def require_admin(
    authorization: Annotated[str | None, Header()] = None,
    x_telegram_init_data: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> AdminPrincipal:
    """FastAPI dependency: authenticate the admin per the configured mode."""
    mode = settings.ADMIN_AUTH_MODE.strip().lower()

    if mode == "initdata":
        init_data = _extract_init_data(authorization, x_telegram_init_data)
        if not init_data:
            raise HTTPException(status_code=401, detail="Missing Telegram initData")
        try:
            fields = validate_init_data(
                init_data, settings.BOT_TOKEN, max_age_seconds=settings.INIT_DATA_MAX_AGE
            )
        except InitDataError as error:
            logger.warning("initData rejected: %s", error)
            raise HTTPException(status_code=401, detail="Invalid Telegram initData") from error
        return resolve_admin(fields, settings.ADMIN_IDS)

    # devkey: dev-only shared key (config forbids this mode in production).
    token = _extract_api_key(x_api_key, authorization)
    if not token or not hmac.compare_digest(token, settings.API_SECRET_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return AdminPrincipal(admin_id=0, username="devkey", auth_method="devkey")
