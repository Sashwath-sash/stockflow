import jwt
import pytest

from app.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_round_trip() -> None:
    encoded = hash_password("Customer123!")

    assert encoded != "Customer123!"
    assert verify_password("Customer123!", encoded)
    assert not verify_password("wrong-password", encoded)


def test_access_token_round_trip() -> None:
    token, lifetime = create_access_token("user-123")

    assert lifetime > 0
    assert decode_access_token(token) == "user-123"


def test_access_token_rejects_invalid_token() -> None:
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token("not-a-token")
