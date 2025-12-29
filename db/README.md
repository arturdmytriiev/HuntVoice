# Database Layer

This directory contains the database layer for the HuntVoice Voice AI Restaurant Bot.

## Structure

- `base.py`: SQLAlchemy DeclarativeBase and base mixins
- `models_sqlalchemy.py`: SQLAlchemy ORM models (tables)
- `session.py`: Async session management and database configuration
- `alembic.ini`: Alembic configuration for migrations
- `migrations/`: Alembic migrations directory
  - `env.py`: Alembic environment setup with async support
  - `versions/`: Migration version files

## Models

### Reservation
Stores restaurant reservation data:
- id (UUID): Primary key
- name, phone, date, time, guests: Reservation details
- notes: Optional special requests
- status: Reservation status (pending, confirmed, canceled, etc.)
- created_at, updated_at, canceled_at: Timestamps

### CallSession
Stores call session state:
- call_id (String): Primary key
- phone_number, intent, status: Call metadata
- state_json (JSONB): Complete call state
- current_step, error_count: Call progress tracking
- started_at, updated_at, completed_at: Timestamps

### AuditLog
Tracks all system actions:
- id (Integer): Primary key
- action, entity_type, entity_id: What was done
- user_id, metadata: Who did it and additional context
- ip_address: Source IP
- created_at: Timestamp

## Usage

### Initialize Database

```python
from db import init_db

# Create all tables
await init_db()
```

### Get Database Session

```python
from db import get_session_context

async with get_session_context() as session:
    # Use session
    result = await session.execute(select(Reservation))
    reservations = result.scalars().all()
```

### Run Migrations

```bash
# Create a new migration
cd db
alembic -c alembic.ini revision --autogenerate -m "Description"

# Apply migrations
alembic -c alembic.ini upgrade head

# Rollback migration
alembic -c alembic.ini downgrade -1
```

## Configuration

Set the following environment variables:

- `DATABASE_URL`: PostgreSQL connection URL (async driver required)
- `DB_POOL_SIZE`: Connection pool size (default: 5)
- `DB_MAX_OVERFLOW`: Max overflow connections (default: 10)
- `DB_ECHO`: Enable SQL logging (default: false)

See `.env.example` for all configuration options.

## Requirements

- PostgreSQL 12+
- Python 3.11+
- asyncpg driver
- SQLAlchemy 2.0+
- Alembic 1.13+
