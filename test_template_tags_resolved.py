#!/usr/bin/env python
"""
Test script to diagnose template tag loading issues
"""
import os
import sys
import django

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'legal_manager.settings')
django.setup()

def test_template_tag_loading():
    """Test if template tags can be loaded properly"""
    print("Testing template tag loading...")
    
    # Test 1: Check if app is in INSTALLED_APPS
    from django.conf import settings
    print(f"INSTALLED_APPS: {settings.INSTALLED_APPS}")
    
    # Test 2: Check if template tag library can be discovered
    from django.template.backends.django import get_installed_libraries
    libraries = get_installed_libraries()
    print(f"Available template libraries: {list(libraries.keys())}")
    
    if 'dashboard_filters' in libraries:
        print("SUCCESS: dashboard_filters found in installed libraries")
    else:
        print("ERROR: dashboard_filters NOT found in installed libraries")
    
    # Test 3: Try to import the module directly
    try:
        from legal_manager.cases.templatetags import dashboard_filters
        print("SUCCESS: Direct import of dashboard_filters successful")
    except Exception as e:
        print(f"ERROR: Direct import failed: {e}")
    
    # Test 4: Try to load via Django's template system
    try:
        from django.template.library import import_library
        lib = import_library('dashboard_filters')
        print("SUCCESS: Django template library loading successful")
    except Exception as e:
        print(f"ERROR: Django template library loading failed: {e}")
    
    # Test 5: Try to render a simple template
    try:
        from django.template import Template, Context
        template_string = """{% load dashboard_filters %}{{ "test_value"|underscore_to_space }}"""
        template = Template(template_string)
        result = template.render(Context({}))
        print(f"SUCCESS: Template rendering successful: {result.strip()}")
    except Exception as e:
        print(f"ERROR: Template rendering failed: {e}")

if __name__ == '__main__':
    test_template_tag_loading()
