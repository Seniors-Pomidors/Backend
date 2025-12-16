from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.orm import Session
import json
from datetime import datetime
from typing import Optional

from src.database.connection import get_db
from src.api.websocket_manager import manager
from src.models.user import User
from src.models.message import Message as MessageModel
from src.models.user_status import UserStatus
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

    await update_user_status(user_id, "online")

    try:
        # Отправляем подтверждение подключения
        await websocket.send_json({
            "type": "connection_established",
            "message": f"Connected as user {user_id}",
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        })

        from src.database.connection import SessionLocal
        db = SessionLocal()

        # Главный цикл получения сообщений
        while True:
            # Ждем данные от клиента
            data = await websocket.receive_json()

            # Обрабатываем тип сообщения
            message_type = data.get("type")

            if message_type == "ping":
                # Ответ на пинг для поддержания соединения
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })
            elif message_type == "chat_message":
                # Получили новое сообщение от клиента
                await handle_chat_message(data, user_id, db)

            elif message_type == "subscribe_to_chat":
                # Подписка на уведомления чата
                chat_id = data.get("chat_id")
                await manager.subscribe_to_chat(user_id, chat_id)

    except WebSocketDisconnect:
        print(f"WebSocket disconnected for user {user_id}")
        manager.disconnect(websocket, user_id)
        await update_user_status(user_id, "offline")

    except Exception as e:
        print(f"WebSocket error for user {user_id}: {e}")
        manager.disconnect(websocket, user_id)
        await update_user_status(user_id, "offline")


async def update_user_status(user_id: int, status: str):
    from src.database.connection import SessionLocal

    db = SessionLocal()
    try:
        user_status = db.query(UserStatus).filter(
            UserStatus.user_id == user_id
        ).first()

        if not user_status:
            user_status = UserStatus(
                user_id=user_id,
                status=status,
                device="web"
            )
            db.add(user_status)
        else:
            user_status.status = status
            user_status.last_seen = datetime.utcnow()
        db.commit()
    except Exception as e:
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


async def handle_chat_message(data: dict, sender_id: int, db: Session):
    from src.models.message import Message
    from src.api.websocket_manager import manager

    message = Message(
        chat_id=data["chat_id"],
        user_id=sender_id,
        content=data["content"],
        message_type=data.get("message_type", "text")
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    await manager.broadcast_to_chat({
        "type": "new_message",
        "message": {
            "id": message.id,
            "chat_id": message.chat_id,
            "user_id": sender_id,
            "content": message.content,
            "created_at": message.created_at.isoformat()
        }
    }, message.chat_id, exclude_user_id=sender_id)