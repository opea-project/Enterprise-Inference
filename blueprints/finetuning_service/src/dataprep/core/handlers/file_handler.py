import os
import uuid
from datetime import datetime
from fastapi import UploadFile
from sqlalchemy.orm import Session
from core.config import settings
from core.handlers.metadata_handler import MetadataHandler
from core.handlers.storage_handler import StorageHandler


class FileHandler:
    """Handles file upload, download, and deletion operations using MinIO storage"""

    def __init__(self):
        self.storage = StorageHandler()

    def generate_file_id(self) -> str:
        """Generate a unique file ID"""
        return f"file-{uuid.uuid4().hex}"

    async def save_file(self, file: UploadFile, db: Session, purpose: str = "assistants", user_id: str = None) -> dict:
        """
        Save an uploaded file to MinIO storage and create metadata

        Args:
            file: The uploaded file
            db: SQLAlchemy session for metadata operations
            purpose: Purpose of the file
            user_id: User identifier to associate with the file

        Returns:
            File metadata dictionary
        """
        # Generate unique file ID
        file_id = self.generate_file_id()

        # Read file content
        file_content = await file.read()
        file_size = len(file_content)

        # Upload to MinIO
        from io import BytesIO
        file_stream = BytesIO(file_content)

        object_name = f"{user_id}/{file_id}"
        success = self.storage.upload_file(
            file_id=object_name,
            file_data=file_stream,
            file_size=file_size,
            content_type=file.content_type or "application/octet-stream"
        )

        if not success:
            raise Exception("Failed to upload file to storage")

        # Create metadata
        file_metadata = {
            "id": file_id,
            "object": "file",
            "bytes": file_size,
            "created_at": int(datetime.now().timestamp()),
            "filename": file.filename,
            "purpose": purpose,
            "status": "processed",
            "status_details": None,
            "user_id": user_id
        }

        # Save metadata using the passed session
        metadata_handler = MetadataHandler(db)
        metadata_handler.add(file_id, file_metadata, user_id)

        return file_metadata

    def get_file_stream(self, file_id: str, user_id: str = None):
        """
        Get a streaming file-like object from MinIO storage
        Args:
            file_id: ID of the file
            user_id: User identifier for access control
        Returns:
            File-like object for streaming, or None if error
        """
        object_name = f"{user_id}/{file_id}"
        return self.storage.get_file_stream(object_name)

    def delete_file(self, file_id: str, db: Session, user_id: str = None) -> bool:
        """
        Delete a file from MinIO storage and remove metadata

        Args:
            file_id: ID of the file to delete
            db: SQLAlchemy session for metadata operations
            user_id: User identifier for access control
        Returns:
            True if deleted successfully
        """
        object_name = f"{user_id}/{file_id}"
        self.storage.delete_file(object_name)
        metadata_handler = MetadataHandler(db)
        return metadata_handler.delete(file_id, user_id)

    def file_exists(self, file_id: str, user_id: str = None) -> bool:
        """
        Check if a file exists in MinIO storage for a user
        Args:
            file_id: ID of the file
            user_id: User identifier for access control
        Returns:
            True if file exists
        """
        object_name = f"{user_id}/{file_id}"
        return self.storage.file_exists(object_name)

    def get_presigned_url(self, file_id: str, user_id: str = None, method: str = "GET", expires_seconds: int = 3600) -> str:
        """
        Generate a presigned URL for file access for a user
        Args:
            file_id: ID of the file
            user_id: User identifier for access control
            method: HTTP method
            expires_seconds: Expiry time in seconds
        Returns:
            Presigned URL string
        """
        object_name = f"{user_id}/{file_id}"
        return self.storage.get_presigned_url(object_name, method, expires_seconds)

    def get_file_stat(self, file_id: str, user_id: str = None) -> dict:
        """
        Get file statistics from MinIO for a user
        Args:
            file_id: ID of the file
            user_id: User identifier for access control
        Returns:
            Dictionary with file metadata
        """
        object_name = f"{user_id}/{file_id}"
        return self.storage.get_file_stat(object_name)
