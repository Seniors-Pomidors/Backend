from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional

from src.database.connection import get_db
from src.auth.dependencies import get_current_user
from src.models.user import User
from src.models.chat import Chat, ChatParticipant
from src.models.message import Message
from src.schemas.chat import ChatCreate, ChatResponse, ChatParticipantResponse
from src.schemas.message import MessageCreate, MessageResponse

router = APIRouter(prefix="/chats", tags=["chats"])


# Создать новый чат
@router.post("/", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
def create_chat(
        chat_data: ChatCreate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # Создаем чат
    chat = Chat(
        name=chat_data.name,
        type=chat_data.type,
        created_by=current_user.id
    )
    db.add(chat)
    db.commit()
    db.refresh(chat)

    # Добавляем создателя как администратора
    creator_participant = ChatParticipant(
        chat_id=chat.id,
        user_id=current_user.id,
        role="admin"
    )
    db.add(creator_participant)

    # Добавляем остальных участников
    for user_id in chat_data.participant_ids:
        if user_id != current_user.id:  # Не дублируем создателя
            participant = ChatParticipant(
                chat_id=chat.id,
                user_id=user_id,
                role="member"
            )
            db.add(participant)

    db.commit()
    return chat


# Получить все чаты пользователя
@router.get("/", response_model=List[ChatResponse])
def get_my_chats(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # Находим все чаты, где пользователь является участником
    participants = db.query(ChatParticipant).filter(
        ChatParticipant.user_id == current_user.id
    ).all()

    chats = []
    for participant in participants:
        chat = participant.chat
        # Добавляем количество участников
        chat_dict = ChatResponse.from_orm(chat)
        chat_dict.participant_count = len(chat.participants)
        chats.append(chat_dict)

    return chats


# Получить информацию о конкретном чате
@router.get("/{chat_id}", response_model=ChatResponse)
def get_chat(
        chat_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # Проверяем, что пользователь участник чата
    participant = db.query(ChatParticipant).filter(
        and_(
            ChatParticipant.chat_id == chat_id,
            ChatParticipant.user_id == current_user.id
        )
    ).first()

    if not participant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ к чату запрещен"
        )

    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Чат не найден"
        )

    chat_response = ChatResponse.from_orm(chat)
    chat_response.participant_count = len(chat.participants)
    return chat_response


# Получить участников чата
@router.get("/{chat_id}/participants", response_model=List[ChatParticipantResponse])
def get_chat_participants(
        chat_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # Проверяем доступ
    participant = db.query(ChatParticipant).filter(
        and_(
            ChatParticipant.chat_id == chat_id,
            ChatParticipant.user_id == current_user.id
        )
    ).first()

    if not participant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ к чату запрещен"
        )

    participants = db.query(ChatParticipant).filter(
        ChatParticipant.chat_id == chat_id
    ).all()

    # Добавляем информацию о пользователях
    result = []
    for participant in participants:
        participant_data = ChatParticipantResponse.from_orm(participant)
        participant_data.username = participant.user.username
        participant_data.email = participant.user.email
        result.append(participant_data)

    return result


# Добавить участника в чат
@router.post("/{chat_id}/participants", response_model=ChatParticipantResponse)
def add_participant(
        chat_id: int,
        user_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # Проверяем, что текущий пользователь - админ чата
    admin_participant = db.query(ChatParticipant).filter(
        and_(
            ChatParticipant.chat_id == chat_id,
            ChatParticipant.user_id == current_user.id,
            ChatParticipant.role == "admin"
        )
    ).first()

    if not admin_participant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администратор может добавлять участников"
        )

    # Проверяем, что пользователь существует
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )

    # Проверяем, что пользователь еще не в чате
    existing_participant = db.query(ChatParticipant).filter(
        and_(
            ChatParticipant.chat_id == chat_id,
            ChatParticipant.user_id == user_id
        )
    ).first()

    if existing_participant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь уже в чате"
        )

    # Добавляем участника
    participant = ChatParticipant(
        chat_id=chat_id,
        user_id=user_id,
        role="member"
    )
    db.add(participant)
    db.commit()
    db.refresh(participant)

    participant_data = ChatParticipantResponse.from_orm(participant)
    participant_data.username = user.username
    participant_data.email = user.email

    return participant_data