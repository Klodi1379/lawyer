#!/bin/bash

# Legal Case Management System - Automated Setup Script
# This script will set up the entire development environment

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to get user input with default
get_input() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"
    
    read -p "$prompt [$default]: " input
    if [ -z "$input" ]; then
        input="$default"
    fi
    eval "$var_name='$input'"
}

# Banner
echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║           Legal Case Management System Setup                 ║"
echo "║                     Version 1.0                             ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

print_status "Starting automated setup process..."

# Check prerequisites
print_status "Checking prerequisites..."

if ! command_exists python3; then
    print_error "Python 3 is not installed. Please install Python 3.11 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
print_success "Python $PYTHON_VERSION found"

if ! command_exists pip; then
    print_error "pip is not installed. Please install pip."
    exit 1
fi

if ! command_exists git; then
    print_warning "Git is not installed. Some features may not work properly."
fi

# Setup type selection
echo ""
print_status "Choose setup type:"
echo "1) Development Setup (SQLite, local development)"
echo "2) Production Setup (PostgreSQL, Redis, Docker)"
echo "3) Docker Development Setup"

get_input "Enter your choice (1-3)" "1" "setup_type"

case $setup_type in
    1)
        SETUP_MODE="development"
        ;;
    2)
        SETUP_MODE="production"
        ;;
    3)
        SETUP_MODE="docker"
        ;;
    *)
        print_error "Invalid choice. Exiting."
        exit 1
        ;;
esac

print_success "Selected: $SETUP_MODE setup"

# Create project directory if not exists
if [ ! -f "manage.py" ] && [ ! -f "legal_manager/manage.py" ]; then
    print_status "Setting up project structure..."
    
    # We're already in the project directory based on the file structure we created
    if [ ! -f "legal_manager/manage.py" ]; then
        print_error "Project structure not found. Please ensure you're in the correct directory."
        exit 1
    fi
fi

# Environment configuration
if [ ! -f ".env" ]; then
    print_status "Creating environment configuration..."
    
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_success "Environment file created from example"
    else
        print_error ".env.example not found. Creating basic .env file..."
        cat > .env << EOF
SECRET_KEY=django-insecure-development-key-change-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=db.sqlite3
LLM_API_KEY=your-api-key-here
EOF
    fi
    
    # Get user preferences
    echo ""
    print_status "Configuring environment..."
    
    get_input "Enter your OpenAI API key (or press Enter to skip)" "" "llm_api_key"
    if [ ! -z "$llm_api_key" ]; then
        if command_exists sed; then
            sed -i.bak "s/your-openai-api-key-here/$llm_api_key/" .env
        else
            print_warning "sed not found. Please manually update LLM_API_KEY in .env file"
        fi
    fi
    
    if [ "$SETUP_MODE" = "production" ]; then
        get_input "Enter database name" "legal_manager_db" "db_name"
        get_input "Enter database user" "legal_user" "db_user" 
        get_input "Enter database password" "" "db_password"
        get_input "Enter database host" "localhost" "db_host"
        
        # Update .env for production
        cat >> .env << EOF

# Production Database Settings
DB_ENGINE=django.db.backends.postgresql
DB_NAME=$db_name
DB_USER=$db_user
DB_PASSWORD=$db_password
DB_HOST=$db_host
DB_PORT=5432
EOF
    fi
else
    print_success "Environment file already exists"
fi

# Virtual environment setup (for non-Docker setups)
if [ "$SETUP_MODE" != "docker" ]; then
    if [ ! -d "venv" ]; then
        print_status "Creating virtual environment..."
        python3 -m venv venv
        print_success "Virtual environment created"
    fi
    
    print_status "Activating virtual environment..."
    source venv/bin/activate
    print_success "Virtual environment activated"
    
    # Install dependencies
    print_status "Installing Python dependencies..."
    
    if [ "$SETUP_MODE" = "development" ]; then
        if [ -f "requirements-dev.txt" ]; then
            pip install -r requirements-dev.txt
        else
            pip install -r requirements.txt
        fi
    else
        pip install -r requirements.txt
    fi
    
    print_success "Dependencies installed"
    
    # Database setup
    print_status "Setting up database..."
    cd legal_manager
    
    python manage.py makemigrations
    python manage.py migrate
    
    print_success "Database setup complete"
    
    # Create superuser
    print_status "Setting up admin account..."
    
    get_input "Enter admin username" "admin" "admin_username"
    get_input "Enter admin email" "admin@example.com" "admin_email"
    get_input "Enter admin password" "admin123" "admin_password"
    
    python manage.py setup_system \
        --superuser-username "$admin_username" \
        --superuser-email "$admin_email" \
        --superuser-password "$admin_password" \
        --with-sample-data
    
    print_success "Admin account created"
    
    cd ..
