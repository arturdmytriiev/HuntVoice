"""Pytest configuration and fixtures for restaurant bot tests."""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.models import Base, Reservation
from src.reservation_service import ReservationService
from src.graph.nodes import ConversationNodes
from src.graph.workflow import create_restaurant_bot_graph


@pytest.fixture(scope="function")
def db_engine():
    """Create an in-memory SQLite database engine for testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create a database session for testing."""
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="function")
def reservation_service(db_session):
    """Create a reservation service instance for testing."""
    return ReservationService(db_session, max_capacity=50, table_turnover_minutes=120)


@pytest.fixture(scope="function")
def sample_reservation_data():
    """Provide sample reservation data for testing."""
    return {
        "customer_name": "John Doe",
        "phone_number": "1234567890",
        "party_size": 4,
        "reservation_time": datetime(2024, 3, 15, 19, 0),  # 7:00 PM
        "notes": "Window seat preferred",
    }


@pytest.fixture(scope="function")
def create_sample_reservation(reservation_service, sample_reservation_data):
    """Factory fixture to create a sample reservation."""
    def _create(**kwargs):
        data = sample_reservation_data.copy()
        data.update(kwargs)
        return reservation_service.create_reservation(**data)
    return _create


@pytest.fixture(scope="function")
def conversation_nodes(reservation_service):
    """Create conversation nodes instance for testing."""
    return ConversationNodes(reservation_service)


@pytest.fixture(scope="function")
def restaurant_bot_graph(reservation_service):
    """Create a compiled restaurant bot graph for testing."""
    return create_restaurant_bot_graph(reservation_service)


@pytest.fixture(scope="function")
def base_time():
    """Provide a base datetime for consistent testing."""
    return datetime(2024, 3, 15, 12, 0)  # Noon on March 15, 2024


@pytest.fixture(scope="function")
def mock_available_times(base_time):
    """Provide a list of mock available reservation times."""
    return [
        base_time.replace(hour=17, minute=0),  # 5:00 PM
        base_time.replace(hour=17, minute=30),  # 5:30 PM
        base_time.replace(hour=18, minute=0),  # 6:00 PM
        base_time.replace(hour=18, minute=30),  # 6:30 PM
        base_time.replace(hour=19, minute=0),  # 7:00 PM
        base_time.replace(hour=19, minute=30),  # 7:30 PM
        base_time.replace(hour=20, minute=0),  # 8:00 PM
    ]


@pytest.fixture(scope="function")
def populate_reservations(reservation_service, base_time):
    """Factory fixture to populate database with multiple reservations."""
    def _populate(count=5):
        reservations = []
        for i in range(count):
            res = reservation_service.create_reservation(
                customer_name=f"Customer {i+1}",
                phone_number=f"555000{i:04d}",
                party_size=2 + (i % 4),
                reservation_time=base_time.replace(hour=18) + timedelta(hours=i),
                notes=f"Test reservation {i+1}",
            )
            reservations.append(res)
        return reservations
    return _populate


@pytest.fixture(autouse=True)
def reset_state():
    """Reset any global state between tests."""
    yield
    # Cleanup code here if needed
