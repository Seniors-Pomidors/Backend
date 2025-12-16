from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


class WsMessage(BaseModel):
    type: str  # message, typing, read_receipt, user_status, notification
    data: dict

    class Config:
        from_attributes = True


class WsChatMessage(BaseModel):
    chat_id: int
    content: str
    message_type: str = "text"
    reply_to: Optional[int] = None

    class Config:
        from_attributes = True


class WsTypingEvent(BaseModel):
    chat_id: int
    is_typing: bool

    class Config:
        from_attributes = True


class WsReadReceipt(BaseModel):
    message_id: int
    chat_id: int

    class Config:
        from_attributes = True


class WsUserStatus(BaseModel):
    user_id: int
    status: str  # online, offline, away
    last_seen: Optional[datetime] = None

    class Config:
        from_attributes = True