#!/usr/bin/env python
"""
Test script to check dashboard with authentication
"""
import requests
import time

def test_dashboard_with_auth():
    """Test dashboard access with authentication"""
    print("Testing dashboard with authentication...")
    
    # Wait for server to be ready
    time.sleep(2)
    
    session = requests.Session()
    
    # Test 1: Check if dashboard redirects to login
    print("\n1. Testing dashboard redirect...")
    try:
        response = session.get('http://localhost:8000/dashboard/', allow_redirects=False)
        print(f"Dashboard response status: {response.status_code}")
        
        if response.status_code == 302:
            print("SUCCESS: Dashboard requires authentication (redirects)")
            location = response.headers.get('Location', '')
            print(f"Redirect location: {location}")
        elif response.status_code == 200:
            print("INFO: Dashboard accessible without authentication")
        else:
            print(f"ERROR: Unexpected status: {response.status_code}")
    except Exception as e:
        print(f"ERROR: {e}")
    
    # Test 2: Check if login page exists
    print("\n2. Testing login page...")
    try:
        response = session.get('http://localhost:8000/login/')
        print(f"Login page status: {response.status_code}")
        
        if response.status_code == 200:
            print("SUCCESS: Login page accessible")
            if 'login' in response.text.lower() or 'username' in response.text.lower():
                print("SUCCESS: Login form found")
            else:
                print("WARNING: Login form not found")
        else:
            print(f"ERROR: Login page not accessible: {response.status_code}")
    except Exception as e:
        print(f"ERROR: {e}")
    
    # Test 3: Test direct access to dashboard after settings change
    print("\n3. Testing direct dashboard access...")
    try:
        response = session.get('http://localhost:8000/', allow_redirects=True)
        print(f"Root URL status: {response.status_code}")
        
        if response.status_code == 200:
            if 'TemplateSyntaxError' in response.text:
                print("ERROR: Template syntax error found!")
                if 'dashboard_filters' in response.text:
                    print("ERROR: dashboard_filters error confirmed")
                else:
                    print("ERROR: Other template error")
            else:
                print("SUCCESS: No template errors found")
                
            if 'Enhanced Dashboard' in response.text:
                print("SUCCESS: Dashboard content loaded")
            elif 'login' in response.text.lower():
                print("INFO: Redirected to login page")
            else:
                print("INFO: Other page content")
        else:
            print(f"ERROR: Request failed: {response.status_code}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == '__main__':
    test_dashboard_with_auth()
