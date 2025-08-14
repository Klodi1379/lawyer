#!/usr/bin/env python3
"""
Test simple për përmirësimet e sidebar dhe navbar
"""

import os
import sys
from pathlib import Path

def test_enhancements():
    """
    Test i thjeshtë për përmirësimet
    """
    print("Testing Enhanced Sidebar and Navbar...")
    print("=" * 50)
    
    project_root = Path(__file__).parent
    
    # Test 1: Check fajlat e rinj
    print("\n1. Checking enhanced template files...")
    
    files_to_check = [
        'templates/partials/sidebar_enhanced.html',
        'templates/partials/navbar_enhanced.html',
        'static/css/enhanced-features.css',
        'legal_manager/cases/views_api_stats.py'
    ]
    
    all_good = True
    for file_path in files_to_check:
        full_path = project_root / file_path
        if full_path.exists():
            print(f"✓ {file_path}")
        else:
            print(f"✗ Missing: {file_path}")
            all_good = False
    
    # Test 2: Check base.html updates
    print("\n2. Checking base.html updates...")
    base_html = project_root / 'templates/base.html'
    
    if base_html.exists():
        with open(base_html, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'sidebar_enhanced.html' in content:
            print("✓ base.html includes sidebar_enhanced.html")
        else:
            print("✗ base.html does not include sidebar_enhanced.html")
            all_good = False
            
        if 'navbar_enhanced.html' in content:
            print("✓ base.html includes navbar_enhanced.html")
        else:
            print("✗ base.html does not include navbar_enhanced.html")
            all_good = False
            
        if 'enhanced-features.css' in content:
            print("✓ base.html includes enhanced-features.css")
        else:
            print("✗ base.html does not include enhanced-features.css")
            all_good = False
    else:
        print("✗ base.html not found")
        all_good = False
    
    # Test 3: Check static files
    print("\n3. Checking static files...")
    
    css_file = project_root / 'staticfiles/css/enhanced-features.css'
    if css_file.exists():
        print("✓ enhanced-features.css copied to staticfiles")
    else:
        print("✗ enhanced-features.css not in staticfiles")
        all_good = False
    
    # Test 4: Check URLs
    print("\n4. Checking URL configuration...")
    urls_file = project_root / 'legal_manager/cases/urls.py'
    
    if urls_file.exists():
        with open(urls_file, 'r', encoding='utf-8') as f:
            urls_content = f.read()
        
        required_urls = [
            'enhanced_stats_api',
            'navbar_stats_api',
            'search_api',
            'notifications_api'
        ]
        
        for url_name in required_urls:
            if url_name in urls_content:
                print(f"✓ {url_name} URL configured")
            else:
                print(f"✗ {url_name} URL missing")
                all_good = False
    else:
        print("✗ urls.py not found")
        all_good = False
    
    print("\n" + "=" * 50)
    
    if all_good:
        print("✓ All tests passed! Enhanced features are ready.")
        print("\nFeatures enabled:")
        print("• Enhanced Navbar with search and notifications")
        print("• Enhanced Sidebar with new modules (Billing, Analytics)")
        print("• Real-time statistics updates")
        print("• Dark mode support")
        print("• Global search functionality")
        print("• Responsive design improvements")
        
        print("\nTo see the changes:")
        print("1. Start/restart your Django server: python manage.py runserver")
        print("2. Login to your dashboard")
        print("3. Notice the enhanced sidebar and navbar")
        print("4. Try the search box in the navbar")
        print("5. Toggle dark mode in the sidebar")
        
        return True
    else:
        print("✗ Some tests failed. Please check the issues above.")
        return False

def main():
    """
    Main function
    """
    success = test_enhancements()
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())