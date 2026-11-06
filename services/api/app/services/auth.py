"""Minimal role-based municipal authentication for the hackathon dashboard."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.schemas import LoginRequest, TokenResponse

_bearer = HTTPBearer(auto_error=False)


def login(credentials: LoginRequest) -> TokenResponse:
    settings = get_settings()
    if credentials.email.lower() != settings.municipal_demo_email.lower() or credentials.password != settings.municipal_demo_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid municipal credentials")
    expires_at = datetime.now(timezone.utc) + timedelta(hours=4)
    token = jwt.encode(
        {"sub": credentials.email, "role": "municipal_staff", "exp": expires_at},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return TokenResponse(access_token=token)


def require_staff(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Municipal authentication is required")
    settings = get_settings()
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token") from error
    if payload.get("role") != "municipal_staff" or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Municipal staff role is required")
    return str(payload["sub"])
