# PowerShell Setup Script for Legal Case Management System
# This script sets up the development environment on Windows

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("dev", "prod", "docker")]
    [string]$SetupType = "dev",
    
    [Parameter(Mandatory=$false)]
    [switch]$WithSampleData,
    
    [Parameter(Mandatory=$false)]
    [string]$PythonPath = "python",
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipVenv
)

# Colors for output
$Red = [ConsoleColor]::Red
$Green = [ConsoleColor]::Green
$Yellow = [ConsoleColor]::Yellow
$Blue = [ConsoleColor]::Blue
$White = [ConsoleColor]::White

function Write-ColorOutput {
    param([string]$Message, [ConsoleColor]$Color = $White)
    Write-Host $Message -ForegroundColor $Color
}

function Write-Status {
    param([string]$Message)
    Write-ColorOutput "[INFO] $Message" $Blue
}

function Write-Success {
    param([string]$Message)
    Write-ColorOutput "[SUCCESS] $Message" $Green
}

function Write-Warning {
    param([string]$Message)
    Write-ColorOutput "[WARNING] $Message" $Yellow
}

function Write-Error {
    param([string]$Message)
    Write-ColorOutput "[ERROR] $Message" $Red
}

function Test-Command {
    param([string]$Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Get-UserInput {
    param([string]$Prompt, [string]$Default = "")
    if ($Default) {
        $input = Read-Host "$Prompt [$Default]"
        if ([string]::IsNullOrWhiteSpace($input)) {
            return $Default
        }
        return $input
    }
    else {
        return Read-Host $Prompt
    }
}

# Banner
Write-ColorOutput @"
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║           Legal Case Management System Setup                 ║
║                     PowerShell Version                      ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"@ $Blue

Write-Status "Starting automated setup process for $SetupType environment..."

# Check prerequisites
Write-Status "Checking prerequisites..."

# Check Python
if (-not (Test-Command $PythonPath)) {
    Write-Error "Python is not found at '$PythonPath'. Please install Python 3.11+ or specify the correct path."
    exit 1
}

try {
    $pythonVersion = & $PythonPath --version 2>&1
    Write-Success "Found $pythonVersion"
}
catch {
    Write-Error "Failed to get Python version"
    exit 1
}

# Check pip
if (-not (Test-Command "pip")) {
    Write-Error "pip is not found. Please ensure pip is installed and in PATH."
    exit 1
}

# Check Git (optional)
if (-not (Test-Command "git")) {
    Write-Warning "Git is not found. Some features may not work properly."
}

# Check Docker for docker setup
if ($SetupType -eq "docker") {
    if (-not (Test-Command "docker")) {
        Write-Error "Docker is not found. Please install Docker Desktop for Windows."
        exit 1
    }
    
    if (-not (Test-Command "docker-compose")) {
        Write-Error "Docker Compose is not found. Please install Docker Compose."
        exit 1
    }
    
    Write-Success "Docker and Docker Compose found"
}

# Verify project structure
if (-not (Test-Path "legal_manager\manage.py")) {
    Write-Error "Django project structure not found. Please ensure you're in the correct directory."
    exit 1
}

Write-Success "Project structure verified"

# Environment configuration
if (-not (Test-Path ".env")) {
    Write-Status "Creating environment configuration..."
    
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Success "Environment file created from example"
    }
    else {
        Write-Error ".env.example not found. Creating basic .env file..."
        @"
SECRET_KEY=django-insecure-development-key-change-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=db.sqlite3
LLM_API_KEY=your-api-key-here
"@ | Out-File -FilePath ".env" -Encoding UTF8
    }
    
    # Get user preferences
    Write-Status "Configuring environment..."
    
    $llmApiKey = Get-UserInput "Enter your OpenAI API key (or press Enter to skip)" ""
    if ($llmApiKey) {
        (Get-Content ".env") -replace "your-openai-api-key-here", $llmApiKey | Set-Content ".env"
    }
    
    if ($SetupType -eq "prod") {
        $dbName = Get-UserInput "Enter database name" "legal_manager_db"
        $dbUser = Get-UserInput "Enter database user" "legal_user"
        $dbPassword = Get-UserInput "Enter database password"
        $dbHost = Get-UserInput "Enter database host" "localhost"
        
        # Append production settings
        @"

# Production Database Settings
DB_ENGINE=django.db.backends.postgresql
DB_NAME=$dbName
DB_USER=$dbUser
DB_PASSWORD=$dbPassword
DB_HOST=$dbHost
DB_PORT=5432
"@ | Add-Content ".env"
    }
}
else {
    Write-Success "Environment file already exists"
}

# Handle different setup types
switch ($SetupType) {
    "docker" {
        Write-Status "Setting up Docker environment..."
        
        Write-Status "Building Docker images..."
        & docker-compose -f docker-compose.dev.yml build
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to build Docker images"
            exit 1
        }
        
        Write-Status "Starting Docker services..."
        & docker-compose -f docker-compose.dev.yml up -d
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to start Docker services"
            exit 1
        }
        
        Write-Status "Waiting for services to start..."
        Start-Sleep -Seconds 15
        
        Write-Status "Setting up database in Docker..."
        $setupArgs = "--superuser-username admin --superuser-email admin@example.com --superuser-password admin123"
        if ($WithSampleData) {
            $setupArgs += " --with-sample-data"
        }
        
        & docker-compose -f docker-compose.dev.yml exec web python manage.py setup_system $setupArgs.Split(' ')
        
        Write-Success "Docker setup complete"
    }
    
    default {
        # Virtual environment setup
        if (-not $SkipVenv -and -not (Test-Path "venv")) {
            Write-Status "Creating virtual environment..."
            & $PythonPath -m venv venv
            if ($LASTEXITCODE -ne 0) {
                Write-Error "Failed to create virtual environment"
                exit 1
            }
            Write-Success "Virtual environment created"
        }
        
        # Activate virtual environment
        if (-not $SkipVenv) {
            Write-Status "Activating virtual environment..."
            if (Test-Path "venv\Scripts\Activate.ps1") {
                & "venv\Scripts\Activate.ps1"
            }
            elseif (Test-Path "venv\Scripts\activate.bat") {
                & "venv\Scripts\activate.bat"
            }
            else {
                Write-Warning "Could not find virtual environment activation script"
            }
        }
        
        # Install dependencies
        Write-Status "Installing Python dependencies..."
        
        $requirementsFile = "requirements.txt"
        if ($SetupType -eq "dev" -and (Test-Path "requirements-dev.txt")) {
            $requirementsFile = "requirements-dev.txt"
        }
        
        & pip install -r $requirementsFile
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to install dependencies"
            exit 1
        }
        
        Write-Success "Dependencies installed"
        
        # Database setup
        Write-Status "Setting up database..."
        Set-Location "legal_manager"
        
        & $PythonPath manage.py makemigrations
        & $PythonPath manage.py migrate
        
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Database setup failed"
            Set-Location ".."
            exit 1
        }
        
        Write-Success "Database setup complete"
        
        # Create superuser
        Write-Status "Setting up admin account..."
        
        $adminUsername = Get-UserInput "Enter admin username" "admin"
        $adminEmail = Get-UserInput "Enter admin email" "admin@example.com"
        $adminPassword = Get-UserInput "Enter admin password" "admin123"
        
        $setupArgs = @(
            "setup_system",
            "--superuser-username", $adminUsername,
            "--superuser-email", $adminEmail,
            "--superuser-password", $adminPassword
        )
        
        if ($WithSampleData) {
            $setupArgs += "--with-sample-data"
        }
        
        & $PythonPath manage.py @setupArgs
        
        Write-Success "Admin account created"
        
        # Collect static files for production
        if ($SetupType -eq "prod") {
            Write-Status "Collecting static files..."
            & $PythonPath manage.py collectstatic --noinput
        }
        
        Set-Location ".."
    }
}

