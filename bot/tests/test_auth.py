"""Telegram WebApp initData validation and the admin dependency (P0-3)."""

import asyncio
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from fastapi import HTTPException

import src.utils.auth as auth_mod
from src.utils.auth import AdminPrincipal, InitDataError, require_admin, resolve_admin, validate_init_data
from src.utils.config import Settings

BOT_TOKEN = "123456789:AA-test-token"
ADMIN_ID = 42


def make_init_data(bot_token: str, user: dict, *, auth_date: int | None = None, tamper: bool = False) -> str:
    auth_date = auth_date if auth_date is not None else int(time.time())
    fields = {"auth_date": str(auth_date), "user": json.dumps(user, separators=(",", ":"))}
    data_check_string = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    fields["hash"] = "0" * 64 if tamper else digest
    return urlencode(fields)


def _settings(**overrides: object) -> Settings:
    base = {
        "_env_file": None,
        "ENV": "development",
        "BOT_TOKEN": BOT_TOKEN,
        "ADMIN_IDS": [ADMIN_ID],
        "API_SECRET_KEY": "k" * 32,
        "ADMIN_AUTH_MODE": "initdata",
        "INIT_DATA_MAX_AGE": 86400,
    }
    base.update(overrides)
    return Settings(**base)


# --- validate_init_data -------------------------------------------------------

def test_valid_init_data_returns_fields() -> None:
    raw = make_init_data(BOT_TOKEN, {"id": ADMIN_ID, "username": "boss"})
    fields = validate_init_data(raw, BOT_TOKEN, max_age_seconds=86400)
    assert json.loads(fields["user"])["id"] == ADMIN_ID


def test_tampered_hash_rejected() -> None:
    raw = make_init_data(BOT_TOKEN, {"id": ADMIN_ID}, tamper=True)
    with pytest.raises(InitDataError):
        validate_init_data(raw, BOT_TOKEN, max_age_seconds=86400)


def test_wrong_bot_token_rejected() -> None:
    raw = make_init_data(BOT_TOKEN, {"id": ADMIN_ID})
    with pytest.raises(InitDataError):
        validate_init_data(raw, "999:other-token", max_age_seconds=86400)


def test_missing_hash_rejected() -> None:
    with pytest.raises(InitDataError):
        validate_init_data("auth_date=1&user=%7B%7D", BOT_TOKEN, max_age_seconds=86400)


def test_expired_init_data_rejected() -> None:
    raw = make_init_data(BOT_TOKEN, {"id": ADMIN_ID}, auth_date=int(time.time()) - 100_000)
    with pytest.raises(InitDataError):
        validate_init_data(raw, BOT_TOKEN, max_age_seconds=86400)


def test_empty_init_data_rejected() -> None:
    with pytest.raises(InitDataError):
        validate_init_data("", BOT_TOKEN, max_age_seconds=86400)


# --- resolve_admin ------------------------------------------------------------

def test_resolve_admin_accepts_known_admin() -> None:
    fields = {"user": json.dumps({"id": ADMIN_ID, "username": "boss"})}
    principal = resolve_admin(fields, [ADMIN_ID])
    assert principal == AdminPrincipal(admin_id=ADMIN_ID, username="boss", auth_method="initdata")


def test_resolve_admin_rejects_non_admin() -> None:
    fields = {"user": json.dumps({"id": 999})}
    with pytest.raises(HTTPException) as exc:
        resolve_admin(fields, [ADMIN_ID])
    assert exc.value.status_code == 403


def test_resolve_admin_rejects_missing_user() -> None:
    with pytest.raises(HTTPException) as exc:
        resolve_admin({}, [ADMIN_ID])
    assert exc.value.status_code == 401


# --- require_admin dependency -------------------------------------------------

def test_require_admin_initdata_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_mod, "settings", _settings())
    raw = make_init_data(BOT_TOKEN, {"id": ADMIN_ID, "username": "boss"})
    principal = asyncio.run(require_admin(authorization=f"tma {raw}"))
    assert principal.admin_id == ADMIN_ID and principal.auth_method == "initdata"


def test_require_admin_missing_header_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_mod, "settings", _settings())
    with pytest.raises(HTTPException) as exc:
        asyncio.run(require_admin())
    assert exc.value.status_code == 401


def test_require_admin_non_admin_403(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_mod, "settings", _settings())
    raw = make_init_data(BOT_TOKEN, {"id": 999})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(require_admin(x_telegram_init_data=raw))
    assert exc.value.status_code == 403


def test_require_admin_devkey_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_mod, "settings", _settings(ADMIN_AUTH_MODE="devkey"))
    ok = asyncio.run(require_admin(x_api_key="k" * 32))
    assert ok.auth_method == "devkey"
    with pytest.raises(HTTPException) as exc:
        asyncio.run(require_admin(x_api_key="wrong"))
    assert exc.value.status_code == 401
