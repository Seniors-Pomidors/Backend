from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from src.database.connection import Base


class Chat(Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    type = Column(String(50))  # 'private', 'group', 'channel'
    created_by = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)

    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")
    participants = relationship("ChatParticipant", back_populates="chat", cascade="all, delete-orphan")


class ChatParticipant(Base):
    __tablename__ = "chat_participants"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey('chats.id'))
    user_id = Column(Integer, ForeignKey('users.id'))
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    role = Column(String(50), default='member')  # 'admin', 'member'

    chat = relationship("Chat", back_populates="participants")
    user = relationship("User")

    # Уникальный constraint - пользователь может быть в чате только один раз
    __table_args__ = (UniqueConstraint('chat_id', 'user_id', name='unique_chat_user'),)