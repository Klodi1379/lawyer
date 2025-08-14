#!/usr/bin/env python
"""
Test script to check if dashboard page loads correctly
"""
import requests
import time

def test_dashboard():
    """Test if the dashboard page loads without template errors"""
    print("Testing dashboard page...")
    
    # Wait a moment for server to be ready
    time.sleep(2)
    
    urls_to_test = [
        'http://localhost:8000/',  # Root dashboard
        'http://localhost:8000/dashboard/'  # Dashboard specific URL
    ]
    
    for url in urls_to_test:
        print(f"\nTesting URL: {url}")
        try:
            # Test the dashboard URL
            response = requests.get(url, timeout=10)
            
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                print("SUCCESS: Dashboard page loaded successfully!")
                # Check if the page contains expected content
                if 'Enhanced Dashboard' in response.text:
                    print("SUCCESS: Enhanced Dashboard content found")
                else:
                    print("WARNING: Enhanced Dashboard content not found")
                    
                # Check for template errors
                if 'TemplateSyntaxError' in response.text:
                    print("ERROR: Template syntax error found in response")
                    # Print part of the error for debugging
                    if "dashboard_filters" in response.text:
                        print("ERROR: dashboard_filters template tag error confirmed")
                else:
                    print("SUCCESS: No template syntax errors found")
                    
            elif response.status_code == 404:
                print("ERROR: Dashboard URL not found (404)")
            elif response.status_code == 500:
                print("ERROR: Server error (500) - check Django logs")
                # Try to extract error info from response
                if 'TemplateSyntaxError' in response.text:
                    print("ERROR: Template syntax error in server response")
            else:
                print(f"ERROR: Unexpected status code: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print("ERROR: Could not connect to Django server. Is it running?")
        except requests.exceptions.Timeout:
            print("ERROR: Request timed out")
        except Exception as e:
            print(f"ERROR: Unexpected error: {e}")

if __name__ == '__main__':
    test_dashboard()
