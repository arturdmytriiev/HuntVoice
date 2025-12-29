"""Database models for the restaurant reservation system."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, Boolean, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

Base = declarative_base()


class Reservation(Base):
    """Reservation model."""

    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    party_size = Column(Integer, nullable=False)
    reservation_time = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    cancelled = Column(Boolean, default=False)
    notes = Column(String, nullable=True)

    def __repr__(self):
        return (
            f"<Reservation(id={self.id}, name='{self.customer_name}', "
            f"time='{self.reservation_time}', size={self.party_size})>"
        )


def get_engine(database_url: str = "sqlite:///./restaurant.db"):
    """Create and return database engine."""
    return create_engine(database_url, connect_args={"check_same_thread": False})


def init_db(engine):
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


def get_db_session(engine) -> Session:
    """Get database session."""
    return Session(bind=engine)
