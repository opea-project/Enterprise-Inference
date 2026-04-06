"""Database configuration and session management"""
import os
import re
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError

from core.schemas.database_models import Base


class DatabaseConfig:
    """PostgreSQL database configuration"""
    
    def __init__(self):
        """Initialize database configuration"""
        # PostgreSQL connection parameters
        self.DB_HOST = os.getenv("DB_HOST") or self._raise_error("DB_HOST")
        self.DB_PORT = int(os.getenv("DB_PORT") or self._raise_error("DB_PORT"))
        self.DB_NAME = os.getenv("DB_NAME") or self._raise_error("DB_NAME")
        self.DB_USER = os.getenv("DB_USER") or self._raise_error("DB_USER")
        self.DB_PASSWORD = os.getenv("DB_PASSWORD") or self._raise_error("DB_PASSWORD")
        
        # Connection pool settings
        self.POOL_SIZE = int(os.getenv("DB_POOL_SIZE") or self._raise_error("DB_POOL_SIZE"))
        self.MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW") or self._raise_error("DB_MAX_OVERFLOW"))
        self.POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE") or self._raise_error("DB_POOL_RECYCLE"))
    
    @staticmethod
    def _raise_error(var_name: str):
        """Raise error for missing environment variable"""
        raise ValueError(f"Environment variable '{var_name}' is not set")
    
    @property
    def DATABASE_URL(self) -> str:
        """Generate PostgreSQL connection URL"""
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    @property
    def engine(self):
        """Create SQLAlchemy engine with connection pooling"""
        return create_engine(
            self.DATABASE_URL,
            poolclass=QueuePool,
            pool_size=self.POOL_SIZE,
            max_overflow=self.MAX_OVERFLOW,
            pool_recycle=self.POOL_RECYCLE,
            echo=os.getenv("DB_ECHO", "false").lower() in ["true", "1", "yes"],
        )


# Initialize database configuration
db_config = DatabaseConfig()

# Create engine
engine = db_config.engine

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """
    Dependency for getting database session.
    Used with FastAPI dependency injection.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database by creating all tables.
    Call this once at application startup.
    """
    Base.metadata.create_all(bind=engine)


def drop_all_tables():
    """
    Drop all tables from the database.
    USE WITH CAUTION - This will delete all data!
    """
    Base.metadata.drop_all(bind=engine)


def _validate_db_identifier(name: str) -> str:
    """Validate a DB name used as a SQL identifier to prevent injection.
    Only allows letters, digits, and underscores."""
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError(
            f"Invalid database name '{name}'. Only letters, digits, and underscores are allowed."
        )
    return name


def create_database_if_not_exists():
    """
    Create the database if it doesn't exist.
    This connects to the default 'postgres' database to create the target database.
    """
    db_config = DatabaseConfig()
    
    # Create connection to default 'postgres' database
    default_engine = create_engine(
        f"postgresql://{db_config.DB_USER}:{db_config.DB_PASSWORD}@{db_config.DB_HOST}:{db_config.DB_PORT}/postgres",
        isolation_level="AUTOCOMMIT"
    )
    
    try:
        with default_engine.connect() as connection:
            # Use bind parameter for the existence check to prevent SQL injection
            result = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                {"dbname": db_config.DB_NAME},
            )
            db_exists = result.fetchone() is not None

            if not db_exists:
                # SQL identifiers can't be parameterised; validate instead
                safe_name = _validate_db_identifier(db_config.DB_NAME)
                print(f"Creating database '{safe_name}'...")
                connection.execute(text(f"CREATE DATABASE {safe_name}"))
                print(f"Database '{safe_name}' created successfully!")
            else:
                print(f"Database '{db_config.DB_NAME}' already exists")
    except SQLAlchemyError as e:
        print(f"Error creating database: {e}")
        raise
    finally:
        default_engine.dispose()
