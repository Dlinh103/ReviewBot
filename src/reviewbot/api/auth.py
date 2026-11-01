"""Authentication and User Management API router for ReviewBot."""

import logging
import re
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from reviewbot.core.security import create_access_token, decode_access_token
from reviewbot.db.models import User
from reviewbot.db.repositories import UserRepository
from reviewbot.db.session import get_db_session

logger = logging.getLogger("reviewbot.api.auth")

router = APIRouter(tags=["authentication"])

AUTH_TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "auth.html"

COOKIE_NAME = "reviewbot_token"
MAX_AGE_SECONDS = 60 * 60 * 24 * 7  # 7 days


class RegisterRequest(BaseModel):
    """Payload to register a new platform account."""

    username: str = Field(min_length=3, max_length=50, description="Tên đăng nhập")
    email: str = Field(min_length=5, max_length=255, description="Địa chỉ email")
    password: str = Field(min_length=6, max_length=128, description="Mật khẩu")
    full_name: str = Field(default="", max_length=100, description="Họ và tên")


class LoginRequest(BaseModel):
    """Payload for user sign in."""

    identifier: str = Field(min_length=3, description="Tên đăng nhập hoặc email")
    password: str = Field(min_length=1, description="Mật khẩu")


class UpdateProfileRequest(BaseModel):
    """Payload to update personal profile or password."""

    full_name: str | None = Field(default=None, max_length=100)
    avatar_url: str | None = Field(default=None, max_length=500)
    new_password: str | None = Field(default=None, min_length=6, max_length=128)


def _format_user(user: User) -> dict[str, Any]:
    """Convert User model to safe serializable dictionary."""
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name or user.username,
        "avatar_url": user.avatar_url,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _validate_email(email: str) -> bool:
    """Basic RFC 5322 regex validation for email."""
    pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    return bool(re.match(pattern, email.strip()))


def get_optional_current_user(
    authorization: Annotated[str | None, Header()] = None,
    reviewbot_token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> User | None:
    """Dependency to retrieve the current user if token is present and valid."""
    token: str | None = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    elif reviewbot_token:
        token = reviewbot_token.strip()

    if not token:
        return None

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None

    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError):
        return None

    with get_db_session() as session:
        user_repo = UserRepository(session)
        user = user_repo.get_by_id(user_id)
        if user and user.is_active:
            session.expunge(user)
            return user
    return None


def get_current_user(
    user: Annotated[User | None, Depends(get_optional_current_user)],
) -> User:
    """Dependency requiring active authentication."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn. Vui lòng đăng nhập lại.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@router.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, response: Response) -> dict[str, Any]:
    """Register a new user account and authenticate immediately."""
    username = req.username.strip()
    email = req.email.strip().lower()

    if not re.match(r"^[a-zA-Z0-9_\-\.]+$", username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên đăng nhập chỉ được chứa chữ cái, số, dấu gạch dưới và dấu chấm.",
        )

    if not _validate_email(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Định dạng email không hợp lệ.",
        )

    with get_db_session() as session:
        user_repo = UserRepository(session)
        try:
            user = user_repo.create_user(
                username=username,
                email=email,
                password=req.password,
                full_name=req.full_name or username,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc

        # Issue access token
        token_data = {
            "sub": str(user.id),
            "username": user.username,
            "email": user.email,
            "is_superuser": user.is_superuser,
        }
        token = create_access_token(token_data)
        user_dict = _format_user(user)

    # Set secure cookie
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,  # Allow http on local development
    )

    return {
        "status": "success",
        "message": "Đăng ký tài khoản thành công!",
        "access_token": token,
        "token_type": "bearer",
        "user": user_dict,
    }


@router.post("/api/auth/login")
def login(req: LoginRequest, response: Response) -> dict[str, Any]:
    """Authenticate with username or email and password."""
    with get_db_session() as session:
        user_repo = UserRepository(session)
        user = user_repo.authenticate(req.identifier, req.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tài khoản hoặc mật khẩu không chính xác.",
            )

        token_data = {
            "sub": str(user.id),
            "username": user.username,
            "email": user.email,
            "is_superuser": user.is_superuser,
        }
        token = create_access_token(token_data)
        user_dict = _format_user(user)

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,
    )

    return {
        "status": "success",
        "message": f"Chào mừng trở lại, {user_dict['full_name']}!",
        "access_token": token,
        "token_type": "bearer",
        "user": user_dict,
    }


@router.post("/api/auth/logout")
def logout(response: Response) -> dict[str, Any]:
    """Sign out the current user and delete authentication cookie."""
    response.delete_cookie(key=COOKIE_NAME)
    return {
        "status": "success",
        "message": "Đã đăng xuất thành công.",
    }


@router.get("/api/auth/me")
def get_me(user: Annotated[User, Depends(get_current_user)]) -> dict[str, Any]:
    """Retrieve profile and permissions of the currently authenticated user."""
    return {
        "status": "success",
        "user": _format_user(user),
    }


@router.put("/api/auth/profile")
def update_profile(
    req: UpdateProfileRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Update profile information or password of the currently authenticated user."""
    with get_db_session() as session:
        user_repo = UserRepository(session)
        updated = user_repo.update_profile(
            user_id=current_user.id,
            full_name=req.full_name,
            avatar_url=req.avatar_url,
            new_password=req.new_password,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Người dùng không tồn tại.")
        user_dict = _format_user(updated)

    return {
        "status": "success",
        "message": "Cập nhật thông tin thành công!",
        "user": user_dict,
    }


@router.get("/login", response_class=HTMLResponse)
def serve_login_page() -> HTMLResponse:
    """Serve the authentication web page configured for login."""
    if AUTH_TEMPLATE_PATH.exists():
        content = AUTH_TEMPLATE_PATH.read_text(encoding="utf-8")
        content = content.replace("DATA_DEFAULT_TAB='register'", "DATA_DEFAULT_TAB='login'")
    else:
        content = "<h1>ReviewBot Auth Ready</h1>"
    return HTMLResponse(content=content, status_code=200)


@router.get("/register", response_class=HTMLResponse)
def serve_register_page() -> HTMLResponse:
    """Serve the authentication web page configured for registration."""
    if AUTH_TEMPLATE_PATH.exists():
        content = AUTH_TEMPLATE_PATH.read_text(encoding="utf-8")
        content = content.replace("DATA_DEFAULT_TAB='login'", "DATA_DEFAULT_TAB='register'")
    else:
        content = "<h1>ReviewBot Auth Ready</h1>"
    return HTMLResponse(content=content, status_code=200)
