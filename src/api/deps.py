from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.jwt import decode_access_token
from src.models import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user_id(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> UUID:
    """Validate the access token and return its user ID without a DB query."""

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_id = decode_access_token(token)

    if user_id is None:
        raise credentials_exception

    return user_id


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Resolve the authenticated user from a JWT access token."""

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_id = decode_access_token(token)

    if user_id is None:
        raise credentials_exception

    user = await db.scalar(
        select(User).where(User.id == user_id)
    )

    if user is None:
        raise credentials_exception

    return user
