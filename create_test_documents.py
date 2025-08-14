# create_test_documents.py - Skript për të krijuar test dokumente
import os
import sys
import django
from django.core.files.base import ContentFile

# Setup Django environment
if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'legal_manager.settings')
    django.setup()

from legal_manager.cases.models import User, Client, Case, CaseDocument

def create_test_data():
    """Krijo test data për dokumentet"""
    
    print("Creating test documents...")
    
    try:
        # Get or create test user
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@legalmanager.com',
                'role': 'admin',
                'is_staff': True,
                'is_superuser': True,
                'first_name': 'Admin',
                'last_name': 'User'
            }
        )
        
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            print(f"Created admin user: {admin_user.username}")
        
        # Get or create test client
        test_client, created = Client.objects.get_or_create(
            full_name='Test Client Ltd.',
            defaults={
                'email': 'client@testcompany.com',
                'phone': '+355691234567',
                'organization': 'Test Company Ltd.',
                'address': 'Rruga Deshmoret e Kombit, Tirane'
            }
        )
        
        if created:
            print(f"Created test client: {test_client.full_name}")
        
        # Get or create test case
        test_case, created = Case.objects.get_or_create(
            title='Commercial Dispute Case',
            defaults={
                'description': 'A test case involving commercial contract disputes',
                'client': test_client,
                'assigned_to': admin_user,
                'case_type': 'commercial',
                'status': 'open'
            }
        )
        
        if created:
            print(f"Created test case: {test_case.title}")
        
        # Create test documents
        test_documents = [
            {
                'title': 'Service Agreement Contract',
                'description': 'Main service agreement between parties',
                'doc_type': 'contract',
                'content': 'This is a sample service agreement contract...'
            },
            {
                'title': 'Legal Brief - Preliminary Motions',
                'description': 'Legal brief for preliminary motions',
                'doc_type': 'legal_brief',
                'content': 'This legal brief outlines the preliminary motions...'
            },
            {
                'title': 'Evidence - Email Correspondence',
                'description': 'Email evidence between parties',
                'doc_type': 'evidence',
                'content': 'Email correspondence showing breach of contract...'
            },
            {
                'title': 'Court Filing - Motion to Dismiss',
                'description': 'Motion to dismiss filed with court',
                'doc_type': 'court_filing',
                'content': 'Motion to dismiss the case for lack of jurisdiction...'
            },
            {
                'title': 'Client Correspondence',
                'description': 'Letter to client regarding case status',
                'doc_type': 'correspondence',
                'content': 'Dear Client, this letter provides an update...'
            },
            {
                'title': 'Expert Report - Financial Analysis',
                'description': 'Financial expert report on damages',
                'doc_type': 'report',
                'content': 'This expert report analyzes the financial damages...'
            }
        ]
        
        created_count = 0
        for doc_data in test_documents:
            # Check if document already exists
            if not CaseDocument.objects.filter(title=doc_data['title']).exists():
                # Create file content
                file_content = ContentFile(doc_data['content'].encode('utf-8'))
                
                # Create document
                document = CaseDocument.objects.create(
                    case=test_case,
                    uploaded_by=admin_user,
                    title=doc_data['title'],
                    description=doc_data['description'],
                    doc_type=doc_data['doc_type'],
                    status='draft',
                    file_size=len(doc_data['content'])
                )
                
                # Save file
                document.file.save(
                    f"{doc_data['title'].replace(' ', '_').lower()}.txt",
                    file_content,
                    save=True
                )
                
                created_count += 1
                print(f"Created document: {document.title}")
        
        print(f"\nTest data creation completed!")
        print(f"Summary:")
        print(f"   - Users: {User.objects.count()}")
        print(f"   - Clients: {Client.objects.count()}")
        print(f"   - Cases: {Case.objects.count()}")
        print(f"   - Documents: {CaseDocument.objects.count()}")
        print(f"   - New documents created: {created_count}")
        
        # Show document type breakdown
        print(f"\nDocument Types:")
        for doc_type, label in CaseDocument.DOCUMENT_TYPES:
            count = CaseDocument.objects.filter(doc_type=doc_type).count()
            print(f"   - {label}: {count}")
        
        return True
        
    except Exception as e:
        print(f"Error creating test data: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def show_access_info():
    """Show access information"""
    print(f"\nACCESS INFORMATION:")
    print(f"=" * 50)
    print(f"Web Interface:")
    print(f"   URL: http://127.0.0.1:50000/")
    print(f"   Documents: http://127.0.0.1:50000/documents/")
    print(f"   Admin: http://127.0.0.1:50000/admin/")
    print(f"")
    print(f"Admin Login:")
    print(f"   Username: admin")
    print(f"   Password: admin123")
    print(f"")
    print(f"API Endpoints:")
    print(f"   Documents API: http://127.0.0.1:50000/api/documents/")
    print(f"   Cases API: http://127.0.0.1:50000/api/cases/")
    print(f"   Users API: http://127.0.0.1:50000/api/users/")

if __name__ == '__main__':
    print("Legal Manager Test Data Creator")
    print("=" * 50)
    
    if create_test_data():
        show_access_info()
        print(f"\nReady to test the document system!")
    else:
        print(f"\nFailed to create test data")
        sys.exit(1)
