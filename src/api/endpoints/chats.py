from fastapi import APIRouter, Depends, HTTPException, status, Query
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
    # Собираем ID всех участников (по username)
    participant_ids = []

    # Валидируем и собираем ID участников
    for username in chat_data.participant_usernames:  # <- исправлено
        if username == current_user.username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя добавить самого себя как участника"
            )

        # Находим пользователя по username
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пользователь с username '{username}' не найден"
            )

        # Проверяем, что пользователь активен
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Пользователь '{username}' деактивирован"
            )

        # Добавляем ID пользователя в список
        if user.id not in participant_ids:
            participant_ids.append(user.id)

    if chat_data.type == "private":
        # Для приватного чата должен быть только 1 другой участник
        if len(participant_ids) != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Личный чат может быть только с одним участником"
            )

        # Проверяем, нет ли уже личного чата с этим пользователем
        existing_private_chat = check_existing_private_chat(
            current_user.id,
            participant_ids[0],
            db
        )
        if existing_private_chat:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Личный чат с этим пользователем уже существует"
            )

    elif chat_data.type == "group":
        # Должно быть минимум 2 других участника
        if len(participant_ids) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Групповой чат должен иметь минимум 2 участника"
            )

        # Можно ограничить максимальное количество
        if len(participant_ids) > 49:  # +1 создатель = максимум 50
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Слишком много участников для группового чата"
            )

    elif chat_data.type == "channel":
        # Проверяем, что есть хотя бы 1 участник
        if len(participant_ids) < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Канал должен иметь хотя бы 1 участника"
            )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неизвестный тип чата. Допустимые значения: 'private', 'group', 'channel'"
        )

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
    for user_id in participant_ids:
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
        ChatParticipant.user_id == current_user.id,
        ChatParticipant.is_hidden == False
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
        username: str,
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
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )

    # Проверяем, что пользователь еще не в чате
    existing_participant = db.query(ChatParticipant).filter(
        and_(
            ChatParticipant.chat_id == chat_id,
            ChatParticipant.user_id == user.id
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
        user_id=user.id,
        role="member"
    )
    db.add(participant)
    db.commit()
    db.refresh(participant)

    participant_data = ChatParticipantResponse.from_orm(participant)
    participant_data.username = user.username
    participant_data.email = user.email

    return participant_data


# src/api/endpoints/chats.py
@router.delete("/{chat_id}", response_model=dict)
def delete_chat(
        chat_id: int,
        action: str = Query("auto", description="Что сделать: hide, leave, delete",
                            enum=["hide", "leave", "delete"]),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):

    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")

    participant = db.query(ChatParticipant).filter(
        ChatParticipant.chat_id == chat_id,
        ChatParticipant.user_id == current_user.id
    ).first()

    if not participant:
        raise HTTPException(status_code=403, detail="Вы не состоите в этом чате")

    is_creator = chat.created_by == current_user.id
    is_admin = participant.role == "admin"
    has_delete_rights = is_creator or is_admin

    participants_count = db.query(ChatParticipant).filter(
        ChatParticipant.chat_id == chat_id
    ).count()


    if action == "hide":
        # Скрыть чат - только для личных чатов
        if chat.type != "private" or participants_count != 2:
            raise HTTPException(
                status_code=400,
                detail="Скрыть можно только личные чаты"
            )

        participant.is_hidden = True
        db.commit()

        return {"success": True, "message": "Чат скрыт"}

    elif action == "leave":
        # Выйти из чата
        # Если последний участник - удаляем весь чат
        if participants_count == 1:
            db.delete(chat)  # ПОЛНОЕ УДАЛЕНИЕ
            db.commit()
            return {"success": True, "message": "Вы вышли из чата. Чат удален."}

        # Если не последний - просто удаляем себя из участников
        db.delete(participant)

        # Если уходил админ - назначаем нового
        if participant.role == "admin":
            new_admin = db.query(ChatParticipant).filter(
                ChatParticipant.chat_id == chat_id,
                ChatParticipant.user_id != current_user.id
            ).first()
            if new_admin:
                new_admin.role = "admin"

        db.commit()
        return {"success": True, "message": "Вы вышли из чата"}

    elif action == "delete":
        # Полное удаление чата - только для админов/создателей
        if not has_delete_rights:
            raise HTTPException(
                status_code=403,
                detail="Только администратор или создатель может удалить чат"
            )

        # ПОЛНОЕ УДАЛЕНИЕ из БД
        db.delete(chat)  # Каскадное удаление: сообщения и участники тоже удалятся
        db.commit()

        return {"success": True, "message": "Чат полностью удален"}

    else:
        raise HTTPException(status_code=400, detail="Неизвестное действие")


# Показать скрытые чаты (только свои)
@router.get("/hidden", response_model=List[ChatResponse])
def get_hidden_chats(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):

    hidden_participants = db.query(ChatParticipant).filter(
        ChatParticipant.user_id == current_user.id,
        ChatParticipant.is_hidden == True
    ).all()

    chats = []
    for participant in hidden_participants:
        chat = participant.chat
        chat_dict = ChatResponse.from_orm(chat)
        chat_dict.participant_count = len(chat.participants)
        chats.append(chat_dict)

    return chats


# Показать скрытый чат (восстановить видимость)
@router.post("/{chat_id}/unhide", response_model=dict)
def unhide_chat(
        chat_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):

    participant = db.query(ChatParticipant).filter(
        ChatParticipant.chat_id == chat_id,
        ChatParticipant.user_id == current_user.id,
        ChatParticipant.is_hidden == True
    ).first()

    if not participant:
        raise HTTPException(status_code=404, detail="Скрытый чат не найден")

    participant.is_hidden = False
    db.commit()

    return {"success": True, "message": "Чат снова отображается"}

def check_existing_private_chat(user1_id: int, user2_id: int, db: Session):
    """
    Проверяет, существует ли уже личный чат между двумя пользователями
    """
    # Находим все чаты, где оба пользователя являются участниками
    from sqlalchemy import and_, or_

    # Находим ID чатов, где есть user1
    user1_chats = db.query(ChatParticipant.chat_id).filter(
        ChatParticipant.user_id == user1_id
    ).subquery()

    # Находим ID чатов, где есть user2
    user2_chats = db.query(ChatParticipant.chat_id).filter(
        ChatParticipant.user_id == user2_id
    ).subquery()

    # Находим пересечение (чаты, где есть оба)
    common_chats = db.query(Chat).join(
        ChatParticipant, Chat.id == ChatParticipant.chat_id
    ).filter(
        and_(
            Chat.id.in_(user1_chats),
            Chat.id.in_(user2_chats),
            Chat.type == "private"
        )
    ).all()

    return common_chats[0] if common_chats else None