fi

# Docker setup
if [ "$SETUP_MODE" = "docker" ]; then
    if ! command_exists docker; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command_exists docker-compose; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    print_status "Building Docker images..."
    docker-compose -f docker-compose.dev.yml build
    
    print_status "Starting services..."
    docker-compose -f docker-compose.dev.yml up -d
    
    print_status "Waiting for services to start..."
    sleep 10
    
    print_status "Setting up database in Docker..."
    docker-compose -f docker-compose.dev.yml exec web python manage.py setup_system --with-sample-data
    
    print_success "Docker setup complete"
fi

# Production-specific setup
if [ "$SETUP_MODE" = "production" ]; then
    print_status "Setting up production environment..."
    
    # Check for production dependencies
    if ! command_exists nginx; then
        print_warning "Nginx is not installed. You may want to install it for production."
    fi
    
    if ! command_exists redis-server; then
        print_warning "Redis is not installed. Installing Redis is recommended for production."
    fi
    
    # Collect static files
    cd legal_manager
    python manage.py collectstatic --noinput
    cd ..
    
    print_success "Production setup complete"
fi

# Final checks and information
echo ""
print_status "Running final checks..."

case $SETUP_MODE in
    "development")
        print_success "Development environment ready!"
        echo ""
        echo "🚀 To start the development server:"
        echo "   source venv/bin/activate"
        echo "   cd legal_manager"
        echo "   python manage.py runserver"
        echo ""
        echo "🌐 Access your application at: http://localhost:8000"
        echo "🔧 Admin panel: http://localhost:8000/admin"
        echo "📚 API documentation: http://localhost:8000/api"
        ;;
    "docker")
        print_success "Docker development environment ready!"
        echo ""
        echo "🌐 Access your application at: http://localhost:8000"
        echo "🔧 Admin panel: http://localhost:8000/admin"
        echo ""
        echo "🐳 Docker commands:"
        echo "   View logs: docker-compose -f docker-compose.dev.yml logs -f"
        echo "   Stop: docker-compose -f docker-compose.dev.yml down"
        echo "   Shell: docker-compose -f docker-compose.dev.yml exec web bash"
        ;;
    "production")
        print_success "Production environment setup complete!"
        echo ""
        echo "⚠️  Additional production steps required:"
        echo "   1. Configure nginx with proper SSL certificates"
        echo "   2. Set up proper firewall rules"
        echo "   3. Configure backup procedures"
        echo "   4. Set up monitoring and logging"
        echo "   5. Update SECRET_KEY in .env with a secure value"
        ;;
esac

echo ""
echo "📋 Default admin credentials:"
echo "   Username: ${admin_username:-admin}"
echo "   Password: ${admin_password:-admin123}"
echo ""
print_warning "Remember to change the admin password in production!"

if [ ! -z "$llm_api_key" ]; then
    echo ""
    print_success "🤖 AI features are configured and ready to use!"
else
    echo ""
    print_warning "🤖 AI features are not configured. Add your LLM API key to .env to enable AI features."
fi

echo ""
print_status "Setup complete! 🎉"

# Optionally start the development server
if [ "$SETUP_MODE" = "development" ]; then
    echo ""
    get_input "Would you like to start the development server now? (y/n)" "y" "start_server"
    
    if [ "$start_server" = "y" ] || [ "$start_server" = "Y" ]; then
        print_status "Starting development server..."
        cd legal_manager
        python manage.py runserver
    fi
fi
