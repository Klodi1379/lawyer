import pytest
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import Client as ClientModel, Case, CaseDocument, UserProfile
from .forms import UserRegistrationForm, CaseForm
import tempfile
from django.core.files.uploadedfile import SimpleUploadedFile

User = get_user_model()

class UserModelTest(TestCase):
    """Test cases for User model and related functionality."""
    
    def setUp(self):
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'role': 'lawyer'
        }
    
    def test_user_creation(self):
        """Test creating a user with custom role."""
        user = User.objects.create_user(
            username=self.user_data['username'],
            email=self.user_data['email'],
            password='testpass123',
            role=self.user_data['role']
        )
        
        self.assertEqual(user.username, self.user_data['username'])
        self.assertEqual(user.email, self.user_data['email'])
        self.assertEqual(user.role, self.user_data['role'])
        self.assertTrue(user.check_password('testpass123'))
    
    def test_user_profile_creation(self):
        """Test that UserProfile is created automatically."""
        user = User.objects.create_user(
            username='profiletest',
            email='profile@example.com',
            password='testpass123'
        )
        
        # Check if profile was created by signal
        self.assertTrue(hasattr(user, 'profile'))
        self.assertIsInstance(user.profile, UserProfile)
    
    def test_user_string_representation(self):
        """Test user string representation."""
        user = User.objects.create_user(
            username='stringtest',
            email='string@example.com',
            password='testpass123',
            role='admin'
        )
        
        expected_str = f"{user.username} ({user.role})"
        self.assertEqual(str(user), expected_str)

class ClientModelTest(TestCase):
    """Test cases for Client model."""
    
    def setUp(self):
        self.client_data = {
            'full_name': 'John Doe',
            'email': 'john@example.com',
            'phone': '+355691234567',
            'address': 'Tirana, Albania',
            'organization': 'ABC Company'
        }
    
    def test_client_creation(self):
        """Test creating a client."""
        client = ClientModel.objects.create(**self.client_data)
        
        self.assertEqual(client.full_name, self.client_data['full_name'])
        self.assertEqual(client.email, self.client_data['email'])
        self.assertEqual(client.phone, self.client_data['phone'])
        self.assertEqual(str(client), self.client_data['full_name'])

