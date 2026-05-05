from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, Index
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class FileMetadata(Base):
    """SQLAlchemy model for storing file metadata in PostgreSQL"""

    __tablename__ = "file_metadata"

    # Primary key - file identifier
    file_id = Column(String(255), primary_key=True, nullable=False, index=True)

    # User identifier for access control
    user_id = Column(String(255), nullable=True, index=True)

    # File metadata as JSON (flexible schema)
    metadata = Column(JSON, nullable=False, default={})

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Indexes for performance
    __table_args__ = (
        Index('idx_user_id_file_id', 'user_id', 'file_id'),
        Index('idx_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<FileMetadata(file_id={self.file_id}, user_id={self.user_id})>"

    def to_dict(self) -> dict:
        """Convert model to dictionary"""
        result = self.metadata.copy() if self.metadata else {}
        result['file_id'] = self.file_id
        if self.user_id:
            result['user_id'] = self.user_id
        result['created_at'] = self.created_at.isoformat()
        result['updated_at'] = self.updated_at.isoformat()
        return result
