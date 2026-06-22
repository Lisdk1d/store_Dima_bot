"""Signed payment-link tokens (online payment v1)."""

import time

import pytest

from src.utils.payment_links import PaymentLinkError, sign_payment_token, verify_payment_token

SECRET = "link-secret"


def test_valid_token_roundtrip() -> None:
    token = sign_payment_token(42, 7, secret=SECRET, ttl_seconds=60)
    payload = verify_payment_token(token, secret=SECRET)
    assert payload == {"order_id": 42, "user_id": 7}


def test_tampered_payload_rejected() -> None:
    token = sign_payment_token(42, 7, secret=SECRET, ttl_seconds=60)
    encoded_payload, _, signature = token.partition(".")
    tampered = f"{encoded_payload}AA.{signature}"
    with pytest.raises(PaymentLinkError):
        verify_payment_token(tampered, secret=SECRET)


def test_tampered_signature_rejected() -> None:
    token = sign_payment_token(42, 7, secret=SECRET, ttl_seconds=60)
    encoded_payload, _, _ = token.partition(".")
    with pytest.raises(PaymentLinkError):
        verify_payment_token(f"{encoded_payload}.{'0' * 64}", secret=SECRET)


def test_expired_token_rejected() -> None:
    token = sign_payment_token(42, 7, secret=SECRET, ttl_seconds=-1)
    with pytest.raises(PaymentLinkError):
        verify_payment_token(token, secret=SECRET)


def test_wrong_secret_rejected() -> None:
    token = sign_payment_token(42, 7, secret=SECRET, ttl_seconds=60)
    with pytest.raises(PaymentLinkError):
        verify_payment_token(token, secret="other-secret")


@pytest.mark.parametrize("malformed", ["", "no-separator-here", ".", "abc.", ".xyz"])
def test_malformed_token_rejected(malformed: str) -> None:
    with pytest.raises(PaymentLinkError):
        verify_payment_token(malformed, secret=SECRET)


def test_token_is_url_safe() -> None:
    # Order/user ids and the resulting token must survive being placed in a URL
    # query string unescaped (no '/', '+', or padding '=').
    token = sign_payment_token(123456789, 987654321, secret=SECRET, ttl_seconds=60)
    assert all(char not in token for char in "/+=")


def test_ttl_boundary_just_within_window() -> None:
    token = sign_payment_token(1, 1, secret=SECRET, ttl_seconds=1)
    assert verify_payment_token(token, secret=SECRET) == {"order_id": 1, "user_id": 1}
    time.sleep(1.1)
    with pytest.raises(PaymentLinkError):
        verify_payment_token(token, secret=SECRET)
