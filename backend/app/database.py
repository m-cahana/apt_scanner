from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
from .config import get_settings

settings = get_settings()


def get_engine():
    """Create engine with appropriate settings for database type."""
    db_url = settings.database_url

    if db_url.startswith("sqlite"):
        # SQLite configuration (for local development)
        return create_engine(
            db_url,
            connect_args={"check_same_thread": False}
        )
    else:
        # PostgreSQL configuration (Supabase or other)
        return create_engine(
            db_url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # Verify connections before use
            pool_recycle=300,    # Recycle connections every 5 minutes
        )


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
