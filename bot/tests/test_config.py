"""Secret-hygiene validation for Settings (P0-1)."""

import pytest
from pydantic import ValidationError

from src.utils.config import Settings

_BASE = {"BOT_TOKEN": "123456789:AAtest", "ADMIN_IDS": [1]}


def _make(**overrides: object) -> Settings:
    # _env_file=None keeps the test hermetic (ignore the repo .env).
    return Settings(_env_file=None, **{**_BASE, **overrides})


def test_production_rejects_placeholder_api_key() -> None:
    with pytest.raises(ValidationError):
        _make(ENV="production", DB_PASS="real-pass", API_SECRET_KEY="change-me-in-production")


def test_production_rejects_default_db_password() -> None:
    with pytest.raises(ValidationError):
        _make(ENV="production", DB_PASS="gorba_secret", API_SECRET_KEY="x" * 32)


def test_production_rejects_short_api_key() -> None:
    with pytest.raises(ValidationError):
        _make(ENV="production", DB_PASS="real-pass", API_SECRET_KEY="tooshort")


def test_production_rejects_empty_secrets() -> None:
    with pytest.raises(ValidationError):
        _make(ENV="production", DB_PASS="", API_SECRET_KEY="")


def test_production_accepts_strong_secrets() -> None:
    settings = _make(ENV="production", DB_PASS="real-strong-pass", API_SECRET_KEY="k" * 32)
    assert settings.is_production is True


def test_development_allows_placeholders() -> None:
    settings = _make(ENV="development")
    assert settings.is_production is False
    assert settings.API_SECRET_KEY == "change-me-in-production"


def test_online_payment_disabled_by_default() -> None:
    settings = _make(ENV="production", DB_PASS="real-pass", API_SECRET_KEY="k" * 32)
    assert settings.online_payment_enabled is False


def test_production_rejects_online_payment_without_link_secret() -> None:
    with pytest.raises(ValidationError):
        _make(
            ENV="production",
            DB_PASS="real-pass",
            API_SECRET_KEY="k" * 32,
            YOOKASSA_SHOP_ID="shop-1",
            YOOKASSA_SECRET_KEY="y" * 32,
            PAYMENT_LINK_SECRET="",
            PAYMENT_PAGE_URL="https://example.com",
        )


def test_production_rejects_online_payment_with_http_page_url() -> None:
    with pytest.raises(ValidationError):
        _make(
            ENV="production",
            DB_PASS="real-pass",
            API_SECRET_KEY="k" * 32,
            YOOKASSA_SHOP_ID="shop-1",
            YOOKASSA_SECRET_KEY="y" * 32,
            PAYMENT_LINK_SECRET="l" * 32,
            PAYMENT_PAGE_URL="http://example.com",
        )


def test_production_accepts_fully_configured_online_payment() -> None:
    settings = _make(
        ENV="production",
        DB_PASS="real-pass",
        API_SECRET_KEY="k" * 32,
        YOOKASSA_SHOP_ID="shop-1",
        YOOKASSA_SECRET_KEY="y" * 32,
        PAYMENT_LINK_SECRET="l" * 32,
        PAYMENT_PAGE_URL="https://example.com",
    )
    assert settings.online_payment_enabled is True
