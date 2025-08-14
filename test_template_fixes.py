#!/usr/bin/env python3
"""
Test i shpejtë për të verifikuar se template-t janë rregulluar
"""

import os
import sys
import django
from pathlib import Path

# Add the project directory to the Python path
project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))
sys.path.insert(0, str(project_dir / 'legal_manager'))

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'legal_manager.settings')
django.setup()

from django.test import Client
from django.urls import reverse

def test_templates():
    """Test që template-t po punojnë siç duhet"""
    print("TESTING TEMPLATE FIXES")
    print("=" * 50)
    
    client = Client()
    
    # Test URLs dhe template rendering
    test_urls = [
        ('/', 'Dashboard'),
        ('/login/', 'Login Page'),
        ('/register/', 'Registration Page'),
    ]
    
    for url, description in test_urls:
        try:
            response = client.get(url)
            if response.status_code == 200:
                print(f"[PASS] {description}: OK (Status: {response.status_code})")
            elif response.status_code == 302:
                print(f"[WARN] {description}: Redirect (Status: {response.status_code})")
            else:
                print(f"[FAIL] {description}: Error (Status: {response.status_code})")
        except Exception as e:
            print(f"[FAIL] {description}: Exception - {str(e)}")
    
    # Test static files paths
    print("\nSTATIC FILES CHECK")
    print("-" * 30)
    
    static_files = [
        'static/css/custom.css',
        'static/js/pwa.js',
        'static/js/widget-manager.js',
    ]
    
    for static_file in static_files:
        file_path = project_dir / static_file
        if file_path.exists():
            print(f"[PASS] {static_file}: Exists")
        else:
            print(f"[FAIL] {static_file}: Missing")
    
    # Test templates
    print("\nTEMPLATES CHECK")
    print("-" * 30)
    
    template_files = [
        'templates/base.html',
        'templates/partials/sidebar.html',
        'templates/dashboard/enhanced_dashboard.html',
        'templates/cases/case_list.html',
        'templates/clients/client_list.html',
        'templates/documents/document_list.html',
        'templates/llm/document_editor.html',
    ]
    
    for template_file in template_files:
        file_path = project_dir / template_file
        if file_path.exists():
            print(f"[PASS] {template_file}: Exists")
        else:
            print(f"[FAIL] {template_file}: Missing")
    
    # Test CSS classes in base.html
    print("\nCSS INTEGRATION CHECK")
    print("-" * 30)
    
    base_html_path = project_dir / 'templates' / 'base.html'
    if base_html_path.exists():
        content = base_html_path.read_text(encoding='utf-8')
        
        css_checks = [
            ('sidebar', 'Sidebar included'),
            ('main-content-with-sidebar', 'Main content wrapper'),
            ('navbar', 'Navigation bar'),
            ('custom.css', 'Custom CSS included'),
        ]
        
        for css_class, description in css_checks:
            if css_class in content:
                print(f"[PASS] {description}: Found")
            else:
                print(f"[FAIL] {description}: Missing")
    else:
        print("[FAIL] base.html not found")
    
    print("\nTEST COMPLETE")
    print("=" * 50)
    print("NEXT STEPS:")
    print("1. Run: python manage.py runserver")
    print("2. Visit: http://localhost:8000")
    print("3. Check that all pages load with sidebar and proper layout")
    print("4. Test both desktop and mobile views")
    print("5. Verify that content is not hidden or overlapped")

if __name__ == '__main__':
    test_templates()
