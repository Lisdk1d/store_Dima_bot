"""Webhook-mode startup preconditions (P1-6)."""

from src.utils.config import Settings

_BASE = {"_env_file": None, "ENV": "development", "BOT_TOKEN": "1:a", "ADMIN_IDS": [1]}


def _make(**overrides: object) -> Settings:
    return Settings(**{**_BASE, **overrides})


def test_polling_mode_has_no_webhook_requirements() -> None:
    assert _make(BOT_MODE="polling").webhook_preconditions() == []


def test_webhook_mode_requires_host_and_secret() -> None:
    errors = _make(BOT_MODE="webhook", WEBHOOK_HOST="", WEBHOOK_SECRET="").webhook_preconditions()
    assert len(errors) == 2


def test_webhook_mode_requires_secret_when_host_set() -> None:
    errors = _make(
        BOT_MODE="webhook", WEBHOOK_HOST="https://example.com", WEBHOOK_SECRET=""
    ).webhook_preconditions()
    assert len(errors) == 1
    assert "WEBHOOK_SECRET" in errors[0]


def test_webhook_mode_ok_when_fully_configured() -> None:
    assert (
        _make(
            BOT_MODE="webhook", WEBHOOK_HOST="https://example.com", WEBHOOK_SECRET="s3cret"
        ).webhook_preconditions()
        == []
    )
