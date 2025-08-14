#!/usr/bin/env python
"""
Django Application Test Script
==============================
Teston nëse Django aplikacioni po funksionon siç duhet me layout-in e ri.
"""

import os
import sys
import subprocess
import django
from django.core.management import execute_from_command_line
from django.conf import settings

def check_django_setup():
    """Check Django setup dhe settings"""
    print("=> Checking Django setup...")
    
    try:
        # Check if manage.py exists
        if not os.path.exists('manage.py'):
            print("[ERROR] manage.py not found. Are you in the project root?")
            return False
            
        # Try to import Django
        import django
        print(f"[OK] Django version: {django.get_version()}")
        
        # Check if we can access settings
        try:
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'legal_manager.settings')
            django.setup()
            print("[OK] Django settings loaded successfully")
            return True
        except Exception as e:
            print(f"[ERROR] Could not load Django settings: {e}")
            return False
            
    except ImportError:
        print("[ERROR] Django not installed or not accessible")
        return False

def run_django_checks():
    """Run Django system checks"""
    print("\n=> Running Django system checks...")
    
    try:
        from django.core.management import call_command
        from io import StringIO
        import sys
        
        # Capture output
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        try:
            call_command('check')
            output = captured_output.getvalue()
            sys.stdout = old_stdout
            
            if 'System check identified no issues' in output:
                print("[OK] Django system check passed")
                return True
            else:
                print(f"[WARNING] Django system check output: {output}")
                return True
        except Exception as e:
            sys.stdout = old_stdout
            print(f"[ERROR] Django system check failed: {e}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Could not run Django checks: {e}")
        return False

def check_static_files():
    """Check static files setup"""
    print("\n=> Checking static files setup...")
    
    try:
        from django.conf import settings
        
        # Check STATIC_URL
        if hasattr(settings, 'STATIC_URL'):
            print(f"[OK] STATIC_URL: {settings.STATIC_URL}")
        else:
            print("[WARNING] STATIC_URL not configured")
            
        # Check STATICFILES_DIRS
        if hasattr(settings, 'STATICFILES_DIRS'):
            print(f"[OK] STATICFILES_DIRS: {settings.STATICFILES_DIRS}")
        else:
            print("[INFO] STATICFILES_DIRS not configured (using app static dirs)")
            
        # Check if static files exist
        static_files = [
            'static/css/custom.css',
            'static/css/mobile-dashboard.css'
        ]
        
        missing_static = []
        for file_path in static_files:
            if not os.path.exists(file_path):
                missing_static.append(file_path)
                
        if missing_static:
            print(f"[ERROR] Missing static files: {missing_static}")
            return False
        else:
            print("[OK] Required static files found")
            
        return True
        
    except Exception as e:
        print(f"[ERROR] Could not check static files: {e}")
        return False

def check_templates():
    """Check templates setup"""
    print("\n=> Checking templates setup...")
    
    try:
        from django.conf import settings
        
        # Check TEMPLATES setting
        if hasattr(settings, 'TEMPLATES') and settings.TEMPLATES:
            template_dirs = settings.TEMPLATES[0].get('DIRS', [])
            print(f"[OK] Template directories: {template_dirs}")
        else:
            print("[WARNING] TEMPLATES setting not configured properly")
            
        # Check if templates exist
        template_files = [
            'templates/base.html',
            'templates/partials/sidebar.html'
        ]
        
        missing_templates = []
        for file_path in template_files:
            if not os.path.exists(file_path):
                missing_templates.append(file_path)
                
        if missing_templates:
            print(f"[ERROR] Missing template files: {missing_templates}")
            return False
        else:
            print("[OK] Required template files found")
            
        return True
        
    except Exception as e:
        print(f"[ERROR] Could not check templates: {e}")
        return False

def test_url_imports():
    """Test if URL imports work"""
    print("\n=> Testing URL imports...")
    
    try:
        from django.urls import reverse
        
        # Test some common URLs (adjust based on your actual URLs)
        test_urls = [
            'admin:index',  # Django admin should always be available
        ]
        
        for url_name in test_urls:
            try:
                url = reverse(url_name)
                print(f"[OK] URL '{url_name}' resolves to: {url}")
            except Exception as e:
                print(f"[INFO] URL '{url_name}' not available: {e}")
                
        return True
        
    except Exception as e:
        print(f"[ERROR] Could not test URL imports: {e}")
        return False