# Display results
Write-Status "Setup completed successfully! 🎉"
Write-Host ""

switch ($SetupType) {
    "docker" {
        Write-Success "Docker development environment ready!"
        Write-Host ""
        Write-Host "🌐 Access your application at: http://localhost:8000" -ForegroundColor Cyan
        Write-Host "🔧 Admin panel: http://localhost:8000/admin" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "🐳 Docker commands:" -ForegroundColor Yellow
        Write-Host "   View logs: docker-compose -f docker-compose.dev.yml logs -f"
        Write-Host "   Stop: docker-compose -f docker-compose.dev.yml down"
        Write-Host "   Shell: docker-compose -f docker-compose.dev.yml exec web bash"
    }
    
    "prod" {
        Write-Success "Production environment setup complete!"
        Write-Host ""
        Write-Host "⚠️  Additional production steps required:" -ForegroundColor Yellow
        Write-Host "   1. Configure nginx with proper SSL certificates"
        Write-Host "   2. Set up proper firewall rules"
        Write-Host "   3. Configure backup procedures"
        Write-Host "   4. Set up monitoring and logging"
        Write-Host "   5. Update SECRET_KEY in .env with a secure value"
    }
    
    default {
        Write-Success "Development environment ready!"
        Write-Host ""
        Write-Host "🚀 To start the development server:" -ForegroundColor Cyan
        Write-Host "   cd legal_manager"
        Write-Host "   python manage.py runserver"
        Write-Host ""
        Write-Host "🌐 Access your application at: http://localhost:8000" -ForegroundColor Cyan
        Write-Host "🔧 Admin panel: http://localhost:8000/admin" -ForegroundColor Cyan
        Write-Host "📚 API documentation: http://localhost:8000/api" -ForegroundColor Cyan
    }
}

Write-Host ""
Write-Host "📋 Default admin credentials:" -ForegroundColor Green
Write-Host "   Username: $($adminUsername ?? 'admin')"
Write-Host "   Password: $($adminPassword ?? 'admin123')"

if ($llmApiKey) {
    Write-Host ""
    Write-Success "🤖 AI features are configured and ready to use!"
}
else {
    Write-Host ""
    Write-Warning "🤖 AI features are not configured. Add your LLM API key to .env to enable AI features."
}

Write-Host ""
Write-Warning "Remember to change the admin password in production!"

# Ask to start development server
if ($SetupType -eq "dev") {
    Write-Host ""
    $startServer = Get-UserInput "Would you like to start the development server now? (y/n)" "y"
    
    if ($startServer -eq "y" -or $startServer -eq "Y") {
        Write-Status "Starting development server..."
        Set-Location "legal_manager"
        & $PythonPath manage.py runserver
    }
}

Write-Host ""
Write-Success "Setup script completed successfully! 🎉"
