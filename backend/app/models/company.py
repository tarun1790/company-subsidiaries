import uuid
from sqlalchemy import Column, String, DateTime, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base

class Company(Base):
    __tablename__ = "companies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_name = Column(String(255), nullable=False)
    legal_name = Column(String(255), nullable=True)
    cik = Column(String(50), nullable=True)
    ticker = Column(String(50), nullable=True)
    domain = Column(String(255), nullable=True)
    hq_country = Column(String(100), nullable=True)
    metadata_fields = Column(JSON, nullable=True) # Renamed to metadata_fields to avoid conflicting with SQLalchemy Model.metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
