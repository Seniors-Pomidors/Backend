from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
from src.database.connection import get_db
from src.models.user import User
from src.schemas.user import UserCreate, UserLogin, UserResponse, Token
from src.auth.utils import (
    verify_password,
    get_password_hash,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
import uuid

router = APIRouter()


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    # Проверяем, существует ли пользователь с таким email
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким email уже существует"
        )

    if user_data.privacy_mode not in ["standard", "private"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Режим приватности должен быть 'standard' или 'private'"
        )

    # Создаем нового пользователя
    hashed_password = get_password_hash(user_data.password)

    user = User(
        email=user_data.email,
        username=user_data.username,
        password=hashed_password,
        avatar_url=user_data.avatar_url,
        privacy_mode=user_data.privacy_mode
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id
    )


@router.post("/login", response_model=Token)
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_data.email, User.is_active == True).first()

    if not user or not verify_password(user_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль"
        )

    from datetime import datetime
    user.last_seen = datetime.utcnow()

    from src.models.user_status import UserStatus

    user_status = db.query(UserStatus).filter(
        UserStatus.user_id == user.id
    ).first()

    if not user_status:
        user_status = UserStatus(
            user_id=user.id,
            status="online",  # или "away" пока не подключился к WS
            device="web"
        )
        db.add(user_status)
    else:
        user_status.status = "online"
        user_status.last_seen = datetime.utcnow()

    db.commit()

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id
    )