#!/usr/bin/env python3
"""
Legal Case Management System - Verification Script
This script verifies that the system is properly set up and functional.
"""

import os
import sys
import django
import requests
import subprocess
from pathlib import Path

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_status(message, status="INFO"):
    color_map = {
        "INFO": Colors.OKBLUE,
        "SUCCESS": Colors.OKGREEN,
        "WARNING": Colors.WARNING,
        "ERROR": Colors.FAIL
    }
    color = color_map.get(status, Colors.OKBLUE)
    print(f"{color}[{status}]{Colors.ENDC} {message}")

def print_header(title):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{title.center(60)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")

def run_command(command, capture_output=True):
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=capture_output, 
            text=True,
            timeout=30
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)

def check_file_exists(file_path, description):
    """Check if a file exists."""
    if os.path.exists(file_path):
        print_status(f"✓ {description} found", "SUCCESS")
        return True
    else:
        print_status(f"✗ {description} missing: {file_path}", "ERROR")
        return False

def check_python_requirements():
    """Check Python version and requirements."""
    print_header("Python Environment Check")
    
    # Check Python version
    python_version = sys.version_info
    if python_version >= (3, 11):
        print_status(f"✓ Python {python_version.major}.{python_version.minor}.{python_version.micro}", "SUCCESS")
    else:
        print_status(f"✗ Python version {python_version.major}.{python_version.minor} is too old. Requires 3.11+", "ERROR")
        return False
    
    # Check if in virtual environment
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print_status("✓ Virtual environment detected", "SUCCESS")
    else:
        print_status("⚠ Not in virtual environment (recommended for development)", "WARNING")
    
    return True

def check_project_structure():
    """Check if project files are in place."""
    print_header("Project Structure Check")
    
    required_files = [
        ("requirements.txt", "Requirements file"),
        ("legal_manager/manage.py", "Django manage.py"),
        ("legal_manager/settings.py", "Django settings"),
        ("legal_manager/cases/models.py", "Cases models"),
        ("legal_manager/cases/views.py", "Cases views"),
        ("templates/base.html", "Base template"),
        (".env.example", "Environment example file"),
        ("docker-compose.yml", "Docker compose file"),
        ("README.md", "README documentation")
    ]
    
    all_files_exist = True
    for file_path, description in required_files:
        if not check_file_exists(file_path, description):
            all_files_exist = False
    
    return all_files_exist

def check_django_setup():
    """Check Django configuration and database."""
    print_header("Django Setup Check")
    
    try:
        # Change to Django project directory
        os.chdir('legal_manager')
        
        # Setup Django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'legal_manager.settings')
        django.setup()
        
        print_status("✓ Django settings loaded successfully", "SUCCESS")
        
        # Check database connection
        from django.db import connection
        from django.core.management import execute_from_command_line
        
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            print_status("✓ Database connection successful", "SUCCESS")
        except Exception as e:
            print_status(f"✗ Database connection failed: {e}", "ERROR")
            return False
        
        # Check migrations
        success, stdout, stderr = run_command("python manage.py showmigrations --plan")
        if success:
            if "[X]" in stdout:
                print_status("✓ Database migrations applied", "SUCCESS")
            else:
                print_status("⚠ Database migrations not applied", "WARNING")
                print_status("Run: python manage.py migrate", "INFO")
        
        # Check for superuser
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            if User.objects.filter(is_superuser=True).exists():
                print_status("✓ Superuser account exists", "SUCCESS")
            else:
                print_status("⚠ No superuser account found", "WARNING")
                print_status("Run: python manage.py setup_system", "INFO")
        except Exception as e:
            print_status(f"✗ Could not check for superuser: {e}", "ERROR")
        
        os.chdir('..')
        return True
        
    except Exception as e:
        print_status(f"✗ Django setup check failed: {e}", "ERROR")
        os.chdir('..')
        return False

def check_dependencies():
    """Check if required dependencies are installed."""
    print_header("Dependencies Check")
    
    required_packages = [
        'django',
        'djangorestframework',
        'celery',
        'redis',
        'requests',
        'pillow'
    ]
    
    all_installed = True
    for package in required_packages:
        try:
            __import__(package)
            print_status(f"✓ {package} installed", "SUCCESS")
        except ImportError:
            print_status(f"✗ {package} not installed", "ERROR")
            all_installed = False
    
    return all_installed

def check_environment_config():
    """Check environment configuration."""
    print_header("Environment Configuration Check")
    
    if not os.path.exists('.env'):
        print_status("✗ .env file not found", "ERROR")
        print_status("Copy .env.example to .env and configure", "INFO")
        return False
    
    print_status("✓ .env file found", "SUCCESS")
    
    # Check for required environment variables
    required_vars = [
        'SECRET_KEY',
        'DEBUG',
        'ALLOWED_HOSTS'
    ]
    
    with open('.env', 'r') as f:
        env_content = f.read()
    
    for var in required_vars:
        if f"{var}=" in env_content:
            print_status(f"✓ {var} configured", "SUCCESS")
        else:
            print_status(f"✗ {var} not configured", "ERROR")
    
    # Check LLM configuration
    if "LLM_API_KEY=" in env_content and "your-api-key-here" not in env_content:
        print_status("✓ LLM API key configured", "SUCCESS")
    else:
        print_status("⚠ LLM API key not configured (AI features disabled)", "WARNING")
    
    return True

