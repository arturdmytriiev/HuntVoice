# Restaurant Voice AI Bot

A sophisticated Voice AI system for handling restaurant calls, reservations, and customer inquiries using LangGraph, FastAPI, and Twilio.

## Features

- Voice-based conversation handling via Twilio
- AI-powered restaurant assistant using LangGraph
- Reservation management system
- Multi-turn conversation support
- Real-time call transcription
- PostgreSQL database for persistent storage
- Redis for session management and caching
- Structured JSON logging
- Docker containerization

## Project Structure

```
restaurant-voice-bot/
├── apps/api/              # FastAPI application and API endpoints
├── core/                  # Core configuration, settings, and logging
├── domain/                # Domain models and business logic
├── db/                    # Database models, migrations, and repositories
├── services/              # Business services layer
├── tools/                 # LangGraph tools and utilities
├── graph/                 # LangGraph workflow definitions
├── integrations/twilio/   # Twilio integration
├── data/                  # Data files and resources
├── tests/                 # Test suite
├── Dockerfile            # Container definition
├── docker-compose.yml    # Multi-container orchestration
├── requirements.txt      # Python dependencies
└── .env.example          # Environment variables template
```

## Prerequisites

- Docker and Docker Compose (recommended)
- Python 3.11+ (for local development)
- PostgreSQL 15+ (if not using Docker)
- Redis 7+ (if not using Docker)
- Twilio account with phone number
- OpenAI API key

## Quick Start with Docker

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd restaurant-voice-bot
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Configure required credentials in `.env`**
   - `TWILIO_ACCOUNT_SID`: Your Twilio Account SID
   - `TWILIO_AUTH_TOKEN`: Your Twilio Auth Token
   - `TWILIO_PHONE_NUMBER`: Your Twilio phone number
   - `OPENAI_API_KEY`: Your OpenAI API key

4. **Start the application**
   ```bash
   docker-compose up -d
   ```

5. **Check application status**
   ```bash
   docker-compose ps
   docker-compose logs -f app
   ```

6. **Access the application**
   - API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

## Local Development Setup

1. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your local configuration
   ```

4. **Start PostgreSQL and Redis**
   ```bash
   docker-compose up -d postgres redis
   ```

5. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

6. **Start the application**
   ```bash
   uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000
   ```

## Configuration

### Environment Variables

Key environment variables (see `.env.example` for complete list):

- **Application**
  - `APP_ENV`: Environment (development, staging, production)
  - `DEBUG`: Enable debug mode
  - `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)

- **Database**
  - `DATABASE_URL`: PostgreSQL connection string
  - `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`: Database credentials

- **Redis**
  - `REDIS_URL`: Redis connection string

- **Restaurant**
  - `RESTAURANT_NAME`: Your restaurant name
  - `RESTAURANT_HOURS_OPEN`: Opening time (HH:MM format)
  - `RESTAURANT_HOURS_CLOSE`: Closing time (HH:MM format)
  - `RESTAURANT_TIMEZONE`: Restaurant timezone

- **Twilio**
  - `TWILIO_ACCOUNT_SID`: Twilio Account SID
  - `TWILIO_AUTH_TOKEN`: Twilio Auth Token
  - `TWILIO_PHONE_NUMBER`: Twilio phone number

- **OpenAI**
  - `OPENAI_API_KEY`: OpenAI API key
  - `OPENAI_MODEL`: Model to use (default: gpt-4-turbo-preview)

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_api.py

# Run with verbose output
pytest -v
```

## Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Show current migration status
alembic current
```

## Docker Commands

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f [service-name]

# Stop all services
docker-compose down

# Rebuild containers
docker-compose up -d --build

# Execute command in container
docker-compose exec app bash

# View running containers
docker-compose ps
```

## API Endpoints

Once running, explore the API documentation at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Twilio Webhook Configuration

1. Log in to your Twilio Console
2. Navigate to your phone number configuration
3. Set the Voice webhook URL to: `https://your-domain.com/api/v1/twilio/voice`
4. Set the HTTP method to `POST`
5. Update `WEBHOOK_BASE_URL` in your `.env` file

## Logging

The application uses structured JSON logging in production and human-readable logs in development.

Logs include:
- Timestamp
- Log level
- Module and function information
- Custom contextual fields
- Exception traces

## Troubleshooting

### Database Connection Issues
```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# View PostgreSQL logs
docker-compose logs postgres
```

### Redis Connection Issues
```bash
# Check if Redis is running
docker-compose ps redis

# Test Redis connection
docker-compose exec redis redis-cli ping
```

### Application Not Starting
```bash
# View application logs
docker-compose logs app

# Restart the application
docker-compose restart app
```

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests
4. Submit a pull request

## License

[Your License Here]

## Support

For issues and questions, please contact [Your Contact Information]
