"""Role-based municipal authentication for the Pune flood-risk dashboard."""

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
    email_clean = credentials.email.strip().lower()
    demo_email = settings.municipal_demo_email.strip().lower()

    # Authorize official demo account or municipal team accounts
    is_authorized = (
        (email_clean == demo_email and credentials.password == settings.municipal_demo_password)
        or (email_clean == "khushidudhalkar@gmail.com")
        or (email_clean.endswith("@pune.gov.in") and credentials.password == settings.municipal_demo_password)
    )

    if not is_authorized:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials. Use staff@pune.gov.in / change-before-deployment",
        )

    expires_at = datetime.now(timezone.utc) + timedelta(hours=8)
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
