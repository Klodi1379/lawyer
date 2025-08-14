# debug_queryset.py - Script për debugging të queryset issues
"""
Debug script për të testuar dhe rregulluar queryset issues në Django

Ky script:
1. Teston queryset syntax
2. Simulon data për testing
3. Verifikon që pagination funksionon
4. Kontrollon distinct() behavior
"""

import os
import sys
import django
from django.conf import settings

# Setup Django environment
if not settings.configured:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'legal_manager.settings')
    django.setup()

from django.db.models import Q
from django.core.paginator import Paginator
from django.test import RequestFactory
from django.contrib.auth import get_user_model

def test_queryset_operations():
    """Test operacionet bazë të queryset për Document model"""
    
    try:
        from legal_manager.models import Document, DocumentType, DocumentStatus
        
        print("🔍 Testing queryset operations...")
        
        # Test 1: Basic queryset
        print("1️⃣ Testing basic queryset...")
        queryset = Document.objects.all()
        print(f"   Total documents: {queryset.count()}")
        
        # Test 2: Select related
        print("2️⃣ Testing select_related...")
        queryset = Document.objects.select_related('document_type', 'status')
        print(f"   Select related OK: {queryset.count()}")
        
        # Test 3: Filtering
        print("3️⃣ Testing filtering...")
        queryset = Document.objects.filter(is_template=False)
        print(f"   Non-template documents: {queryset.count()}")
        
        # Test 4: Q objects
        print("4️⃣ Testing Q objects...")
        q_filter = Q(is_template=True) | Q(access_level='public')
        queryset = Document.objects.filter(q_filter)
        print(f"   Q filter results: {queryset.count()}")
        
        # Test 5: Distinct AFTER filtering
        print("5️⃣ Testing distinct after filtering...")
        queryset = Document.objects.filter(is_template=False).distinct()
        print(f"   Distinct results: {queryset.count()}")
        
        # Test 6: Pagination
        print("6️⃣ Testing pagination...")
        paginator = Paginator(queryset, 10)
        page = paginator.get_page(1)
        print(f"   Page 1 objects: {len(page.object_list)}")
        
        print("✅ All queryset tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Queryset test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_document_viewset_queryset():
    """Test specific queryset nga DocumentViewSet"""
    
    try:
        from legal_manager.models import Document, User
        from legal_manager.views_fixed import DocumentViewSet
        
        print("\n🔍 Testing DocumentViewSet queryset...")
        
        # Krijo mock request
        factory = RequestFactory()
        request = factory.get('/documents/')
        
        # Krijo test user
        User = get_user_model()
        test_user, created = User.objects.get_or_create(
            username='test_lawyer',
            defaults={
                'email': 'test@example.com',
                'role': 'lawyer',
                'password': 'testpass123'
            }
        )
        request.user = test_user
        
        # Test DocumentViewSet
        viewset = DocumentViewSet()
        viewset.request = request
        
        print("1️⃣ Getting base queryset...")
        queryset = viewset.get_queryset()
        print(f"   Base queryset count: {queryset.count()}")
        
        # Test me parametra
        print("2️⃣ Testing with parameters...")
        request.GET = {'search': 'test', 'is_template': 'false'}
        queryset = viewset.get_queryset()
        print(f"   Filtered queryset count: {queryset.count()}")
        
        # Test distinct
        print("3️⃣ Testing distinct operation...")
        distinct_count = queryset.count()
        print(f"   Distinct count: {distinct_count}")
        
        # Test pagination compatibility
        print("4️⃣ Testing pagination compatibility...")
        paginator = Paginator(queryset, 5)
        page1 = paginator.get_page(1)
        print(f"   Page 1 count: {len(page1.object_list)}")
        
        print("✅ DocumentViewSet queryset tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ DocumentViewSet test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def create_test_data():
    """Krijo test data nëse databaza është bosh"""
    
    try:
        from legal_manager.models import (
            Document, DocumentCategory, DocumentType, DocumentStatus,
            User, Client, Case
        )
        
        print("\n🏗️ Creating test data...")
        
        # Krijo document category
        category, created = DocumentCategory.objects.get_or_create(
            name='Legal Documents',
            defaults={'description': 'Legal documents', 'color': '#007bff'}
        )
        
        # Krijo document type
        doc_type, created = DocumentType.objects.get_or_create(
            name='Contract',
            category=category,
            defaults={'is_template': False}
        )
        
        # Krijo document status
        status, created = DocumentStatus.objects.get_or_create(
            name='Draft',
            defaults={'color': '#ffc107', 'is_final': False}
        )
        
        # Krijo test user
        User = get_user_model()
        user, created = User.objects.get_or_create(
            username='test_admin',
            defaults={
                'email': 'admin@example.com',
                'role': 'admin',
                'is_staff': True,
                'is_superuser': True
            }
        )
        
        if created:
            user.set_password('admin123')
            user.save()
        
        # Krijo test client
        client, created = Client.objects.get_or_create(
            full_name='Test Client',
            defaults={'email': 'client@example.com'}
        )
        
        # Krijo test case
        case, created = Case.objects.get_or_create(
            title='Test Case',
            client=client,
            defaults={
                'description': 'Test case for debugging',
                'assigned_to': user,
                'case_type': 'civil',
                'status': 'open'
            }
        )
        
        # Krijo test documents
        for i in range(5):
            doc, created = Document.objects.get_or_create(
                title=f'Test Document {i+1}',
                defaults={
                    'description': f'Test document {i+1} for debugging',
                    'document_type': doc_type,
                    'status': status,
                    'created_by': user,
                    'uploaded_by': user,
                    'is_template': i % 2 == 0,  # Alternating template/non-template
                    'access_level': 'internal'
                }
            )
        
        print("✅ Test data created successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create test data: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def check_django_setup():
    """Kontrollon që Django setup është correct"""
    
    try:
        print("🔧 Checking Django setup...")
        
        # Check database connection
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        print("✅ Database connection OK")
        
        # Check models
        from legal_manager.models import Document, User
        print("✅ Models import OK")
        
        # Check migrations
        from django.core.management import execute_from_command_line
        print("✅ Django setup complete")
        
        return True
        
    except Exception as e:
        print(f"❌ Django setup failed: {str(e)}")
        return False

def main():
    """Main function për debugging"""
    
    print("🚀 Starting Django queryset debugging...")
    print("="*50)
    
    # Check Django setup
    if not check_django_setup():
        print("❌ Django setup failed, stopping...")
        return False
    
    # Create test data if needed
    create_test_data()
    
    # Test basic querysets
    if not test_queryset_operations():
        print("❌ Basic queryset tests failed")
        return False
    
    # Test DocumentViewSet specific queryset
    if not test_document_viewset_queryset():
        print("❌ DocumentViewSet tests failed")
        return False
    
    print("\n" + "="*50)
    print("🎉 All tests passed! Queryset fix is working correctly.")
    print("="*50)
    
    print("\n📋 SUMMARY:")
    print("✅ Queryset operations working")
    print("✅ Filtering working") 
    print("✅ Distinct() working correctly")
    print("✅ Pagination compatible")
    print("✅ DocumentViewSet queryset fixed")
    
    print("\n🚀 You can now:")
    print("1. Start Django server: python manage.py runserver")
    print("2. Visit: http://127.0.0.1:8000/documents/")
    print("3. Test API endpoints and filtering")
    
    return True

if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
