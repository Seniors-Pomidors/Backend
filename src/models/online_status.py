from sqlalchemy import Column, Integer, DateTime, String, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from src.database.connection import Base


class UserOnlineStatus(Base):
    __tablename__ = "user_online_status"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True, nullable=False)
    status = Column(String(20), default="offline")  # online, offline, away
    last_seen = Column(DateTime(timezone=True), server_default=func.now())
    device = Column(String(100), default="web")
    connection_count = Column(Integer, default=0)

    user = relationship("User")