def check_server_functionality():
    """Check if Django server can start."""
    print_header("Server Functionality Check")
    
    os.chdir('legal_manager')
    
    print_status("Starting Django development server...", "INFO")
    
    # Start server in background
    import threading
    import time
    
    def start_server():
        os.system("python manage.py runserver 8001 > /dev/null 2>&1")
    
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # Wait for server to start
    time.sleep(5)
    
    try:
        response = requests.get("http://localhost:8001/health/", timeout=10)
        if response.status_code == 200:
            print_status("✓ Django server started successfully", "SUCCESS")
            print_status("✓ Health check endpoint working", "SUCCESS")
            server_working = True
        else:
            print_status(f"✗ Health check failed with status {response.status_code}", "ERROR")
            server_working = False
    except requests.exceptions.RequestException as e:
        print_status(f"✗ Could not connect to server: {e}", "ERROR")
        server_working = False
    
    # Stop server
    success, _, _ = run_command("pkill -f 'manage.py runserver'")
    
    os.chdir('..')
    return server_working

def check_api_endpoints():
    """Check API endpoints."""
    print_header("API Endpoints Check")
    
    os.chdir('legal_manager')
    
    # Start server for API testing
    import threading
    import time
    
    def start_server():
        os.system("python manage.py runserver 8002 > /dev/null 2>&1")
    
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    time.sleep(5)
    
    api_endpoints = [
        "/health/",
        "/ready/",
        "/live/",
        "/api/",
    ]
    
    all_working = True
    for endpoint in api_endpoints:
        try:
            response = requests.get(f"http://localhost:8002{endpoint}", timeout=5)
            if response.status_code in [200, 401]:  # 401 is OK for protected endpoints
                print_status(f"✓ {endpoint} responding", "SUCCESS")
            else:
                print_status(f"✗ {endpoint} returned {response.status_code}", "ERROR")
                all_working = False
        except requests.exceptions.RequestException:
            print_status(f"✗ {endpoint} not accessible", "ERROR")
            all_working = False
    
    # Stop server
    run_command("pkill -f 'manage.py runserver'")
    
    os.chdir('..')
    return all_working

def check_static_files():
    """Check static files setup."""
    print_header("Static Files Check")
    
    static_dirs = [
        "static/css",
        "static/js",
        "templates"
    ]
    
    all_exist = True
    for static_dir in static_dirs:
        if os.path.exists(static_dir):
            print_status(f"✓ {static_dir} directory exists", "SUCCESS")
        else:
            print_status(f"✗ {static_dir} directory missing", "ERROR")
            all_exist = False
    
    # Check specific static files
    static_files = [
        "static/css/custom.css",
        "static/js/main.js",
        "templates/base.html"
    ]
    
    for static_file in static_files:
        if os.path.exists(static_file):
            print_status(f"✓ {static_file} exists", "SUCCESS")
        else:
            print_status(f"✗ {static_file} missing", "ERROR")
            all_exist = False
    
    return all_exist

def run_tests():
    """Run the test suite."""
    print_header("Test Suite")
    
    os.chdir('legal_manager')
    
    print_status("Running Django tests...", "INFO")
    success, stdout, stderr = run_command("python manage.py test cases --verbosity=2")
    
    if success:
        print_status("✓ All tests passed", "SUCCESS")
    else:
        print_status("✗ Some tests failed", "ERROR")
        print(f"Error output: {stderr}")
    
    os.chdir('..')
    return success

def generate_report(checks_results):
    """Generate a summary report."""
    print_header("Verification Summary")
    
    total_checks = len(checks_results)
    passed_checks = sum(1 for result in checks_results.values() if result)
    
    print(f"Total checks: {total_checks}")
    print(f"Passed: {Colors.OKGREEN}{passed_checks}{Colors.ENDC}")
    print(f"Failed: {Colors.FAIL}{total_checks - passed_checks}{Colors.ENDC}")
    
    if passed_checks == total_checks:
        print_status("🎉 All checks passed! System is ready to use.", "SUCCESS")
        print("\n" + "="*60)
        print(f"{Colors.OKGREEN}Your Legal Case Management System is fully functional!{Colors.ENDC}")
        print("\nTo start using the system:")
        print("1. cd legal_manager")
        print("2. python manage.py runserver")
        print("3. Open http://localhost:8000 in your browser")
        print("4. Login with your admin credentials")
        print("="*60)
    else:
        print_status("⚠ Some checks failed. Please review the issues above.", "WARNING")
        
        if not checks_results.get('dependencies', True):
            print("\n📋 To fix dependency issues:")
            print("pip install -r requirements.txt")
        
        if not checks_results.get('django', True):
            print("\n📋 To fix Django issues:")
            print("cd legal_manager")
            print("python manage.py migrate")
            print("python manage.py setup_system --with-sample-data")
        
        if not checks_results.get('environment', True):
            print("\n📋 To fix environment issues:")
            print("cp .env.example .env")
            print("Edit .env with your configuration")

def main():
    """Main verification function."""
    print(f"{Colors.HEADER}{Colors.BOLD}")
    print("🏛️  Legal Case Management System - Verification Script")
    print("=" * 60)
    print(f"{Colors.ENDC}")
    
    # Run all checks
    checks = {
        'python': check_python_requirements,
        'structure': check_project_structure,
        'dependencies': check_dependencies,
        'environment': check_environment_config,
        'django': check_django_setup,
        'static': check_static_files,
        'server': check_server_functionality,
        'api': check_api_endpoints,
        'tests': run_tests
    }
    
    results = {}
    
    for check_name, check_function in checks.items():
        try:
            results[check_name] = check_function()
        except Exception as e:
            print_status(f"✗ {check_name} check failed with exception: {e}", "ERROR")
            results[check_name] = False
    
    # Generate final report
    generate_report(results)
    
    return all(results.values())

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
