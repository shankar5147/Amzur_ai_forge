from fastapi import APIRouter, Depends, HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.schemas import AuthResponse, GoogleAuthRequest, LoginRequest, SignupRequest, UserInfo
from app.services.auth_service import AuthError, AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    if not payload.email.endswith("@amzur.com"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Amzur email accounts (@amzur.com) are allowed to register.",
        )
    service = AuthService(db)
    try:
        user = await service.signup(payload.email, payload.password, payload.full_name)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    token = AuthService.create_token(user.id)
    return AuthResponse(
        access_token=token,
        user=UserInfo.model_validate(user),
    )


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    if not payload.email.endswith("@amzur.com"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Amzur email accounts (@amzur.com) are allowed to sign in.",
        )
    service = AuthService(db)
    try:
        user = await service.login(payload.email, payload.password)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    token = AuthService.create_token(user.id)
    return AuthResponse(
        access_token=token,
        user=UserInfo.model_validate(user),
    )


@router.post("/google", response_model=AuthResponse)
async def google_auth(payload: GoogleAuthRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    try:
        idinfo = id_token.verify_oauth2_token(
            payload.credential,
            google_requests.Request(),
            audience=settings.google_client_id or None,
            clock_skew_in_seconds=10,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token.",
        ) from exc

    google_id = idinfo["sub"]
    email = idinfo["email"]
    full_name = idinfo.get("name", email.split("@")[0])
    avatar_url = idinfo.get("picture")

    service = AuthService(db)
    user = await service.google_login(google_id, email, full_name, avatar_url)

    token = AuthService.create_token(user.id)
    return AuthResponse(
        access_token=token,
        user=UserInfo.model_validate(user),
    )
