#!/usr/bin/env python
"""
Legal Case Manager - Layout Test Script
========================================
Teston strukturën e re të layout-it dhe identifikon probleme të mundshme.
"""

import os
import sys
import subprocess
from pathlib import Path

def test_file_structure():
    """Test file structure dhe templates"""
    print("=> Testing file structure...")
    
    required_files = [
        'templates/base.html',
        'templates/partials/sidebar.html',
        'static/css/custom.css',
        'static/css/mobile-dashboard.css',
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    if missing_files:
        print(f"[ERROR] Missing files: {missing_files}")
        return False
    else:
        print("[OK] All required files found")
        return True

def test_template_syntax():
    """Test Django template syntax"""
    print("\n=> Testing template syntax...")
    
    try:
        # Simple syntax check për base.html
        with open('templates/base.html', 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check for common syntax errors
        errors = []
        
        # Check for unclosed tags
        if content.count('{% block') != content.count('{% endblock %}'):
            errors.append("Mismatched block tags")
            
        if content.count('{% if') > content.count('{% endif %}'):
            errors.append("Unclosed if statements")
            
        # Check for proper DOCTYPE
        if not content.strip().startswith('<!DOCTYPE html>'):
            errors.append("Missing or incorrect DOCTYPE")
            
        if errors:
            print(f"[ERROR] Template syntax errors: {errors}")
            return False
        else:
            print("[OK] Template syntax looks good")
            return True
            
    except Exception as e:
        print(f"[ERROR] Error reading template: {e}")
        return False

def test_css_structure():
    """Test CSS structure dhe syntax"""
    print("\n=> Testing CSS structure...")
    
    try:
        with open('static/css/custom.css', 'r', encoding='utf-8') as f:
            css_content = f.read()
            
        # Basic CSS syntax checks
        open_braces = css_content.count('{')
        close_braces = css_content.count('}')
        
        if open_braces != close_braces:
            print(f"[ERROR] CSS syntax error: {open_braces} opening braces, {close_braces} closing braces")
            return False
            
        # Check for key layout classes
        required_classes = [
            '.app-container',
            '.sidebar',
            '.main-content',
            '.sidebar-overlay'
        ]
        
        missing_classes = []
        for class_name in required_classes:
            if class_name not in css_content:
                missing_classes.append(class_name)
                
        if missing_classes:
            print(f"[ERROR] Missing CSS classes: {missing_classes}")
            return False
        else:
            print("[OK] CSS structure looks good")
            return True
            
    except Exception as e:
        print(f"[ERROR] Error reading CSS: {e}")
        return False

def test_responsive_breakpoints():
    """Test responsive design breakpoints"""
    print("\n=> Testing responsive breakpoints...")
    
    try:
        with open('static/css/custom.css', 'r', encoding='utf-8') as f:
            css_content = f.read()
            
        # Check for responsive breakpoints
        breakpoints = [
            '@media (max-width: 991.98px)',  # Mobile
            '@media (min-width: 992px)',     # Desktop
            '@media (max-width: 767.98px)',  # Small mobile
        ]
        
        missing_breakpoints = []
        for breakpoint in breakpoints:
            if breakpoint not in css_content:
                missing_breakpoints.append(breakpoint)
                
        if missing_breakpoints:
            print(f"[WARNING] Missing responsive breakpoints: {missing_breakpoints}")
        else:
            print("[OK] Responsive breakpoints found")
            
        return True
        
    except Exception as e:
        print(f"[ERROR] Error checking breakpoints: {e}")
        return False

def check_conflicts():
    """Check for potential CSS conflicts"""
    print("\n=> Checking for potential conflicts...")
    
    try:
        # Read both CSS files
        with open('static/css/custom.css', 'r', encoding='utf-8') as f:
            custom_css = f.read()
        with open('static/css/mobile-dashboard.css', 'r', encoding='utf-8') as f:
            mobile_css = f.read()
            
        conflicts = []
        
        # Check for duplicate sidebar definitions
        if custom_css.count('.sidebar {') > 1:
            conflicts.append("Multiple .sidebar definitions in custom.css")
            
        if '.sidebar {' in custom_css and '.sidebar {' in mobile_css:
            conflicts.append("Sidebar defined in both CSS files")
            
        # Check for conflicting positioning
        if 'position: fixed' in custom_css and 'position: fixed' in mobile_css:
            print("[INFO] Both CSS files use fixed positioning - check for conflicts")
            
        if conflicts:
            print(f"[WARNING] Potential conflicts found: {conflicts}")
        else:
            print("[OK] No obvious conflicts detected")
            
        return True
        
    except Exception as e:
        print(f"[ERROR] Error checking conflicts: {e}")
        return False

def generate_quick_test():
    """Generate a simple test to verify layout works"""
    print("\n=> Generating quick layout test...")
    
    test_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Quick Layout Test</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="static/css/custom.css">
    <style>
        .test-box { 
            background: #e3f2fd; 
            border: 2px solid #1976d2; 
            padding: 1rem; 
            margin: 1rem 0; 
            border-radius: 8px;
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-dark fixed-top">
        <div class="container-fluid">
            <button class="btn btn-outline-light d-lg-none" id="toggleBtn">Menu</button>
            <span class="navbar-brand">Layout Test</span>
        </div>
    </nav>
    
    <div class="app-container">
        <div class="sidebar-overlay" id="overlay"></div>
        
        <div class="sidebar" id="sidebar">
            <div class="sidebar-header">
                <h6>Test Sidebar</h6>
                <button class="btn btn-sm btn-outline-light d-lg-none" id="closeBtn">X</button>
            </div>
            <div class="sidebar-content">
                <div class="nav-link">Dashboard</div>
                <div class="nav-link">Cases</div>
                <div class="nav-link">Clients</div>
            </div>
        </div>
        
        <main class="main-content with-sidebar">
            <div class="content-wrapper">
                <div class="test-box">
                    <h2>Layout Test</h2>
                    <p>If you can see this properly, the layout is working!</p>
                    <button class="btn btn-primary" onclick="alert('Button works!')">Test Button</button>
                </div>
                
                <div class="test-box">
                    <h4>Instructions:</h4>
                    <ol>
                        <li>Resize window to test responsive behavior</li>
                        <li>On small screens, click Menu to open sidebar</li>
                        <li>Click X or outside to close sidebar</li>
                    </ol>
                </div>
            </div>
        </main>
    </div>
    
    <script>
        const toggle = document.getElementById('toggleBtn');
        const sidebar = document.getElementById('sidebar');
        const overlay = document.getElementById('overlay');
        const close = document.getElementById('closeBtn');
        
        toggle.onclick = () => {
            sidebar.classList.add('show');
            overlay.classList.add('show');
        };
        
        close.onclick = overlay.onclick = () => {
            sidebar.classList.remove('show');
            overlay.classList.remove('show');
        };
        
        console.log('Test script loaded successfully');
    </script>
</body>
</html>
    """
    
    try:
        with open('quick_test.html', 'w', encoding='utf-8') as f:
            f.write(test_content.strip())
        print("[OK] Quick test file created: quick_test.html")
        return True
    except Exception as e:
        print(f"[ERROR] Could not create test file: {e}")
        return False

def run_all_tests():
    """Run all tests"""
    print("Legal Case Manager - Layout Testing")
    print("=" * 50)
    
    all_passed = True
    
    # Test file structure
    if not test_file_structure():
        all_passed = False
    
    # Test template syntax
    if not test_template_syntax():
        all_passed = False
    
    # Test CSS structure
    if not test_css_structure():
        all_passed = False
    
    # Test responsive breakpoints
    if not test_responsive_breakpoints():
        all_passed = False
    
    # Check for conflicts
    if not check_conflicts():
        all_passed = False
    
    # Generate test file
    if not generate_quick_test():
        all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("[SUCCESS] All tests passed! Layout should be working correctly.")
        print("\nNext steps:")
        print("   1. Open quick_test.html in your browser")
        print("   2. Test responsive behavior by resizing window")
        print("   3. On mobile size, test sidebar toggle functionality")
        print("   4. Start Django server to test full application")
        print("\nTo start Django:")
        print("   python manage.py runserver")
    else:
        print("[FAILED] Some tests failed. Please fix the issues before proceeding.")
    
    return all_passed

if __name__ == "__main__":
    run_all_tests()
