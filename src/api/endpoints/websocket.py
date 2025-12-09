from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.orm import Session
import json
from datetime import datetime
from typing import Optional

from src.database.connection import get_db
from src.api.websocket_manager import manager
from src.models.user import User
from src.models.message import Message as MessageModel
from src.models.online_status import UserOnlineStatus
from src.schemas.message import MessageCreate
from src.auth.utils import verify_token

router = APIRouter()


async def get_current_user_ws(websocket: WebSocket) -> Optional[int]:
    try:
        # Получаем токен из query параметров
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=1008)
            return None

        # Верифицируем токен
        payload = verify_token(token)
        if not payload:
            await websocket.close(code=1008)
            return None

        user_id = int(payload.get("sub"))
        if not user_id:
            await websocket.close(code=1008)
            return None

        return user_id

    except Exception as e:
        print(f"WebSocket auth error: {e}")
        await websocket.close(code=1011)
        return None


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Аутентификация через query параметр ?token=...
    user_id = await get_current_user_ws(websocket)
    if not user_id:
        return

    # Подключаем пользователя
    await manager.connect(websocket, user_id)

    try:
        # Отправляем подтверждение подключения
        await websocket.send_json({
            "type": "connection_established",
            "message": f"Connected as user {user_id}",
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Главный цикл получения сообщений
        while True:
            # Ждем данные от клиента
            data = await websocket.receive_json()

            # Обрабатываем тип сообщения
            message_type = data.get("type")

            if message_type == "message":
                await handle_message(data, user_id, websocket)

            elif message_type == "typing":
                await handle_typing(data, user_id)

            elif message_type == "read_receipt":
                await handle_read_receipt(data, user_id)

            elif message_type == "ping":
                # Ответ на пинг для поддержания соединения
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })

    except WebSocketDisconnect:
        print(f"WebSocket disconnected for user {user_id}")
        manager.disconnect(websocket, user_id)
        await update_user_status(user_id, "offline")

    except Exception as e:
        print(f"WebSocket error for user {user_id}: {e}")
        manager.disconnect(websocket, user_id)
        await update_user_status(user_id, "offline")


async def handle_message(data: dict, user_id: int, websocket: WebSocket):
    """Обработка нового сообщения"""
    from src.database.connection import SessionLocal

    db = SessionLocal()
    try:
        # Проверяем, что пользователь участник чата
        from src.models.chat import ChatParticipant

        participant = db.query(ChatParticipant).filter(
            ChatParticipant.chat_id == data["chat_id"],
            ChatParticipant.user_id == user_id
        ).first()

        if not participant:
            await websocket.send_json({
                "type": "error",
                "message": "Не состоите в этом чате"
            })
            return

        # Сохраняем сообщение в БД
        message = MessageModel(
            chat_id=data["chat_id"],
            user_id=user_id,
            content=data["content"],
            message_type=data.get("message_type", "text")
        )

        db.add(message)
        db.commit()
        db.refresh(message)

        # Получаем информацию об авторе
        from src.models.user import User
        user = db.query(User).filter(User.id == user_id).first()

        # Формируем ответ
        message_response = {
            "type": "new_message",
            "data": {
                "id": message.id,
                "chat_id": message.chat_id,
                "user_id": message.user_id,
                "username": user.username,
                "content": message.content,
                "message_type": message.message_type,
                "created_at": message.created_at.isoformat()
            }
        }

        # Отправляем всем участникам чата
        await manager.broadcast_to_chat(
            message_response,
            data["chat_id"],
            exclude_user_id=user_id  # не отправляем отправителю
        )

    finally:
        db.close()


async def handle_typing(data: dict, user_id: int):
    """Обработка индикатора набора текста"""
    typing_event = {
        "type": "user_typing",
        "data": {
            "user_id": user_id,
            "chat_id": data["chat_id"],
            "is_typing": data["is_typing"]
        }
    }

    await manager.broadcast_to_chat(
        typing_event,
        data["chat_id"],
        exclude_user_id=user_id
    )


async def handle_read_receipt(data: dict, user_id: int):
    """Обработка подтверждения прочтения"""
    from src.database.connection import SessionLocal

    db = SessionLocal()
    try:
        pass
    finally:
        db.close()

    # Рассылаем уведомление о прочтении
    receipt_event = {
        "type": "message_read",
        "data": {
            "user_id": user_id,
            "message_id": data["message_id"],
            "chat_id": data["chat_id"]
        }
    }

    await manager.broadcast_to_chat(
        receipt_event,
        data["chat_id"],
        exclude_user_id=user_id
    )


async def update_user_status(user_id: int, status: str):
    """Обновление статуса пользователя"""
    from src.database.connection import SessionLocal

    db = SessionLocal()
    try:
        online_status = db.query(UserOnlineStatus).filter(
            UserOnlineStatus.user_id == user_id
        ).first()

        if not online_status:
            online_status = UserOnlineStatus(user_id=user_id, status=status)
            db.add(online_status)
        else:
            online_status.status = status
            online_status.last_seen = datetime.utcnow()

        db.commit()

    finally:
        db.close()