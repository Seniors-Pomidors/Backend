from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List

from src.database.connection import get_db
from src.auth.dependencies import get_current_user
from src.models.user import User
from src.models.chat import Chat, ChatParticipant
from src.models.message import Message
from src.schemas.message import MessageCreate, MessageResponse

router = APIRouter(prefix="/chats", tags=["messages"])


# Отправить сообщение в чат
@router.post("/{chat_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def send_message(
        chat_id: int,
        message_data: MessageCreate,
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
            detail="Нельзя отправлять сообщения в этот чат"
        )

    # Создаем сообщение
    message = Message(
        chat_id=chat_id,
        user_id=current_user.id,
        content=message_data.content,
        message_type=message_data.message_type
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    # Добавляем username для ответа
    message_response = MessageResponse.from_orm(message)
    message_response.username = current_user.username

    return message_response


# Получить сообщения чата
@router.get("/{chat_id}/messages", response_model=List[MessageResponse])
def get_chat_messages(
        chat_id: int,
        limit: int = 100,
        offset: int = 0,
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
            detail="Доступ к сообщениям запрещен"
        )

    # Получаем сообщения с информацией о пользователях
    messages = db.query(Message).join(User).filter(
        Message.chat_id == chat_id
    ).order_by(Message.created_at.desc()).offset(offset).limit(limit).all()

    result = []
    for message in messages:
        message_data = MessageResponse.from_orm(message)
        message_data.username = message.user.username
        result.append(message_data)

    return result


# Получить конкретное сообщение
@router.get("/{chat_id}/messages/{message_id}", response_model=MessageResponse)
def get_message(
        chat_id: int,
        message_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # Проверяем доступ к чату
    participant = db.query(ChatParticipant).filter(
        and_(
            ChatParticipant.chat_id == chat_id,
            ChatParticipant.user_id == current_user.id
        )
    ).first()

    if not participant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ к сообщению запрещен"
        )

    message = db.query(Message).filter(
        and_(
            Message.id == message_id,
            Message.chat_id == chat_id
        )
    ).first()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Сообщение не найдено"
        )

    message_response = MessageResponse.from_orm(message)
    message_response.username = message.user.username

    return message_response


# Удалить сообщение
@router.delete("/{chat_id}/messages/{message_id}")
def delete_message(
        chat_id: int,
        message_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # Проверяем доступ к чату
    participant = db.query(ChatParticipant).filter(
        and_(
            ChatParticipant.chat_id == chat_id,
            ChatParticipant.user_id == current_user.id
        )
    ).first()

    if not participant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещен"
        )

    message = db.query(Message).filter(
        and_(
            Message.id == message_id,
            Message.chat_id == chat_id
        )
    ).first()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Сообщение не найдено"
        )

    # Проверяем, что пользователь автор сообщения или админ
    if message.user_id != current_user.id and participant.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Можно удалять только свои сообщения"
        )

    db.delete(message)
    db.commit()

    return {"message": "Сообщение удалено"}