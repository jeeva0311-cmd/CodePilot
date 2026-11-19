"""Settings ORM model — key/value store."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime
from app.database.database import Base


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(256), primary_key=True)
    value = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
