"""Database initialization utilities"""
import logging
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.config.database import engine, init_db, create_database_if_not_exists, SessionLocal
from core.schemas.database_models import Base, FileMetadata

logger = logging.getLogger(__name__)


def init_database():
    """
    Initialize database and tables at application startup.
    Steps:
    1. Create database if it doesn't exist
    2. Create all tables defined in SQLAlchemy models
    """
    try:
        logger.info("Checking/creating PostgreSQL database...")
        create_database_if_not_exists()

        logger.info("Initializing database tables...")
        init_db()
        logger.info("Database tables initialized successfully")
    except SQLAlchemyError as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during database initialization: {e}")
        raise


def check_database_connection():
    """
    Check if database connection is working.

    Returns:
        bool: True if connection is successful, False otherwise
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        logger.info("Database connection successful")
        return True
    except SQLAlchemyError as e:
        logger.error(f"Failed to connect to database: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error checking database connection: {e}")
        return False


def get_file_metadata(file_id: str, user_id: str) -> dict:
    """
    Get file metadata from PostgreSQL database.

    Args:
        file_id: File identifier
        user_id: User identifier

    Returns:
        Dictionary with file metadata including filename and extension,
        or None if not found.
    """
    with SessionLocal() as db:
        file_metadata = db.query(FileMetadata).filter(
            FileMetadata.file_id == file_id,
            FileMetadata.user_id == user_id,
        ).first()

        if file_metadata:
            return file_metadata.to_dict()
        return None


def get_filename_with_extension(file_id: str, user_id: str) -> tuple:
    """
    Get original filename and extension from PostgreSQL.

    Args:
        file_id: File identifier
        user_id: User identifier

    Returns:
        Tuple of (filename, extension) or (None, None) if not found
    """
    metadata = get_file_metadata(file_id, user_id)

    if not metadata:
        return None, None

    # Extract filename from metadata
    filename = metadata.get('filename', file_id)

    # Extract extension
    if '.' in filename:
        name, ext = filename.rsplit('.', 1)
        return name, ext

    return filename, None
