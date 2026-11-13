from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import JWTError, jwt

from src.core.config import settings


ALGORITHM = "HS256"


def create_access_token(user_id: UUID) -> str:
    """Create a signed JWT access token for a user."""

    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )

    payload = {
        "sub": str(user_id),
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        settings.secret_key.get_secret_value(),
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> UUID | None:
    """Decode a JWT and return its user UUID if valid."""

    if not isinstance(token, str) or not token:
        return None

    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[ALGORITHM],
        )

        subject = payload.get("sub")
        if not isinstance(subject, str):
            return None

        return UUID(subject)

    except (JWTError, ValueError, TypeError):
        return None
