"""FastAPI dependencies."""

from typing import Generator
from sqlalchemy.orm import Session
from database.connection import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """
    Database session dependency.

    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
