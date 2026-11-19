"""Auth endpoints — signup, login, me, logout."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional

from app.database import get_db
from app.services.auth_service import register_user, login_user, get_user_from_token, create_token
from app.models.user import User

router = APIRouter()


class SignupRequest(BaseModel):
    email: str
    username: str
    password: str
    full_name: str = ""

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v

    @field_validator("username")
    @classmethod
    def username_valid(cls, v):
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Username must be at least 2 characters")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str


def _user_dict(user: User, token: str = "") -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "token": token,
    }


def _get_token(authorization: Optional[str] = Header(None)) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split(" ")
    return parts[1] if len(parts) == 2 and parts[0].lower() == "bearer" else None


@router.post("/auth/signup", status_code=201)
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    try:
        user = register_user(db, body.email, body.username, body.password, body.full_name)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    token = create_token(user.id, user.email, user.username)
    return _user_dict(user, token)


@router.post("/auth/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = login_user(db, body.email, body.password)
    if not user:
        raise HTTPException(401, "Invalid email or password")
    token = create_token(user.id, user.email, user.username)
    return _user_dict(user, token)


@router.get("/auth/me")
def me(token: Optional[str] = Depends(_get_token), db: Session = Depends(get_db)):
    if not token:
        raise HTTPException(401, "Not authenticated")
    user = get_user_from_token(db, token)
    if not user:
        raise HTTPException(401, "Token invalid or expired")
    return _user_dict(user)


@router.post("/auth/logout")
def logout():
    # JWT is stateless; client just drops the token
    return {"success": True, "message": "Logged out"}
