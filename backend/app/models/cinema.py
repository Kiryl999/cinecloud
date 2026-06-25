from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from backend.app.core.database import Base

class Cinema(Base):
    __tablename__ = "cinemas"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())