# Legal Case Management System 🏛️

A comprehensive case management system for law firms and legal professionals, built with Django and featuring AI-powered legal assistance.

## Features ✨

- **Case Management**: Complete case lifecycle management with document tracking
- **Client Management**: Client profiles and communication history
- **User Management**: Role-based access control (Admin, Lawyer, Paralegal, Client)
- **Document Management**: Secure document upload and version control
- **Calendar & Events**: Deadline tracking and court date management
- **Time Tracking**: Billable hours tracking and invoicing
- **AI Integration**: LLM-powered legal assistance and document drafting
- **Audit Logging**: Comprehensive audit trail for compliance
- **API Support**: RESTful API for integrations
- **Responsive Design**: Mobile-friendly interface

## Technology Stack 🛠️

- **Backend**: Django 5.0, Django REST Framework
- **Database**: PostgreSQL (production), SQLite (development)
- **Cache/Queue**: Redis, Celery
- **Frontend**: Bootstrap 5, jQuery
- **AI/LLM**: OpenAI API (configurable for other providers)
- **Deployment**: Docker, Docker Compose
- **Web Server**: Nginx (production)

## Quick Start 🚀

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (recommended)
- Git

### Option 1: Docker Setup (Recommended)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd JURISTI
   ```

2. **Environment Configuration**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start with Docker Compose**
   ```bash
   # Development
   docker-compose -f docker-compose.dev.yml up -d
   
   # Production
   docker-compose up -d
   ```

4. **Initialize the System**
   ```bash
   docker-compose exec web python manage.py setup_system --with-sample-data
   ```

5. **Access the Application**
   - Web Interface: http://localhost:8000
   - Admin Panel: http://localhost:8000/admin
   - API: http://localhost:8000/api

### Option 2: Local Development Setup

1. **Clone and Setup Environment**
   ```bash
   git clone <repository-url>
   cd JURISTI
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements-dev.txt
   ```

3. **Database Setup**
   ```bash
   cd legal_manager
   python manage.py migrate
   ```

4. **Initialize System**
   ```bash
   python manage.py setup_system --with-sample-data
   ```

5. **Start Development Server**
   ```bash
   python manage.py runserver
   ```

## Configuration ⚙️

### Environment Variables

Key environment variables in `.env`:

```env
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (PostgreSQL for production)
DB_ENGINE=django.db.backends.postgresql
DB_NAME=legal_manager_db
DB_USER=legal_user
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

# LLM Configuration
LLM_API_KEY=your-openai-api-key
LLM_MODEL=gpt-4o-mini

# Email Configuration
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Celery/Redis
CELERY_BROKER_URL=redis://localhost:6379/0
```

### LLM Setup

1. **Get an API Key**
   - OpenAI: https://platform.openai.com/api-keys
   - Anthropic: https://console.anthropic.com/
   - Other providers: Configure in `llm_service.py`

2. **Configure the Service**
   ```env
   LLM_API_KEY=your-api-key-here
   LLM_API_ENDPOINT=https://api.openai.com/v1/chat/completions
   LLM_MODEL=gpt-4o-mini
   ```

3. **Fine-tuning (Optional)**
   ```bash
   # Process legal documents for training
   python manage.py process_legal_data --documents-dir legal_documents
   ```

## Usage Guide 📖

### User Roles

- **Admin**: Full system access, user management
- **Lawyer**: Case management, client access, document handling
- **Paralegal**: Assigned case access, time tracking
- **Client**: View own cases and documents

### Core Workflows

1. **Creating a Case**
   - Navigate to Cases → New Case
   - Fill in case details, assign lawyer
   - Upload initial documents
   - Set important dates/deadlines

2. **Document Management**
   - Upload documents with version control
   - Organize by case and document type
   - Generate AI-powered document drafts

3. **Calendar & Deadlines**
   - Set court dates and filing deadlines
   - Automatic email reminders
   - Calendar integration

4. **Time Tracking & Billing**
   - Log billable hours per case
   - Generate invoices
   - Track payments

### API Usage

The system provides a full REST API:

```bash
# Authentication
POST /api-auth/login/

# Cases
GET /api/cases/
POST /api/cases/
GET /api/cases/{id}/
PUT /api/cases/{id}/

# Clients
GET /api/clients/
POST /api/clients/

# Documents
POST /api/cases/{id}/add_document/
```

## AI Features 🤖

### Legal Assistant

- **Document Drafting**: Generate legal documents using AI
- **Case Analysis**: Analyze case facts and suggest strategies
- **Legal Research**: Query legal databases with natural language

### Fine-tuning for Local Law

1. **Prepare Legal Documents**
   ```bash
   mkdir legal_documents
   # Add .txt files with legal codes, regulations
   ```

2. **Process and Create Dataset**
   ```bash
   python manage.py process_legal_data --documents-dir legal_documents
   ```

3. **Fine-tune Model**
   - Use the generated JSONL files with your LLM provider
   - Update model configuration in settings

## Development 👨‍💻

### Running Tests

```bash
# All tests
pytest

# Specific test categories
pytest -m unit
pytest -m integration
pytest -m api

# With coverage
pytest --cov=cases --cov-report=html
```

### Code Quality

```bash
# Format code
black .
isort .

# Lint
flake8 .

# Type checking
mypy .
```

### Database

```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Seed sample data
python manage.py seed_data --users 10 --clients 20 --cases 30
```

## Deployment 🚀

### Production Deployment

1. **Server Setup**
   ```bash
   # Clone repository
   git clone <repository-url>
   cd JURISTI
   ```

2. **Environment Configuration**
   ```bash
   cp .env.example .env
   # Configure production settings
   ```

3. **Deploy with Docker**
   ```bash
   docker-compose up -d
   ```

4. **SSL Configuration**
   - Update `nginx.conf` with SSL certificates
   - Use Let's Encrypt for free certificates

### Environment-Specific Settings

- **Development**: `docker-compose.dev.yml`
- **Production**: `docker-compose.yml`
- **Testing**: Separate test database configuration

## Security 🔒

### Built-in Security Features

- CSRF Protection
- XSS Protection
- SQL Injection Prevention
- Role-based Access Control
- Audit Logging
- Two-Factor Authentication (2FA)
- Secure File Uploads

### Security Checklist

- [ ] Change default passwords
- [ ] Configure HTTPS
- [ ] Set up proper firewalls
- [ ] Regular security updates
- [ ] Database encryption
- [ ] Backup strategy

## API Documentation 📚

### Authentication

The API uses session-based authentication. Login through the web interface or use the API endpoints:

```bash
# Login
curl -X POST http://localhost:8000/api-auth/login/ \
  -d "username=admin&password=admin123"
```

### Endpoints

- `GET /api/cases/` - List cases
- `POST /api/cases/` - Create case
- `GET /api/cases/{id}/` - Get case details
- `PUT /api/cases/{id}/` - Update case
- `POST /api/cases/{id}/add_document/` - Upload document
- `GET /api/clients/` - List clients
- `POST /api/clients/` - Create client

## Contributing 🤝

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run the test suite
6. Submit a pull request

## Support 💬

- **Documentation**: Check the `/docs` directory
- **Issues**: Use GitHub Issues
- **Email**: support@legalsystem.com

## License 📄

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments 🙏

- Django and Django REST Framework communities
- Bootstrap for the UI framework
- OpenAI for AI capabilities
- PostgreSQL and Redis teams

---

Built with ❤️ for the legal profession
