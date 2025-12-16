from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey, JSON, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from src.database.connection import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey('chats.id'))
    user_id = Column(Integer, ForeignKey('users.id'))
    content = Column(Text)
    message_type = Column(String(50), default='text')  # 'text', 'image', 'file', 'system'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    read_by = Column(JSON, default=list)  # список user_id, прочитавших сообщение
    edited = Column(Boolean, default=False)
    reply_to = Column(Integer, nullable=True)

    chat = relationship("Chat", back_populates="messages")
    user = relationship("User")