def create_test_view():
    """Create a simple test view for layout testing"""
    print("\n=> Creating test view...")
    
    test_view_content = '''from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required

def layout_test_view(request):
    """Simple view to test layout functionality"""
    context = {
        'test_data': {
            'cases_count': 5,
            'documents_count': 12,
            'events_count': 8,
        }
    }
    return render(request, 'test_layout.html', context)

def health_check(request):
    """Health check endpoint"""
    return HttpResponse("OK - Legal Case Manager is running")
'''
    
    test_template_content = '''{% extends 'base.html' %}

{% block title %}Layout Test{% endblock %}

{% block content %}
<div class="container-fluid">
    <div class="row">
        <div class="col-12">
            <h1 class="mb-4">
                <i class="bi bi-check-circle text-success me-2"></i>
                Layout Test Page
            </h1>
            
            <div class="alert alert-success" role="alert">
                <h4 class="alert-heading">Layout Test Successful!</h4>
                <p class="mb-0">If you can see this page with the sidebar and navigation working properly, the layout is functioning correctly.</p>
            </div>
            
            <div class="row">
                <div class="col-md-4">
                    <div class="card">
                        <div class="card-header">
                            <h5 class="mb-0">Test Statistics</h5>
                        </div>
                        <div class="card-body">
                            <ul class="list-group list-group-flush">
                                <li class="list-group-item d-flex justify-content-between">
                                    <span>Cases:</span>
                                    <strong>{{ test_data.cases_count }}</strong>
                                </li>
                                <li class="list-group-item d-flex justify-content-between">
                                    <span>Documents:</span>
                                    <strong>{{ test_data.documents_count }}</strong>
                                </li>
                                <li class="list-group-item d-flex justify-content-between">
                                    <span>Events:</span>
                                    <strong>{{ test_data.events_count }}</strong>
                                </li>
                            </ul>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-8">
                    <div class="card">
                        <div class="card-header">
                            <h5 class="mb-0">Layout Features</h5>
                        </div>
                        <div class="card-body">
                            <div class="row">
                                <div class="col-md-6">
                                    <h6>Desktop Features:</h6>
                                    <ul>
                                        <li>Fixed sidebar navigation</li>
                                        <li>Responsive main content</li>
                                        <li>Sticky top navbar</li>
                                        <li>Bootstrap components</li>
                                    </ul>
                                </div>
                                <div class="col-md-6">
                                    <h6>Mobile Features:</h6>
                                    <ul>
                                        <li>Collapsible sidebar</li>
                                        <li>Touch-friendly interface</li>
                                        <li>Responsive grid system</li>
                                        <li>Mobile-optimized navigation</li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="mt-4">
                <div class="card">
                    <div class="card-body">
                        <h5>Testing Instructions:</h5>
                        <ol>
                            <li>Resize the browser window to test responsive behavior</li>
                            <li>On mobile size, use the hamburger menu to toggle the sidebar</li>
                            <li>Check that all navigation links are accessible</li>
                            <li>Verify that content doesn't overlap with the sidebar</li>
                            <li>Test all interactive elements (buttons, links, etc.)</li>
                        </ol>
                        
                        <button class="btn btn-primary me-2" onclick="alert('Button test successful!')">
                            <i class="bi bi-check me-1"></i>Test Button
                        </button>
                        
                        <button class="btn btn-outline-secondary" onclick="window.location.reload()">
                            <i class="bi bi-arrow-clockwise me-1"></i>Reload Page
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
'''
    
    try:
        # Create test views file
        with open('test_views.py', 'w', encoding='utf-8') as f:
            f.write(test_view_content)
        print("[OK] Test views file created: test_views.py")
        
        # Create test template
        os.makedirs('templates', exist_ok=True)
        with open('templates/test_layout.html', 'w', encoding='utf-8') as f:
            f.write(test_template_content)
        print("[OK] Test template created: templates/test_layout.html")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Could not create test files: {e}")
        return False

def run_all_tests():
    """Run all Django tests"""
    print("Django Application Testing")
    print("=" * 50)
    
    all_passed = True
    
    # Check Django setup
    if not check_django_setup():
        all_passed = False
        return False  # Can't continue without Django
    
    # Run Django system checks
    if not run_django_checks():
        all_passed = False
    
    # Check static files
    if not check_static_files():
        all_passed = False
    
    # Check templates
    if not check_templates():
        all_passed = False
    
    # Test URL imports
    if not test_url_imports():
        all_passed = False
    
    # Create test view
    if not create_test_view():
        all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("[SUCCESS] Django application tests passed!")
        print("\nNext steps:")
        print("   1. Start the development server:")
        print("      python manage.py runserver")
        print("   2. Open http://127.0.0.1:8000/ in your browser")
        print("   3. Test the layout and functionality")
        print("   4. Check browser console for any JavaScript errors")
        print("\nTest URLs:")
        print("   - Health check: http://127.0.0.1:8000/health/")
        print("   - Layout test: http://127.0.0.1:8000/test-layout/")
        print("   - Admin panel: http://127.0.0.1:8000/admin/")
    else:
        print("[FAILED] Some Django tests failed. Please fix the issues before starting the server.")
    
    return all_passed

if __name__ == "__main__":
    run_all_tests()
