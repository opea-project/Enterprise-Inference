"""Metadata handler for file metadata operations using PostgreSQL"""
import logging
from typing import Dict, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from core.config.database import SessionLocal
from core.schemas.database_models import FileMetadata

logger = logging.getLogger(__name__)


class MetadataHandler:
    """Handles file metadata operations using PostgreSQL database"""

    def __init__(self, db: Session):
        """
        Initialize metadata handler.

        Args:
            db: SQLAlchemy session (Required - managed by caller, typically FastAPI dependency)
        """
        if db is None:
            raise ValueError("MetadataHandler requires a valid SQLAlchemy Session instance")
        self.db = db
        self._own_session = False  # Session lifecycle is managed by the caller

    def get(self, file_id: str, user_id: Optional[str] = None) -> Optional[Dict]:
        """
        Get metadata for a specific file.

        Args:
            file_id: File identifier
            user_id: User identifier for access control (optional)

        Returns:
            File metadata dictionary if found and user has access, None otherwise
        """
        try:
            query = self.db.query(FileMetadata).filter(FileMetadata.file_id == file_id)

            # Check user access if user_id is provided
            if user_id:
                query = query.filter(FileMetadata.user_id == user_id)

            file_metadata = query.first()

            if file_metadata:
                return file_metadata.to_dict()
            return None
        except SQLAlchemyError as e:
            logger.exception("Database error while getting metadata for %s", file_id)
            return None

    def add(self, file_id: str, file_metadata: Dict, user_id: Optional[str] = None) -> bool:
        """
        Add metadata for a new file.

        Args:
            file_id: File identifier
            file_metadata: File metadata dictionary
            user_id: User identifier to associate with the file (optional)

        Returns:
            True if added successfully, False otherwise
        """
        try:
            # Check if file already exists
            existing = self.db.query(FileMetadata).filter(
                FileMetadata.file_id == file_id
            ).first()

            if existing:
                # Update existing record
                existing.file_data = file_metadata
                existing.updated_at = datetime.utcnow()
                if user_id:
                    existing.user_id = user_id
                self.db.commit()
                return True

            # Create new record
            new_metadata = FileMetadata(
                file_id=file_id,
                user_id=user_id,
                file_data=file_metadata
            )
            self.db.add(new_metadata)
            self.db.commit()
            return True
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.exception("Database error while adding metadata for %s", file_id)
            return False

    def delete(self, file_id: str, user_id: Optional[str] = None) -> bool:
        """
        Delete metadata for a file.

        Args:
            file_id: File identifier
            user_id: User identifier for access control (optional)

        Returns:
            True if deleted successfully, False if not found or access denied
        """
        try:
            query = self.db.query(FileMetadata).filter(FileMetadata.file_id == file_id)

            # Check user access if user_id is provided
            if user_id:
                query = query.filter(FileMetadata.user_id == user_id)

            file_metadata = query.first()

            if file_metadata:
                self.db.delete(file_metadata)
                self.db.commit()
                return True
            return False
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.exception("Database error while deleting metadata for %s", file_id)
            return False

    def list_all(self, purpose: Optional[str] = None, user_id: Optional[str] = None) -> List[Dict]:
        """
        List all files, optionally filtered by purpose and user.

        Args:
            purpose: Filter by file purpose (optional)
            user_id: Filter by user identifier (optional)

        Returns:
            List of file metadata dictionaries
        """
        try:
            query = self.db.query(FileMetadata)

            # Filter by user_id if provided
            if user_id:
                query = query.filter(FileMetadata.user_id == user_id)

            # Exclude intermediate processing files at the database level
            # to avoid fetching unnecessary rows into Python memory.
            query = query.filter(
                FileMetadata.file_data["purpose"].as_string() != "intermediate_processing"
            )

            files = query.all()

            # Remaining filters that require Python-level logic
            # (e.g. filename-pattern inspection) are applied here.
            filtered_files = []
            for f in files:
                file_dict = f.to_dict()
                file_purpose = file_dict.get("purpose", "")

                # Skip non-aggregated training data JSONL files
                if file_purpose == "training_data":
                    filename = file_dict.get("filename", "")
                    if filename.endswith(".jsonl") and "aggregated" not in filename.lower():
                        continue

                # If a purpose filter is specified, only include matching files
                if purpose and file_purpose != purpose:
                    continue

                filtered_files.append(file_dict)

            return filtered_files
        except SQLAlchemyError as e:
            logger.exception("Database error while listing metadata")
            return []

    def update(self, file_id: str, file_metadata: Dict, user_id: Optional[str] = None) -> bool:
        """
        Update metadata for an existing file.

        Args:
            file_id: File identifier
            file_metadata: Updated file metadata dictionary
            user_id: User identifier for access control (optional)

        Returns:
            True if updated successfully, False if not found or access denied
        """
        return self.add(file_id, file_metadata, user_id)

    def load(self) -> Dict:
        """
        Load all metadata as a dictionary (for backwards compatibility).

        Returns:
            Dictionary with file_id as keys and metadata as values
        """
        try:
            files = self.db.query(FileMetadata).all()
            result = {}
            for f in files:
                result[f.file_id] = f.to_dict()
            return result
        except SQLAlchemyError as e:
            logger.exception("Database error while loading all metadata")
            return {}

    def save(self, metadata: Dict) -> bool:
        """
        Save metadata dictionary (for backwards compatibility with file-based approach).

        Args:
            metadata: Dictionary with file_id as keys and metadata as values

        Returns:
            True if all records saved successfully, False otherwise
        """
        try:
            for file_id, file_data in metadata.items():
                user_id = file_data.pop("user_id", None)
                self.add(file_id, file_data, user_id)
            return True
        except Exception as e:
            logger.exception("Error saving metadata")
            return False
