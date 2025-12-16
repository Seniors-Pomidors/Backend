from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class ChatBase(BaseModel):
    name: str
    type: str  # 'private', 'group', 'channel'


class ChatCreate(ChatBase):
    participant_usernames: List[str]


class ChatResponse(ChatBase):
    id: int
    created_by: int
    created_at: datetime
    is_active: bool
    participant_count: Optional[int] = None

    class Config:
        from_attributes = True


class ChatParticipantResponse(BaseModel):
    id: int
    user_id: int
    chat_id: int
    role: str
    joined_at: datetime
    username: Optional[str] = None
    email: Optional[str] = None

    class Config:
        from_attributes = True

class ChatDeleteResponse(BaseModel):
    message: str
    chat_id: int
    deleted_at: datetime

    class Config:
        from_attributes = True


class ChatDeleteResponse(BaseModel):
    success: bool
    message: str
    chat_id: int
    action: str  # 'deleted', 'hidden', 'left', 'archived'
    timestamp: datetime

    class Config:
        from_attributes = True