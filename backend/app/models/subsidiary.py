import uuid
from sqlalchemy import Column, String, Float, ForeignKey, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Subsidiary(Base):
    __tablename__ = "subsidiaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    legal_name = Column(String(255), nullable=True)
    country = Column(String(100), nullable=True)
    ownership = Column(String(100), nullable=True)
    parent = Column(String(255), nullable=True)
    relationship_type = Column(String(100), nullable=True) # "Subsidiary", "Holding Company", "Division", "Brand", etc.
    registration_number = Column(String(100), nullable=True)
    confidence = Column(Float, default=0.0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    evidences = relationship("Evidence", back_populates="subsidiary", cascade="all, delete-orphan", lazy="selectin")

class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subsidiary_id = Column(UUID(as_uuid=True), ForeignKey("subsidiaries.id", ondelete="CASCADE"), nullable=False)
    source_type = Column(String(100), nullable=False) # "SEC Filings", "Official Website", "Public Registry", "Wikipedia", "Web Research"
    source_url = Column(Text, nullable=True)
    extracted_text = Column(Text, nullable=True)
    verified_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    subsidiary = relationship("Subsidiary", back_populates="evidences")
