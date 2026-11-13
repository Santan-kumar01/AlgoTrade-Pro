import pytest

from src.core.security import hash_password, verify_password


def test_password_is_hashed_using_argon2id():
    password = "StrongPassword@2026"

    password_hash = hash_password(password)

    assert password_hash.startswith("$argon2id$")
    assert password_hash != password


def test_password_hash_is_not_plaintext():
    password = "StrongPassword@2026"

    assert hash_password(password) != password


def test_password_hash_uses_unique_salts():
    password = "StrongPassword@2026"

    first_hash = hash_password(password)
    second_hash = hash_password(password)

    assert first_hash != second_hash


def test_correct_password_verification():
    password = "StrongPassword@2026"
    password_hash = hash_password(password)

    assert verify_password(password, password_hash) is True


def test_incorrect_password_verification():
    password_hash = hash_password("StrongPassword@2026")

    assert verify_password("WrongPassword@2026", password_hash) is False


def test_invalid_hash_returns_false():
    assert verify_password("SomePassword", "invalid-hash") is False


def test_empty_password_is_rejected():
    with pytest.raises(ValueError):
        hash_password("")


def test_non_string_password_is_rejected():
    with pytest.raises(ValueError):
        hash_password(None)


def test_empty_password_verification_returns_false():
    assert verify_password("", "some-hash") is False
