from uuid import uuid4

from src.core.jwt import create_access_token, decode_access_token


def test_access_token_can_be_created():
    user_id = uuid4()

    token = create_access_token(user_id)

    assert isinstance(token, str)
    assert len(token) > 0


def test_access_token_contains_correct_user_id():
    user_id = uuid4()

    token = create_access_token(user_id)

    assert decode_access_token(token) == user_id


def test_invalid_token_is_rejected():
    assert decode_access_token("invalid-token") is None


def test_empty_token_is_rejected():
    assert decode_access_token("") is None


def test_non_string_token_is_rejected():
    assert decode_access_token(None) is None


def test_token_with_invalid_user_id_is_rejected():
    from jose import jwt

    from src.core.config import settings
    from src.core.jwt import ALGORITHM

    token = jwt.encode(
        {"sub": "not-a-valid-uuid"},
        settings.secret_key.get_secret_value(),
        algorithm=ALGORITHM,
    )

    assert decode_access_token(token) is None
from datetime import datetime, timedelta, timezone

from jose import jwt

from src.core.config import settings
from src.core.jwt import ALGORITHM


def test_expired_token_is_rejected():
    expired_token = jwt.encode(
        {
            "sub": str(uuid4()),
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        settings.secret_key.get_secret_value(),
        algorithm=ALGORITHM,
    )

    assert decode_access_token(expired_token) is None


def test_token_signed_with_wrong_secret_is_rejected():
    user_id = uuid4()

    wrong_token = jwt.encode(
        {"sub": str(user_id)},
        "completely-different-test-secret",
        algorithm=ALGORITHM,
    )

    assert decode_access_token(wrong_token) is None
