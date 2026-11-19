"""
Authentication service — password hashing, JWT creation/validation.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User

logger = logging.getLogger("codepilot.auth")

_ALGORITHM = "HS256"


# ── Password helpers ──────────────────────────────────────────────────────────
def hash_password(plain: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain.encode(), salt).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ── JWT helpers ───────────────────────────────────────────────────────────────
def create_token(user_id: str, email: str, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "email": email,
        "username": username,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        logger.warning("JWT expired")
        return None
    except jwt.InvalidTokenError as exc:
        logger.warning(f"Invalid JWT: {exc}")
        return None


# ── User operations ───────────────────────────────────────────────────────────
def register_user(db: Session, email: str, username: str, password: str, full_name: str = "") -> User:
    if db.query(User).filter(User.email == email).first():
        raise ValueError("Email already registered")
    if db.query(User).filter(User.username == username).first():
        raise ValueError("Username already taken")
    user = User(
        email=email.lower().strip(),
        username=username.strip(),
        hashed_password=hash_password(password),
        full_name=full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login_user(db: Session, email: str, password: str) -> Optional[User]:
    user = db.query(User).filter(User.email == email.lower().strip()).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    user.last_login = datetime.utcnow()
    db.commit()
    return user


def get_user_from_token(db: Session, token: str) -> Optional[User]:
    payload = decode_token(token)
    if not payload:
        return None
    return db.query(User).filter(User.id == payload["sub"]).first()
