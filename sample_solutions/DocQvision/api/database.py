"""
Database configuration and session management.

This module sets up SQLAlchemy engine, session factory, and base class
for all database models. Provides dependency injection for FastAPI endpoints.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import config

# Database URL from configuration
DATABASE_URL = getattr(config, 'DATABASE_URL', 'sqlite:///./DocQvision.db')

# Create SQLAlchemy engine
# connect_args for SQLite only - allows multi-threaded access
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
    echo=False
)

# Session factory for creating database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all ORM models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function for FastAPI endpoints to get database session.

    Yields database session and ensures proper cleanup after request completion.

    Yields:
        Session: SQLAlchemy database session

    Example:
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize database by creating all tables.

    Should be called on application startup to ensure database schema exists.
    """
    Base.metadata.create_all(bind=engine)
