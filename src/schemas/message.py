from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class MessageBase(BaseModel):
    content: str
    message_type: str = 'text'


class MessageCreate(MessageBase):
    chat_id: int


class MessageResponse(MessageBase):
    id: int
    chat_id: int
    user_id: int
    created_at: datetime
    username: Optional[str] = None

    class Config:
        from_attributes = True