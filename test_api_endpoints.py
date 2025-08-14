#!/usr/bin/env python3
"""
Test script për API endpoints që dikur shikonin gabime
"""

import requests
import json

def test_api_endpoints():
    """Test API endpoints lokalisht"""
    print("🧪 Testing API Endpoints...")
    print("=" * 50)
    
    base_url = "http://127.0.0.1:8000"
    
    # API endpoints për të testuar
    endpoints = [
        "/api/dashboard/enhanced-stats/",
        "/api/dashboard/navbar-stats/", 
        "/api/dashboard/quick-stats/",
        "/api/notifications/",
    ]
    
    # Session për cookies
    session = requests.Session()
    
    for endpoint in endpoints:
        url = base_url + endpoint
        print(f"\n📡 Testing: {endpoint}")
        
        try:
            # Kjo do të kthejë 302 redirect ose 403 nëse nuk jemi logged in
            # Por duhet të mos ketë 500 Internal Server Error
            response = session.get(url, timeout=5, allow_redirects=False)
            
            if response.status_code == 500:
                print(f"❌ ERROR 500: Internal Server Error")
                print(f"   URL: {url}")
            elif response.status_code == 302:
                print(f"✅ OK: Redirects to login (expected for unauthenticated)")
            elif response.status_code == 403:
                print(f"✅ OK: Forbidden (expected for unauthenticated)")
            elif response.status_code == 404:
                print(f"⚠️  WARNING: 404 Not Found - endpoint may not exist")
            else:
                print(f"✅ OK: Status {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print(f"❌ ERROR: Cannot connect to server at {base_url}")
            print("   Make sure Django development server is running:")
            print("   python manage.py runserver")
            break
        except requests.exceptions.Timeout:
            print(f"❌ ERROR: Request timeout")
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
    
    print("\n" + "=" * 50)
    print("🏁 Test completed!")
    print("\nIf you see ✅ or redirects, the APIs are working correctly.")
    print("❌ means there are still server errors that need fixing.")

def test_template_urls():
    """Test template URLs"""
    print("\n🌐 Testing Template URLs...")
    print("=" * 50)
    
    base_url = "http://127.0.0.1:8000"
    
    # Template URLs për të testuar  
    template_urls = [
        "/billing/",
        "/analytics/", 
        "/portal/",
    ]
    
    session = requests.Session()
    
    for url_path in template_urls:
        url = base_url + url_path
        print(f"\n📄 Testing: {url_path}")
        
        try:
            response = session.get(url, timeout=5, allow_redirects=False)
            
            if response.status_code == 500:
                print(f"❌ ERROR 500: Internal Server Error")
            elif response.status_code == 302:
                print(f"✅ OK: Redirects to login (expected)")
            elif response.status_code == 403:
                print(f"✅ OK: Forbidden (expected for unauthenticated)")
            elif response.status_code == 404:
                print(f"❌ ERROR: 404 Not Found - URL pattern may not exist")
            elif response.status_code == 200:
                print(f"✅ OK: Page loads successfully")
            else:
                print(f"ℹ️  Status: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print(f"❌ ERROR: Cannot connect to server")
            break
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")

if __name__ == "__main__":
    print("🚀 Starting API and Template Tests")
    print("Make sure Django server is running: python manage.py runserver")
    print("=" * 60)
    
    # Test API endpoints
    test_api_endpoints()
    
    # Test template URLs
    test_template_urls()
    
    print("\n📝 Summary:")
    print("- APIs should redirect or return 403 (not 500)")
    print("- Templates should redirect or return 403 (not 404/500)")
    print("- No 500 Internal Server Errors = SUCCESS! ✅")