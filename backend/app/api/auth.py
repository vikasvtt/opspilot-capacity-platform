import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.dependencies import current_user, get_db
from app.core.security import create_token_pair, decode_token, hash_password, verify_password
from app.models.entities import User, UserRole
from app.schemas.auth import LoginInput, RefreshInput, RegisterInput, TokenPair, UserOutput
from app.services.audit import write_audit

router = APIRouter(prefix="/auth", tags=["authentication"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/register", response_model=UserOutput, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterInput, db: Session = Depends(get_db)):
    email = str(payload.email).lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(email=email, password_hash=hash_password(payload.password), role=UserRole.VIEWER)
    db.add(user)
    db.flush()
    write_audit(db, email, "auth.registered", "user", user.id, {})
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenPair)
@limiter.limit("5/minute")
def login(request: Request, payload: LoginInput, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    return create_token_pair(user.id, user.role.value)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshInput, db: Session = Depends(get_db)):
    try:
        claims = decode_token(payload.refresh_token, "refresh")
        user = db.get(User, int(claims["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        user = None
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired credentials")
    return create_token_pair(user.id, user.role.value)


@router.get("/me", response_model=UserOutput)
def me(user: User = Depends(current_user)):
    return user
