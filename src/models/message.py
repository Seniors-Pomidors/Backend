from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey
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

    chat = relationship("Chat", back_populates="messages")
    user = relationship("User")