class CaseModelTest(TestCase):
    """Test cases for Case model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='lawyer1',
            email='lawyer@example.com',
            password='testpass123',
            role='lawyer'
        )
        
        self.client = ClientModel.objects.create(
            full_name='Jane Smith',
            email='jane@example.com',
            phone='+355691234567'
        )
        
        self.case_data = {
            'title': 'Contract Dispute Case',
            'description': 'A dispute over contract terms.',
            'client': self.client,
            'assigned_to': self.user,
            'case_type': 'commercial',
            'status': 'open'
        }
    
    def test_case_creation(self):
        """Test creating a case."""
        case = Case.objects.create(**self.case_data)
        
        self.assertEqual(case.title, self.case_data['title'])
        self.assertEqual(case.client, self.client)
        self.assertEqual(case.assigned_to, self.user)
        self.assertEqual(case.case_type, 'commercial')
        self.assertEqual(case.status, 'open')
        
        # Test UID auto-generation
        self.assertIsNotNone(case.uid)
        self.assertEqual(len(case.uid), 32)
    
    def test_case_string_representation(self):
        """Test case string representation."""
        case = Case.objects.create(**self.case_data)
        expected_str = f"{case.uid} - {case.title}"
        self.assertEqual(str(case), expected_str)

class UserRegistrationFormTest(TestCase):
    """Test cases for user registration form."""
    
    def test_valid_registration_form(self):
        """Test valid registration form."""
        form_data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'role': 'paralegal',
            'password1': 'strongpassword123',
            'password2': 'strongpassword123'
        }
        
        form = UserRegistrationForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_password_mismatch(self):
        """Test form with mismatched passwords."""
        form_data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'role': 'paralegal',
            'password1': 'strongpassword123',
            'password2': 'differentpassword123'
        }
        
        form = UserRegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('password2', form.errors)
    
    def test_duplicate_username(self):
        """Test form with existing username."""
        # Create existing user
        User.objects.create_user(
            username='existinguser',
            email='existing@example.com',
            password='testpass123'
        )
        
        form_data = {
            'username': 'existinguser',
            'email': 'newuser@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'role': 'client',
            'password1': 'strongpassword123',
            'password2': 'strongpassword123'
        }
        
        form = UserRegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)

class ViewsTest(TestCase):
    """Test cases for views."""
    
    def setUp(self):
        self.client_web = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role='lawyer'
        )
        self.case_client = ClientModel.objects.create(
            full_name='Test Client',
            email='client@example.com'
        )
    
    def test_login_view(self):
        """Test login view."""
        response = self.client_web.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Login')
    
    def test_registration_view(self):
        """Test registration view."""
        response = self.client_web.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Create Account')
    
    def test_dashboard_requires_login(self):
        """Test that dashboard requires login."""
        response = self.client_web.get(reverse('dashboard'))
        self.assertRedirects(response, '/login/?next=/')
    
    def test_dashboard_authenticated(self):
        """Test dashboard with authenticated user."""
        self.client_web.login(username='testuser', password='testpass123')
        response = self.client_web.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Welcome')
    
    def test_case_list_view(self):
        """Test case list view."""
        self.client_web.login(username='testuser', password='testpass123')
        response = self.client_web.get(reverse('case_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Case Management')
    
    def test_profile_view(self):
        """Test profile view."""
        self.client_web.login(username='testuser', password='testpass123')
        response = self.client_web.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Profile')

class APITest(TestCase):
    """Test cases for API endpoints."""
    
    def setUp(self):
        self.client_web = Client()
        self.user = User.objects.create_user(
            username='apiuser',
            email='api@example.com',
            password='testpass123',
            role='lawyer'
        )
        self.case_client = ClientModel.objects.create(
            full_name='API Test Client',
            email='apiclient@example.com'
        )
    
    def test_api_requires_authentication(self):
        """Test that API requires authentication."""
        response = self.client_web.get('/api/cases/')
        self.assertEqual(response.status_code, 401)
    
    def test_api_cases_list(self):
        """Test cases API list endpoint."""
        self.client_web.login(username='apiuser', password='testpass123')
        response = self.client_web.get('/api/cases/')
        self.assertEqual(response.status_code, 200)
    
    def test_api_clients_list(self):
        """Test clients API list endpoint."""
        self.client_web.login(username='apiuser', password='testpass123')
        response = self.client_web.get('/api/clients/')
        self.assertEqual(response.status_code, 200)

class DocumentUploadTest(TestCase):
    """Test cases for document upload functionality."""
    
    def setUp(self):
        self.client_web = Client()
        self.user = User.objects.create_user(
            username='docuser',
            email='doc@example.com',
            password='testpass123',
            role='lawyer'
        )
        self.case_client = ClientModel.objects.create(
            full_name='Document Test Client',
            email='docclient@example.com'
        )
        self.case = Case.objects.create(
            title='Document Test Case',
            client=self.case_client,
            assigned_to=self.user
        )
    
    def test_document_upload(self):
        """Test document upload via API."""
        self.client_web.login(username='docuser', password='testpass123')
        
        # Create a temporary file
        test_file = SimpleUploadedFile(
            "test_document.txt",
            b"This is a test document content.",
            content_type="text/plain"
        )
        
        response = self.client_web.post(
            f'/api/cases/{self.case.id}/add_document/',
            {
                'file': test_file,
                'title': 'Test Document'
            }
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            CaseDocument.objects.filter(
                case=self.case,
                title='Test Document'
            ).exists()
        )

@pytest.mark.django_db
class TestLLMService:
    """Test cases for LLM service functionality."""
    
    def test_llm_service_import(self):
        """Test that LLM service can be imported."""
        from cases.llm_service import LLMService
        service = LLMService()
        assert service is not None
    
    def test_llm_service_call_without_api_key(self):
        """Test LLM service call without API key."""
        from cases.llm_service import LLMService
        service = LLMService(api_key=None)
        result = service.call("Test prompt")
        assert 'error' in result
        assert 'not configured' in result['error']

@pytest.mark.django_db  
class TestPermissions:
    """Test cases for permission system."""
    
    def test_lawyer_permissions(self):
        """Test lawyer role permissions."""
        user = User.objects.create_user(
            username='lawyer_test',
            email='lawyer_test@example.com',
            password='testpass123',
            role='lawyer'
        )
        assert user.role == 'lawyer'
    
    def test_client_permissions(self):
        """Test client role permissions."""
        user = User.objects.create_user(
            username='client_test',
            email='client_test@example.com',
            password='testpass123',
            role='client'
        )
        assert user.role == 'client'
    
    def test_admin_permissions(self):
        """Test admin role permissions."""
        user = User.objects.create_user(
            username='admin_test',
            email='admin_test@example.com',
            password='testpass123',
            role='admin'
        )
        assert user.role == 'admin'

if __name__ == '__main__':
    pytest.main([__file__])
