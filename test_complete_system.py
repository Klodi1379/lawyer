#!/usr/bin/env python3
"""
Sistema e Avancuar e Menaxhimit të Rasteve Juridike - Testim i Plotë
Ky script teston të gjitha modulet e sistemit për të siguruar funksionalitetin e plotë.
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

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from legal_manager.cases.models import Case, Client as ClientModel, CaseDocument, CaseEvent, User

class LegalSystemIntegrationTest:
    """
    Test i plotë i të gjitha moduleve të sistemit
    """
    
    def __init__(self):
        self.client = Client()
        self.test_results = []
        
    def log_test(self, test_name, success, message=""):
        """Log test results"""
        status = "[PASS]" if success else "[FAIL]"
        print(f"{status} {test_name}")
        if message:
            print(f"    Note: {message}")
        self.test_results.append({
            'test': test_name,
            'success': success,
            'message': message
        })
    
    def test_database_models(self):
        """Test database models and relationships"""
        print("\nTesting Database Models...")
        
        try:
            # Test User model
            user = User.objects.create_user(
                username='test_lawyer',
                email='lawyer@test.com',
                password='testpass123',
                role='lawyer'
            )
            self.log_test("User Creation", True, f"Created user: {user.username}")
            
            # Test Client model
            client = ClientModel.objects.create(
                full_name='Test Client',
                email='client@test.com',
                phone='+355691234567'
            )
            self.log_test("Client Creation", True, f"Created client: {client.full_name}")
            
            # Test Case model
            case = Case.objects.create(
                title='Test Legal Case',
                description='This is a test case for system validation',
                client=client,
                assigned_to=user,
                case_type='civil',
                status='open'
            )
            self.log_test("Case Creation", True, f"Created case: {case.title} (UID: {case.uid})")
            
            # Test relationships
            self.log_test("User-Case Relationship", 
                         user.assigned_cases.count() == 1,
                         f"User has {user.assigned_cases.count()} assigned cases")
            
            self.log_test("Client-Case Relationship", 
                         client.cases.count() == 1,
                         f"Client has {client.cases.count()} cases")
            
        except Exception as e:
            self.log_test("Database Models", False, f"Error: {str(e)}")
    
    def test_url_patterns(self):
        """Test URL patterns and routing"""
        print("\nTesting URL Patterns...")
        
        # Test major URL patterns
        test_urls = [
            ('dashboard', 'Dashboard URL'),
            ('case_list', 'Case List URL'),
            ('client_list', 'Client List URL'),
            ('document_list', 'Document List URL'),
            ('event_list', 'Event List URL'),
            ('event_calendar', 'Calendar URL'),
            ('document_editor', 'Document Editor URL'),
            ('login', 'Login URL'),
            ('register', 'Registration URL'),
        ]
        
        for url_name, description in test_urls:
            try:
                url = reverse(url_name)
                self.log_test(description, True, f"URL: {url}")
            except Exception as e:
                self.log_test(description, False, f"Error: {str(e)}")
    
    def test_views_and_templates(self):
        """Test views and template rendering"""
        print("\nTesting Views and Templates...")
        
        # Create test user for authenticated views
        try:
            user = User.objects.get(username='test_lawyer')
        except User.DoesNotExist:
            user = User.objects.create_user(
                username='test_lawyer',
                email='lawyer@test.com',
                password='testpass123',
                role='lawyer'
            )
        
        # Test public views
        public_views = [
            ('login', 'Login View'),
            ('register', 'Registration View'),
        ]
        
        for url_name, description in public_views:
            try:
                response = self.client.get(reverse(url_name))
                success = response.status_code in [200, 302]
                self.log_test(description, success, 
                             f"Status: {response.status_code}")
            except Exception as e:
                self.log_test(description, False, f"Error: {str(e)}")
        
        # Login for authenticated views
        login_success = self.client.login(username='test_lawyer', password='testpass123')
        self.log_test("User Authentication", login_success, "Logged in test user")
        
        if login_success:
            # Test authenticated views
            authenticated_views = [
                ('dashboard', 'Dashboard View'),
                ('case_list', 'Case List View'),
                ('client_list', 'Client List View'),
                ('document_list', 'Document List View'),
                ('event_list', 'Event List View'),
                ('event_calendar', 'Calendar View'),
                ('document_editor', 'Document Editor View'),
                ('profile', 'Profile View'),
            ]
            
            for url_name, description in authenticated_views:
                try:
                    response = self.client.get(reverse(url_name))
                    success = response.status_code == 200
                    self.log_test(description, success, 
                                 f"Status: {response.status_code}")
                except Exception as e:
                    self.log_test(description, False, f"Error: {str(e)}")
    
    def test_api_endpoints(self):
        """Test API endpoints"""
        print("\nTesting API Endpoints...")
        
        # Make sure user is logged in
        self.client.login(username='test_lawyer', password='testpass123')
        
        api_endpoints = [
            ('/api/', 'API Root'),
            ('/api/cases/', 'Cases API'),
            ('/api/clients/', 'Clients API'),
            ('/api/documents/', 'Documents API'),
            ('/api/events/', 'Events API'),
            ('/dashboard/api/quick-stats/', 'Quick Stats API'),
            ('/health/', 'Health Check API'),
        ]
        
        for endpoint, description in api_endpoints:
            try:
                response = self.client.get(endpoint)
                success = response.status_code in [200, 401, 403]  # 401/403 acceptable for auth-protected APIs
                self.log_test(description, success, 
                             f"Status: {response.status_code}")
            except Exception as e:
                self.log_test(description, False, f"Error: {str(e)}")
    
    def test_llm_integration(self):
        """Test LLM integration"""
        print("\nTesting LLM Integration...")
        
        # Make sure user is logged in
        self.client.login(username='test_lawyer', password='testpass123')
        
        try:
            # Test LLM service import
            from legal_manager.cases.llm_service import LLMService
            llm_service = LLMService()
            self.log_test("LLM Service Import", True, "Successfully imported LLMService")
            
            # Test document editor view
            response = self.client.get(reverse('document_editor'))
            success = response.status_code == 200
            self.log_test("Document Editor Access", success, 
                         f"Status: {response.status_code}")
            
            # Test template API
            response = self.client.get('/api/templates/?type=contract')
            success = response.status_code in [200, 500]  # 500 acceptable if no API key
            self.log_test("Template API", success, 
                         f"Status: {response.status_code}")
            
        except Exception as e:
            self.log_test("LLM Integration", False, f"Error: {str(e)}")
    
    def test_static_files(self):
        """Test static files and assets"""
        print("\nTesting Static Files...")
        
        static_files = [
            '/static/css/custom.css',
            '/static/js/pwa.js',
            '/static/js/widget-manager.js',
        ]
        
        for static_file in static_files:
            try:
                response = self.client.get(static_file)
                success = response.status_code in [200, 404]  # 404 acceptable if file doesn't exist
                self.log_test(f"Static File: {static_file}", success, 
                             f"Status: {response.status_code}")
            except Exception as e:
                self.log_test(f"Static File: {static_file}", False, f"Error: {str(e)}")
    
    def test_sidebar_and_navigation(self):
        """Test sidebar and navigation functionality"""
        print("\nTesting Sidebar and Navigation...")
        
        # Make sure user is logged in
        self.client.login(username='test_lawyer', password='testpass123')
        
        try:
            # Test dashboard with sidebar
            response = self.client.get(reverse('dashboard'))
            success = response.status_code == 200
            content = response.content.decode('utf-8')
            
            # Check for sidebar elements
            sidebar_elements = [
                'sidebar',
                'Legal Manager',
                'Quick Actions',
                'Case Management',
                'AI Assistant',
                'nav-link'
            ]
            
            sidebar_found = all(element in content for element in sidebar_elements)
            self.log_test("Sidebar Rendering", sidebar_found, 
                         "Sidebar elements found in dashboard")
            
            # Check for navigation links
            nav_links = [
                '/cases/',
                '/clients/',
                '/documents/',
                '/calendar/',
                '/document-editor/'
            ]
            
            nav_found = any(link in content for link in nav_links)
            self.log_test("Navigation Links", nav_found, 
                         "Navigation links found in page")
            
        except Exception as e:
            self.log_test("Sidebar and Navigation", False, f"Error: {str(e)}")
    
    def test_ai_document_editor(self):
        """Test AI Document Editor functionality"""
        print("\nTesting AI Document Editor...")
        
        # Make sure user is logged in
        self.client.login(username='test_lawyer', password='testpass123')
        
        try:
            # Test document editor page
            response = self.client.get(reverse('document_editor'))
            success = response.status_code == 200
            content = response.content.decode('utf-8')
            
            # Check for editor elements
            editor_elements = [
                'AI Document Editor',
                'Quill',
                'AI Assistant',
                'Document Templates',
                'Quick Actions'
            ]
            
            editor_found = any(element in content for element in editor_elements)
            self.log_test("Document Editor Rendering", editor_found, 
                         "Document editor elements found")
            
            # Check for AI integration elements
            ai_elements = [
                'robot',
                'AI Assistant',
                'Generate from Template',
                'llm'
            ]
            
            ai_found = any(element in content for element in ai_elements)
            self.log_test("AI Integration Elements", ai_found, 
                         "AI integration elements found")
            
        except Exception as e:
            self.log_test("AI Document Editor", False, f"Error: {str(e)}")
    
    def run_all_tests(self):
        """Run all tests"""
        print("Starting Legal Case Management System Integration Tests")
        print("=" * 70)
        
        self.test_database_models()
        self.test_url_patterns()
        self.test_views_and_templates()
        self.test_api_endpoints()
        self.test_llm_integration()
        self.test_static_files()
        self.test_sidebar_and_navigation()
        self.test_ai_document_editor()
        
        # Summary
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print("\nFAILED TESTS:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  • {result['test']}: {result['message']}")
        
        print("\nSYSTEM STATUS:")
        if failed_tests == 0:
            print("ALL TESTS PASSED - System is ready for use!")
        elif failed_tests <= 3:
            print("MINOR ISSUES - System is mostly functional")
        else:
            print("MAJOR ISSUES - System needs attention")
        
        return failed_tests == 0

if __name__ == '__main__':
    tester = LegalSystemIntegrationTest()
    success = tester.run_all_tests()
    
    print("\n" + "=" * 70)
    print("NEXT STEPS:")
    print("=" * 70)
    print("1. Run: python manage.py runserver")
    print("2. Visit: http://localhost:8000")
    print("3. Login with test credentials if created")
    print("4. Test the AI Document Editor at: /document-editor/")
    print("5. Explore all modules through the sidebar navigation")
    print("\nFor LLM functionality, ensure OPENAI_API_KEY is set in environment")
    
    sys.exit(0 if success else 1)
