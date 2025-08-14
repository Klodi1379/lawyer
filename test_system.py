# test_system.py - Skript për testimin e sistemit të përmirësuar
import os
import sys
import django
from datetime import datetime, timedelta
from django.core.files.base import ContentFile
from django.test import TestCase, Client
from django.contrib.auth import authenticate
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
import json

# Setup Django environment (nëse run standalone)
if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'legal_manager.settings')
    django.setup()

from models_improved import (
    User, Client as ClientModel, Case, Document, DocumentCategory, 
    DocumentType, DocumentStatus, DocumentCaseRelation, DocumentAccess
)

class SystemTestCase(TestCase):
    """Test i plotë i sistemit të menaxhimit të dokumenteve"""
    
    def setUp(self):
        """Setup të dhënat e testimit"""
        print("🔧 Setting up test data...")
        
        # Krijo users
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='testpass123',
            role='admin',
            first_name='Admin',
            last_name='User'
        )
        
        self.lawyer_user = User.objects.create_user(
            username='lawyer1',
            email='lawyer@test.com',
            password='testpass123',
            role='lawyer',
            first_name='John',
            last_name='Lawyer'
        )
        
        self.client_user = User.objects.create_user(
            username='client1',
            email='client@test.com',
            password='testpass123',
            role='client',
            first_name='Jane',
            last_name='Client'
        )
        
        # Krijo client
        self.client_obj = ClientModel.objects.create(
            full_name='Test Client Company',
            email='client@company.com',
            phone='+355691234567',
            organization='Test Company Ltd'
        )
        
        # Krijo case
        self.case = Case.objects.create(
            title='Test Litigation Case',
            description='A test case for litigation purposes',
            client=self.client_obj,
            assigned_to=self.lawyer_user,
            case_type='civil',
            status='open'
        )
        
        # Krijo document categories dhe types
        self.legal_category = DocumentCategory.objects.create(
            name='Legal Documents',
            description='Official legal documents',
            color='#007bff'
        )
        
        self.template_category = DocumentCategory.objects.create(
            name='Templates',
            description='Document templates',
            color='#28a745'
        )
        
        self.contract_type = DocumentType.objects.create(
            name='Contract',
            category=self.legal_category,
            is_template=False
        )
        
        self.template_type = DocumentType.objects.create(
            name='Contract Template',
            category=self.template_category,
            is_template=True
        )
        
        # Krijo document statuses
        self.draft_status = DocumentStatus.objects.create(
            name='Draft',
            color='#ffc107',
            is_final=False
        )
        
        self.final_status = DocumentStatus.objects.create(
            name='Final',
            color='#28a745',
            is_final=True
        )
        
        # Setup API client
        self.api_client = APIClient()
        
        print("✅ Test data setup complete!")
    
    def test_user_authentication(self):
        """Test user authentication"""
        print("\n🔐 Testing user authentication...")
        
        # Test login
        response = self.api_client.post('/api/auth/login/', {
            'username': 'lawyer1',
            'password': 'testpass123'
        })
        
        self.assertEqual(response.status_code, 200)
        print("✅ User authentication successful")
    
    def test_document_without_case(self):
        """Test krijimin e dokumentit pa case (template ose i përgjithshëm)"""
        print("\n📄 Testing document creation without case...")
        
        # Authenticate si lawyer
        self.api_client.force_authenticate(user=self.lawyer_user)
        
        # Krijo një template
        template_data = {
            'title': 'Standard Contract Template',
            'description': 'A standard contract template for client agreements',
            'document_type': self.template_type.id,
            'status': self.draft_status.id,
            'is_template': True,
            'access_level': 'internal',
            'template_variables': json.dumps({
                'client_name': 'Client Name Placeholder',
                'contract_date': 'Date Placeholder',
                'amount': 'Amount Placeholder'
            }),
            'tags': 'template, contract, standard'
        }
        
        # Krijo file content
        file_content = ContentFile(
            b'This is a contract template with placeholders for {{client_name}}, {{contract_date}}, and {{amount}}.',
            name='contract_template.txt'
        )
        template_data['file'] = file_content
        
        response = self.api_client.post('/api/documents/', template_data, format='multipart')
        
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['is_template'])
        self.assertIsNone(response.data.get('case'))  # Nuk duhet të ketë case
        
        template_id = response.data['id']
        print(f"✅ Template created successfully with ID: {template_id}")
        
        return template_id
    
    def test_document_with_case(self):
        """Test krijimin e dokumentit me case"""
        print("\n📄 Testing document creation with case...")
        
        # Authenticate si lawyer
        self.api_client.force_authenticate(user=self.lawyer_user)
        
        # Krijo dokument të lidhur me case
        document_data = {
            'title': 'Client Agreement Contract',
            'description': 'Contract between law firm and client',
            'document_type': self.contract_type.id,
            'status': self.draft_status.id,
            'is_template': False,
            'access_level': 'confidential',
            'tags': 'contract, client, agreement'
        }
        
        # Krijo file content
        file_content = ContentFile(
            b'This is a client agreement contract for the specific case.',
            name='client_contract.txt'
        )
        document_data['file'] = file_content
        
        response = self.api_client.post('/api/documents/', document_data, format='multipart')
        
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.data['is_template'])
        
        document_id = response.data['id']
        print(f"✅ Document created successfully with ID: {document_id}")
        
        # Tani lidh dokumentin me case
        self.test_link_document_to_case(document_id)
        
        return document_id
    
    def test_link_document_to_case(self, document_id):
        """Test lidhjen e dokumentit me case"""
        print(f"\n🔗 Testing linking document {document_id} to case...")
        
        # Lidh dokumentin me case
        response = self.api_client.post(f'/api/cases/{self.case.id}/add-document/', {
            'document_id': document_id,
            'relationship_type': 'primary'
        })
        
        self.assertEqual(response.status_code, 200)
        
        # Verifiko që lidhja është krijuar
        relation = DocumentCaseRelation.objects.filter(
            document_id=document_id,
            case=self.case
        ).first()
        
        self.assertIsNotNone(relation)
        self.assertEqual(relation.relationship_type, 'primary')
        print("✅ Document linked to case successfully")
    
    def test_create_document_from_template(self):
        """Test krijimin e dokumentit nga template"""
        print("\n🎯 Testing document creation from template...")
        
        # Së pari krijo template
        template_id = self.test_document_without_case()
        
        # Tani krijo dokument nga template
        response = self.api_client.post('/api/documents/create-from-template/', {
            'template_id': template_id,
            'title': 'Contract for Test Client',
            'case_id': self.case.id,
            'template_variables': json.dumps({
                'client_name': 'Test Client Company',
                'contract_date': '2024-01-15',
                'amount': '$5,000'
            })
        })
        
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.data['is_template'])
        self.assertEqual(response.data['title'], 'Contract for Test Client')
        
        # Verifiko që është i lidhur me case
        new_document_id = response.data['id']
        relation = DocumentCaseRelation.objects.filter(
            document_id=new_document_id,
            case=self.case
        ).first()
        
        self.assertIsNotNone(relation)
        self.assertEqual(relation.relationship_type, 'template_used')
        print("✅ Document created from template and linked to case successfully")
    
    def test_document_access_control(self):
        """Test kontrollin e aksesit në dokumente"""
        print("\n🔒 Testing document access control...")
        
        # Krijo dokument si lawyer
        document_id = self.test_document_with_case()
        
        # Provo aksesin si client (duhet të refuzohet)
        self.api_client.force_authenticate(user=self.client_user)
        
        response = self.api_client.get(f'/api/documents/{document_id}/')
        self.assertEqual(response.status_code, 403)  # Forbidden
        print("✅ Access properly denied for unauthorized user")
        
        # Jep akses si admin
        self.api_client.force_authenticate(user=self.admin_user)
        
        response = self.api_client.post(f'/api/documents/{document_id}/grant-access/', {
            'user_id': self.client_user.id,
            'permissions': {
                'can_view': True,
                'can_download': True,
                'can_edit': False,
                'can_delete': False
            }
        })
        
        self.assertEqual(response.status_code, 200)
        print("✅ Access granted successfully")
        
        # Tani provo aksesin si client (duhet të lejohet)
        self.api_client.force_authenticate(user=self.client_user)
        
        response = self.api_client.get(f'/api/documents/{document_id}/')
        self.assertEqual(response.status_code, 200)
        print("✅ Access properly allowed after permission grant")
    
    def test_document_search_and_filter(self):
        """Test search dhe filter functionality"""
        print("\n🔍 Testing document search and filtering...")
        
        self.api_client.force_authenticate(user=self.lawyer_user)
        
        # Krijo disa dokumente për test
        self.test_document_without_case()  # Template
        self.test_document_with_case()     # Document me case
        
        # Test search by title
        response = self.api_client.get('/api/documents/', {'search': 'contract'})
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.data['results']), 0)
        print("✅ Search functionality working")
        
        # Test filter by template
        response = self.api_client.get('/api/documents/', {'is_template': 'true'})
        self.assertEqual(response.status_code, 200)
        templates = [doc for doc in response.data['results'] if doc['is_template']]
        self.assertGreater(len(templates), 0)
        print("✅ Template filtering working")
        
        # Test filter by case
        response = self.api_client.get('/api/documents/', {'case': self.case.id})
        self.assertEqual(response.status_code, 200)
        case_docs = response.data['results']
        self.assertGreater(len(case_docs), 0)
        print("✅ Case filtering working")
    
    def test_bulk_operations(self):
        """Test bulk operations në dokumente"""
        print("\n📦 Testing bulk operations...")
        
        self.api_client.force_authenticate(user=self.admin_user)
        
        # Krijo disa dokumente
        doc1_id = self.test_document_without_case()
        doc2_id = self.test_document_with_case()
        
        # Test bulk status change
        response = self.api_client.post('/api/documents/bulk-action/', {
            'document_ids': [doc1_id, doc2_id],
            'action': 'change_status',
            'new_status': self.final_status.id
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['success'], 2)
        self.assertEqual(response.data['failed'], 0)
        print("✅ Bulk status change successful")
    
    def run_all_tests(self):
        """Ekzekuto të gjitha testet"""
        print("🚀 Starting comprehensive system tests...\n")
        
        try:
            self.test_user_authentication()
            self.test_document_without_case()
            self.test_document_with_case()
            self.test_create_document_from_template()
            self.test_document_access_control()
            self.test_document_search_and_filter()
            self.test_bulk_operations()
            
            print("\n🎉 All tests passed successfully!")
            return True
            
        except Exception as e:
            print(f"\n❌ Test failed with error: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

# ==========================================
# STANDALONE TEST RUNNER
# ==========================================

def run_standalone_tests():
    """Run tests standalone (jo Django test suite)"""
    from django.test.utils import setup_test_environment, teardown_test_environment
    from django.test.runner import DiscoverRunner
    from django.conf import settings
    
    # Setup test environment
    setup_test_environment()
    
    # Create test database
    test_runner = DiscoverRunner(verbosity=2, interactive=True, keepdb=False)
    old_config = test_runner.setup_databases()
    
    try:
        # Run tests
        test_case = SystemTestCase()
        test_case.setUp()
        result = test_case.run_all_tests()
        
        return result
        
    finally:
        # Cleanup
        test_runner.teardown_databases(old_config)
        teardown_test_environment()

# ==========================================
# DATA INITIALIZATION SCRIPT
# ==========================================

def initialize_test_data():
    """Inicializo të dhëna test në database"""
    print("🏗️  Initializing test data in database...")
    
    # Krijo categories
    categories = [
        {'name': 'Legal Documents', 'description': 'Official legal documents', 'color': '#007bff'},
        {'name': 'Templates', 'description': 'Document templates', 'color': '#28a745'},
        {'name': 'Internal', 'description': 'Internal documents', 'color': '#6c757d'},
        {'name': 'Client Communications', 'description': 'Communications with clients', 'color': '#fd7e14'},
    ]
    
    for cat_data in categories:
        category, created = DocumentCategory.objects.get_or_create(
            name=cat_data['name'],
            defaults=cat_data
        )
        if created:
            print(f"✅ Created category: {category.name}")
    
    # Krijo document types
    types_data = [
        {'name': 'Contract', 'category': 'Legal Documents', 'is_template': False},
        {'name': 'Contract Template', 'category': 'Templates', 'is_template': True},
        {'name': 'Legal Brief', 'category': 'Legal Documents', 'is_template': False},
        {'name': 'Client Letter', 'category': 'Client Communications', 'is_template': False},
        {'name': 'Letter Template', 'category': 'Templates', 'is_template': True},
        {'name': 'Internal Memo', 'category': 'Internal', 'is_template': False},
    ]
    
    for type_data in types_data:
        category = DocumentCategory.objects.get(name=type_data['category'])
        doc_type, created = DocumentType.objects.get_or_create(
            name=type_data['name'],
            category=category,
            defaults={'is_template': type_data['is_template']}
        )
        if created:
            print(f"✅ Created document type: {doc_type.name}")
    
    # Krijo statuses
    statuses = [
        {'name': 'Draft', 'color': '#ffc107', 'is_final': False},
        {'name': 'Review', 'color': '#17a2b8', 'is_final': False},
        {'name': 'Final', 'color': '#28a745', 'is_final': True},
        {'name': 'Signed', 'color': '#6f42c1', 'is_final': True},
        {'name': 'Archived', 'color': '#6c757d', 'is_final': True},
    ]
    
    for status_data in statuses:
        status_obj, created = DocumentStatus.objects.get_or_create(
            name=status_data['name'],
            defaults=status_data
        )
        if created:
            print(f"✅ Created status: {status_obj.name}")
    
    # Krijo default admin user nëse nuk ekziston
    if not User.objects.filter(username='admin').exists():
        admin_user = User.objects.create_user(
            username='admin',
            email='admin@legalmanager.com',
            password='admin123',
            role='admin',
            first_name='System',
            last_name='Administrator'
        )
        print(f"✅ Created admin user: {admin_user.username}")
    
    print("🎉 Test data initialization complete!")

if __name__ == '__main__':
    # Kontrollo arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == 'init':
            initialize_test_data()
        elif sys.argv[1] == 'test':
            run_standalone_tests()
        else:
            print("Usage: python test_system.py [init|test]")
            print("  init - Initialize test data")
            print("  test - Run system tests")
    else:
        print("Available commands:")
        print("  python test_system.py init  - Initialize test data")
        print("  python test_system.py test  - Run system tests")
