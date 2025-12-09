from fastapi import WebSocket
from typing import Dict, List
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}
        self.chat_subscriptions: Dict[int, List[int]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        print(f"User {user_id} connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        print(f"User {user_id} disconnected. Remaining connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict, user_id: int):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    print(f"Error sending to user {user_id}: {e}")

    async def broadcast_to_chat(self, message: dict, chat_id: int, exclude_user_id: int = None):
        from src.database.connection import SessionLocal
        from src.models.chat import ChatParticipant

        db = SessionLocal()
        try:
            participants = db.query(ChatParticipant).filter(
                ChatParticipant.chat_id == chat_id
            ).all()

            for participant in participants:
                user_id = participant.user_id
                if exclude_user_id and user_id == exclude_user_id:
                    continue

                if user_id in self.active_connections:
                    for connection in self.active_connections[user_id]:
                        try:
                            await connection.send_json(message)
                        except Exception as e:
                            print(f"Error sending to user {user_id}: {e}")
        finally:
            db.close()


manager = ConnectionManager()