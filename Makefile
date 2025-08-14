# Makefile for Legal Case Management System

.PHONY: help setup install dev prod test clean lint format migrate shell backup restore

# Default target
help:
	@echo "Legal Case Management System - Development Commands"
	@echo ""
	@echo "Setup Commands:"
	@echo "  setup          - Initial project setup"
	@echo "  install        - Install dependencies"
	@echo "  install-dev    - Install development dependencies"
	@echo ""
	@echo "Development Commands:"
	@echo "  dev            - Start development server"
	@echo "  migrate        - Run database migrations"
	@echo "  shell          - Start Django shell"
	@echo "  createsuperuser - Create superuser account"
	@echo "  seed           - Create sample data"
	@echo ""
	@echo "Docker Commands:"
	@echo "  docker-dev     - Start development with Docker"
	@echo "  docker-prod    - Start production with Docker"
	@echo "  docker-build   - Build Docker images"
	@echo "  docker-logs    - View Docker logs"
	@echo "  docker-clean   - Clean Docker containers and images"
	@echo ""
	@echo "Testing Commands:"
	@echo "  test           - Run all tests"
	@echo "  test-unit      - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  coverage       - Run tests with coverage report"
	@echo ""
	@echo "Code Quality Commands:"
	@echo "  lint           - Run linting checks"
	@echo "  format         - Format code with black and isort"
	@echo "  type-check     - Run type checking with mypy"
	@echo ""
	@echo "Deployment Commands:"
	@echo "  prod           - Start production server"
	@echo "  backup         - Backup database"
	@echo "  restore        - Restore database from backup"
	@echo ""
	@echo "Maintenance Commands:"
	@echo "  clean          - Clean temporary files"
	@echo "  logs           - View application logs"

# Setup Commands
setup: install migrate createsuperuser
	@echo "✅ Setup complete! Run 'make dev' to start development server"

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

# Development Commands
dev:
	cd legal_manager && python manage.py runserver

migrate:
	cd legal_manager && python manage.py makemigrations
	cd legal_manager && python manage.py migrate

shell:
	cd legal_manager && python manage.py shell

createsuperuser:
	cd legal_manager && python manage.py setup_system

seed:
	cd legal_manager && python manage.py seed_data --users 10 --clients 20 --cases 30

collectstatic:
	cd legal_manager && python manage.py collectstatic --noinput

# Docker Commands
docker-dev:
	docker-compose -f docker-compose.dev.yml up -d
	@echo "🐳 Development environment started at http://localhost:8000"

docker-prod:
	docker-compose up -d
	@echo "🚀 Production environment started"

docker-build:
	docker-compose build

docker-logs:
	docker-compose logs -f

docker-shell:
	docker-compose exec web python manage.py shell

docker-bash:
	docker-compose exec web bash

docker-clean:
	docker-compose down -v
	docker system prune -f

# Testing Commands
test:
	cd legal_manager && pytest

test-unit:
	cd legal_manager && pytest -m unit

test-integration:
	cd legal_manager && pytest -m integration

test-api:
	cd legal_manager && pytest -m api

coverage:
	cd legal_manager && pytest --cov=cases --cov-report=html --cov-report=term
	@echo "📊 Coverage report generated in legal_manager/htmlcov/"

# Code Quality Commands
lint:
	flake8 legal_manager/
	@echo "✅ Linting complete"

format:
	black legal_manager/
	isort legal_manager/
	@echo "✅ Code formatting complete"

type-check:
	mypy legal_manager/
	@echo "✅ Type checking complete"

quality: format lint type-check
	@echo "✅ All code quality checks complete"

# Celery Commands
celery-worker:
	cd legal_manager && celery -A legal_manager worker --loglevel=info

celery-beat:
	cd legal_manager && celery -A legal_manager beat --loglevel=info

celery-flower:
	cd legal_manager && celery -A legal_manager flower

# Database Commands
db-reset:
	cd legal_manager && python manage.py flush --noinput
	cd legal_manager && python manage.py migrate
	cd legal_manager && python manage.py setup_system --with-sample-data

backup:
	@echo "🔄 Creating database backup..."
	cd legal_manager && python manage.py dumpdata --natural-foreign --natural-primary > backup_$(shell date +%Y%m%d_%H%M%S).json
	@echo "✅ Backup created"

restore:
	@read -p "Enter backup file name: " backup_file; \
	cd legal_manager && python manage.py loaddata $$backup_file
	@echo "✅ Database restored"

# Production Commands
prod:
	cd legal_manager && gunicorn --bind 0.0.0.0:8000 --workers 3 legal_manager.wsgi:application

# Maintenance Commands
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.log" -delete
	find . -name ".coverage" -delete
	find . -name "htmlcov" -type d -exec rm -rf {} +
	find . -name ".pytest_cache" -type d -exec rm -rf {} +
	find . -name ".mypy_cache" -type d -exec rm -rf {} +
	@echo "✅ Cleanup complete"

logs:
	tail -f legal_manager/logs/django.log

# Health checks
health:
	@echo "🔍 Running health checks..."
	cd legal_manager && python manage.py check
	@echo "✅ Health checks complete"

# Documentation
docs:
	@echo "📚 Documentation available:"
	@echo "  - README.md - Main documentation"
	@echo "  - API docs at http://localhost:8000/api/ when server is running"
	@echo "  - Admin interface at http://localhost:8000/admin/"

# Security
security-check:
	cd legal_manager && python manage.py check --deploy
	@echo "🔒 Security check complete"

# Environment setup
env-example:
	cp .env.example .env
	@echo "📝 Environment file created. Please edit .env with your settings."

# Quick development setup
quick-start: env-example install-dev migrate seed dev

# Reset development environment
reset-dev: docker-clean clean setup seed

# Production deployment
deploy: docker-build docker-prod
	@echo "🚀 Deployment complete"

# Show current status
status:
	@echo "📊 System Status:"
	@echo "Python: $(shell python --version)"
	@echo "Django: $(shell cd legal_manager && python -c 'import django; print(django.get_version())')"
	@echo "Database: $(shell cd legal_manager && python manage.py showmigrations --plan | grep -c '\[X\]') migrations applied"
	@echo "Users: $(shell cd legal_manager && python manage.py shell -c 'from django.contrib.auth import get_user_model; print(get_user_model().objects.count())')"

# Show configuration
config:
	@echo "⚙️  Configuration:"
	cd legal_manager && python manage.py diffsettings

# Help for specific commands
help-docker:
	@echo "🐳 Docker Commands Help:"
	@echo "  make docker-dev    - Start development environment with hot reload"
	@echo "  make docker-prod   - Start production environment with nginx"
	@echo "  make docker-logs   - View all container logs"
	@echo "  make docker-shell  - Access Django shell in container"
	@echo "  make docker-bash   - Access bash shell in container"

help-test:
	@echo "🧪 Testing Commands Help:"
	@echo "  make test         - Run all tests"
	@echo "  make test-unit    - Run only unit tests (fast)"
	@echo "  make test-integration - Run integration tests"
	@echo "  make coverage     - Generate test coverage report"
