"""
Tests për Document Editor Module
Përfshin unit tests, integration tests dhe functional tests
"""

import json
import tempfile
from unittest.mock import patch, Mock
from datetime import datetime, timedelta

from django.test import TestCase, TransactionTestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from django.db import transaction
from django.test.utils import override_settings

from .models.document_models import (
    Document, DocumentTemplate, DocumentType, DocumentStatus,
    DocumentVersion, DocumentComment, DocumentEditor, 
    LLMInteraction, DocumentAuditLog
)
from .services.document_service import DocumentEditingService
from .services.llm_service import LegalLLMService, DocumentContext
from .forms import DocumentForm, DocumentTemplateForm, DocumentCommentForm

User = get_user_model()

class DocumentModelTest(TestCase):
    """Teste për modelet e dokumenteve"""
    
    def setUp(self):
        self.user_admin = User.objects.create_user(
            username='admin_user',
            email='admin@example.com',
            password='testpass123',
            role='admin'
        )
        self.user_lawyer = User.objects.create_user(
            username='lawyer_user',
            email='lawyer@example.com',
            password='testpass123',
            role='lawyer'
        )
        self.user_client = User.objects.create_user(
            username='client_user',
            email='client@example.com',
            password='testpass123',
            role='client'
        )
        
        # Krijo objekte të nevojshme
        self.doc_type = DocumentType.objects.create(
            name='Kontratë',
            description='Kontratë e përgjithshme'
        )
        self.doc_status = DocumentStatus.objects.create(
            name='Draft',
            description='Në përgatitje',
            color='#ffc107'
        )
        
        # Krijo një rast për test (duhet të ekzistojë modeli Case)
        try:
            from cases.models import Case, Client
            self.client_obj = Client.objects.create(
                full_name='Test Client',
                email='client@test.com'
            )
            self.case = Case.objects.create(
                title='Test Case',
                description='Test case për dokumente',
                client=self.client_obj,
                assigned_to=self.user_lawyer
            )
        except ImportError:
            # Nëse nuk ekziston modeli Case, krijo mock
            self.case = None

    def test_document_creation(self):
        """Test krijimi i dokumentit"""
        document = Document.objects.create(
            title='Test Document',
            description='Dokument për test',
            case=self.case,
            document_type=self.doc_type,
            status=self.doc_status,
            content='Përmbajtja e testit',
            created_by=self.user_lawyer,
            owned_by=self.user_lawyer
        )
        
        self.assertTrue(document.uid)  # UUID duhet të gjenerohej automatikisht
        self.assertEqual(document.version_number, 1)
        self.assertEqual(str(document), f"{document.uid} - Test Document")
        self.assertTrue(document.can_edit(self.user_lawyer))
        self.assertFalse(document.can_edit(self.user_client))

    def test_document_versioning(self):
        """Test version control i dokumentit"""
        document = Document.objects.create(
            title='Versioned Document',
            content='Versioni i parë',
            case=self.case,
            document_type=self.doc_type,
            status=self.doc_status,
            created_by=self.user_lawyer,
            owned_by=self.user_lawyer
        )
        
        # Krijo version të ri
        new_version = document.create_new_version(
            user=self.user_lawyer,
            reason="Përditësim i përmbajtjes"
        )
        
        self.assertEqual(new_version.version_number, 2)
        self.assertEqual(new_version.parent_document, document)

    def test_document_locking(self):
        """Test bllokimi/çbllokimi i dokumentit"""
        document = Document.objects.create(
            title='Lockable Document',
            case=self.case,
            document_type=self.doc_type,
            status=self.doc_status,
            created_by=self.user_lawyer,
            owned_by=self.user_lawyer
        )
        
        # Blloko dokumentin
        success = document.lock_document(self.user_lawyer)
        self.assertTrue(success)
        self.assertTrue(document.is_locked)
        self.assertEqual(document.locked_by, self.user_lawyer)
        
        # Provo të bllokosh nga përdorues tjetër
        success = document.lock_document(self.user_admin)
        self.assertFalse(success)
        
        # Çblloko
        success = document.unlock_document(self.user_lawyer)
        self.assertTrue(success)
        self.assertFalse(document.is_locked)

    def test_document_permissions(self):
        """Test permissions e dokumentit"""
        document = Document.objects.create(
            title='Permission Test Document',
            case=self.case,
            document_type=self.doc_type,
            status=self.doc_status,
            created_by=self.user_lawyer,
            owned_by=self.user_lawyer
        )
        
        # Owner mund të editojë
        self.assertTrue(document.can_edit(self.user_lawyer))
        
        # Përdorues tjetër nuk mund të editojë
        self.assertFalse(document.can_edit(self.user_client))
        
        # Shto si editor
        DocumentEditor.objects.create(
            document=document,
            user=self.user_admin,
            permission_level='edit',
            added_by=self.user_lawyer
        )
        
        self.assertTrue(document.can_edit(self.user_admin))

class DocumentTemplateTest(TestCase):
    """Teste për template-at e dokumenteve"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='template_user',
            password='testpass123',
            role='lawyer'
        )

    def test_template_creation(self):
        """Test krijimi i template"""
        template = DocumentTemplate.objects.create(
            name='Kontratë Standarde',
            description='Template për kontrata standarde',
            category='Kontrata',
            content='Kjo është një kontratë midis {palë_e_parë} dhe {palë_e_dytë}.',
            variables={'palë_e_parë': 'Kompania', 'palë_e_dytë': 'Klienti'},
            created_by=self.user
        )
        
        self.assertEqual(template.name, 'Kontratë Standarde')
        self.assertEqual(template.category, 'Kontrata')
        self.assertTrue(template.is_active)
        self.assertEqual(str(template), 'Kontrata - Kontratë Standarde')

class DocumentCommentTest(TestCase):
    """Teste për komentet e dokumenteve"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='comment_user',
            password='testpass123',
            role='lawyer'
        )
        
        self.doc_type = DocumentType.objects.create(name='Test Type')
        self.doc_status = DocumentStatus.objects.create(name='Draft')
        
        self.document = Document.objects.create(
            title='Commented Document',
            document_type=self.doc_type,
            status=self.doc_status,
            created_by=self.user,
            owned_by=self.user
        )

    def test_comment_creation(self):
        """Test krijimi i komentit"""
        comment = DocumentComment.objects.create(
            document=self.document,
            content='Ky është një koment test',
            author=self.user,
            position_start=10,
            position_end=20,
            selected_text='tekst i zgjedhur'
        )
        
        self.assertEqual(comment.content, 'Ky është një koment test')
        self.assertEqual(comment.author, self.user)
        self.assertFalse(comment.is_resolved)

    def test_comment_resolution(self):
        """Test zgjidhja e komentit"""
        comment = DocumentComment.objects.create(
            document=self.document,
            content='Koment për zgjidhje',
            author=self.user
        )
        
        # Zgjidh komentin
        comment.is_resolved = True
        comment.resolved_by = self.user
        comment.resolved_at = timezone.now()
        comment.save()
        
        self.assertTrue(comment.is_resolved)
        self.assertEqual(comment.resolved_by, self.user)
        self.assertIsNotNone(comment.resolved_at)

class DocumentServiceTest(TestCase):
    """Teste për DocumentEditingService"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='service_user',
            password='testpass123',
            role='lawyer'
        )
        
        self.doc_type = DocumentType.objects.create(name='Service Test Type')
        self.doc_status = DocumentStatus.objects.create(name='Draft')
        
        self.document = Document.objects.create(
            title='Service Test Document',
            content='Përmbajtja origjinale',
            document_type=self.doc_type,
            status=self.doc_status,
            created_by=self.user,
            owned_by=self.user
        )
        
        self.service = DocumentEditingService()

    def test_get_document_for_editing(self):
        """Test marrja e dokumentit për editim"""
        doc = self.service.get_document_for_editing(self.document.id, self.user)
        
        self.assertEqual(doc.id, self.document.id)
        self.assertTrue(doc.is_locked)
        self.assertEqual(doc.locked_by, self.user)

    def test_save_document_content(self):
        """Test ruajtja e përmbajtjes së dokumentit"""
        new_content = 'Përmbajtja e përditësuar'
        
        doc = self.service.save_document_content(
            document=self.document,
            content=new_content,
            user=self.user
        )
        
        self.assertEqual(doc.content, new_content)
        self.assertEqual(doc.last_edited_by, self.user)
        self.assertIsNotNone(doc.last_edited_at)

    def test_add_comment(self):
        """Test shtimi i komentit"""
        comment = self.service.add_comment(
            document=self.document,
            content='Koment nga service',
            user=self.user,
            position_start=5,
            position_end=15
        )
        
        self.assertEqual(comment.content, 'Koment nga service')
        self.assertEqual(comment.document, self.document)
        self.assertEqual(comment.author, self.user)

    def test_get_document_statistics(self):
        """Test statistikat e dokumentit"""
        # Shto disa komente dhe versione
        DocumentComment.objects.create(
            document=self.document,
            content='Koment 1',
            author=self.user
        )
        DocumentComment.objects.create(
            document=self.document,
            content='Koment 2',
            author=self.user
        )
        
        stats = self.service.get_document_statistics(self.document)
        
        self.assertIn('total_comments', stats)
        self.assertIn('word_count', stats)
        self.assertIn('character_count', stats)
        self.assertEqual(stats['total_comments'], 2)

class LLMServiceTest(TestCase):
    """Teste për LLM Service"""
    
    def setUp(self):
        self.service = LegalLLMService()
        self.context = DocumentContext(
            title='Test Document',
            content='Kjo është një test dokument për analizë.',
            document_type='contract',
            case_type='civil'
        )

    @patch('requests.post')
    def test_llm_call(self, mock_post):
        """Test thirrja e LLM"""
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'Test response from LLM'}}],
            'usage': {'total_tokens': 100}
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        response = self.service.call('Test prompt')
        
        self.assertIn('text', response)
        self.assertEqual(response['text'], 'Test response from LLM')

    @patch('requests.post')
    def test_generate_document(self, mock_post):
        """Test gjenerimi i dokumentit"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'Generated document content'}}],
            'usage': {'total_tokens': 150}
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        response = self.service.generate_document(
            document_type='contract',
            context=self.context,
            template_vars={'party1': 'ABC Corp', 'party2': 'XYZ Ltd'}
        )
        
        self.assertIn('text', response)
        self.assertEqual(response['text'], 'Generated document content')

    @patch('requests.post')
    def test_review_document(self, mock_post):
        """Test rishikimi i dokumentit"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'Document review results'}}],
            'usage': {'total_tokens': 200}
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        response = self.service.review_document(
            context=self.context,
            focus_areas=['legal_accuracy', 'format']
        )
        
        self.assertIn('text', response)
        self.assertEqual(response['text'], 'Document review results')

class DocumentFormTest(TestCase):
    """Teste për format e dokumenteve"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='form_user',
            password='testpass123',
            role='lawyer'
        )
        
        self.doc_type = DocumentType.objects.create(name='Form Test Type')
        self.doc_status = DocumentStatus.objects.create(name='Draft')

    def test_document_form_valid(self):
        """Test forma e vlefshme e dokumentit"""
        form_data = {
            'title': 'Test Document Form',
            'description': 'Përshkrim i dokumentit',
            'document_type': self.doc_type.id,
            'status': self.doc_status.id,
            'content': 'Përmbajtja e testit'
        }
        
        form = DocumentForm(data=form_data, user=self.user)
        self.assertTrue(form.is_valid())

    def test_document_form_invalid_title(self):
        """Test forma e pavlefshme (titull i shkurtër)"""
        form_data = {
            'title': 'AB',  # Shumë i shkurtër
            'document_type': self.doc_type.id,
            'status': self.doc_status.id,
            'content': 'Përmbajtje'
        }
        
        form = DocumentForm(data=form_data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)

    def test_document_template_form(self):
        """Test forma e template"""
        form_data = {
            'name': 'Test Template',
            'description': 'Template për test',
            'category': 'Test Category',
            'content': 'Template content with {variable}',
            'variables': '{"variable": "default_value"}',
            'is_active': True
        }
        
        form = DocumentTemplateForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_document_template_form_invalid_json(self):
        """Test forma e template me JSON të pavlefshëm"""
        form_data = {
            'name': 'Test Template',
            'category': 'Test',
            'content': 'Content',
            'variables': 'invalid json'  # JSON i pavlefshëm
        }
        
        form = DocumentTemplateForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('variables', form.errors)

class DocumentViewTest(TestCase):
    """Teste për views e dokumenteve"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='view_user',
            password='testpass123',
            role='lawyer'
        )
        
        self.doc_type = DocumentType.objects.create(name='View Test Type')
        self.doc_status = DocumentStatus.objects.create(name='Draft')
        
        self.document = Document.objects.create(
            title='View Test Document',
            content='Test content',
            document_type=self.doc_type,
            status=self.doc_status,
            created_by=self.user,
            owned_by=self.user
        )

    def test_document_editor_view(self):
        """Test view i editorit të dokumentit"""
        self.client.login(username='view_user', password='testpass123')
        
        url = reverse('document_editor:edit_document', kwargs={'document_id': self.document.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.document.title)

    def test_document_load_api(self):
        """Test API për ngarkimin e dokumentit"""
        self.client.login(username='view_user', password='testpass123')
        
        url = reverse('document_editor:load_document', kwargs={'document_id': self.document.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['document']['title'], self.document.title)

    def test_document_save_api(self):
        """Test API për ruajtjen e dokumentit"""
        self.client.login(username='view_user', password='testpass123')
        
        url = reverse('document_editor:save_document', kwargs={'document_id': self.document.id})
        payload = {
            'content': 'Updated content',
            'content_html': '<p>Updated content</p>'
        }
        
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])

    def test_document_comments_api(self):
        """Test API për komentet"""
        self.client.login(username='view_user', password='testpass123')
        
        # Test GET comments
        url = reverse('document_editor:document_comments', kwargs={'document_id': self.document.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        # Test POST comment
        payload = {
            'content': 'Test comment via API',
            'position_start': 5,
            'position_end': 15
        }
        
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])

class DocumentAuditTest(TestCase):
    """Teste për audit logs"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='audit_user',
            password='testpass123',
            role='lawyer'
        )
        
        self.doc_type = DocumentType.objects.create(name='Audit Test Type')
        self.doc_status = DocumentStatus.objects.create(name='Draft')
        
        self.document = Document.objects.create(
            title='Audit Test Document',
            document_type=self.doc_type,
            status=self.doc_status,
            created_by=self.user,
            owned_by=self.user
        )

    def test_audit_log_creation(self):
        """Test krijimi i audit log"""
        audit_log = DocumentAuditLog.objects.create(
            document=self.document,
            user=self.user,
            action='view',
            details='Document viewed',
            metadata={'ip_address': '127.0.0.1'}
        )
        
        self.assertEqual(audit_log.document, self.document)
        self.assertEqual(audit_log.user, self.user)
        self.assertEqual(audit_log.action, 'view')

    def test_audit_log_search(self):
        """Test kërkim në audit logs"""
        # Krijo disa logs
        DocumentAuditLog.objects.create(
            document=self.document,
            user=self.user,
            action='create',
            details='Document created'
        )
        DocumentAuditLog.objects.create(
            document=self.document,
            user=self.user,
            action='edit',
            details='Document edited'
        )
        
        # Kërko logs
        create_logs = DocumentAuditLog.objects.filter(
            document=self.document,
            action='create'
        )
        edit_logs = DocumentAuditLog.objects.filter(
            document=self.document,
            action='edit'
        )
        
        self.assertEqual(create_logs.count(), 1)
        self.assertEqual(edit_logs.count(), 1)

class DocumentIntegrationTest(TransactionTestCase):
    """Integration tests për workflows të plota"""
    
    def setUp(self):
        self.user_lawyer = User.objects.create_user(
            username='integration_lawyer',
            password='testpass123',
            role='lawyer'
        )
        self.user_client = User.objects.create_user(
            username='integration_client',
            password='testpass123',
            role='client'
        )
        
        self.doc_type = DocumentType.objects.create(name='Integration Test Type')
        self.doc_status_draft = DocumentStatus.objects.create(name='Draft')
        self.doc_status_final = DocumentStatus.objects.create(name='Final')

    def test_complete_document_workflow(self):
        """Test workflow i plotë i dokumentit"""
        service = DocumentEditingService()
        
        # 1. Krijo dokument
        document = Document.objects.create(
            title='Workflow Test Document',
            content='Initial content',
            document_type=self.doc_type,
            status=self.doc_status_draft,
            created_by=self.user_lawyer,
            owned_by=self.user_lawyer
        )
        
        # 2. Merr për editim
        doc_for_edit = service.get_document_for_editing(document.id, self.user_lawyer)
        self.assertTrue(doc_for_edit.is_locked)
        
        # 3. Editoj përmbajtjen
        updated_doc = service.save_document_content(
            document=doc_for_edit,
            content='Updated content',
            user=self.user_lawyer,
            create_version=True
        )
        
        # 4. Shto koment
        comment = service.add_comment(
            document=updated_doc,
            content='Review needed',
            user=self.user_lawyer
        )
        
        # 5. Ndrysho statusin
        updated_doc.status = self.doc_status_final
        updated_doc.save()
        
        # 6. Çblloko dokumentin
        service.release_document_lock(updated_doc, self.user_lawyer)
        
        # Verifiko rezultatet
        final_doc = Document.objects.get(id=document.id)
        self.assertEqual(final_doc.content, 'Updated content')
        self.assertEqual(final_doc.status, self.doc_status_final)
        self.assertFalse(final_doc.is_locked)
        self.assertEqual(final_doc.comments.count(), 1)
        self.assertTrue(final_doc.version_history.exists())

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_async_operations(self):
        """Test operacionet asinkrone"""
        # Ky test do të ekzekutohet vetëm nëse Celery është konfiguruar
        pass

class DocumentPerformanceTest(TestCase):
    """Performance tests"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='perf_user',
            password='testpass123',
            role='lawyer'
        )
        
        self.doc_type = DocumentType.objects.create(name='Performance Test Type')
        self.doc_status = DocumentStatus.objects.create(name='Draft')

    def test_bulk_document_creation(self):
        """Test krijimi masiv i dokumenteve"""
        import time
        
        start_time = time.time()
        
        documents = []
        for i in range(100):
            documents.append(Document(
                title=f'Bulk Document {i}',
                content=f'Content for document {i}',
                document_type=self.doc_type,
                status=self.doc_status,
                created_by=self.user,
                owned_by=self.user
            ))
        
        Document.objects.bulk_create(documents)
        
        end_time = time.time()
        creation_time = end_time - start_time
        
        # Duhet të jetë më pak se 5 sekonda
        self.assertLess(creation_time, 5.0)
        self.assertEqual(Document.objects.count(), 100)

    def test_large_content_handling(self):
        """Test menaxhimi i përmbajtjes së madhe"""
        large_content = 'A' * 100000  # 100KB content
        
        document = Document.objects.create(
            title='Large Content Document',
            content=large_content,
            document_type=self.doc_type,
            status=self.doc_status,
            created_by=self.user,
            owned_by=self.user
        )
        
        self.assertEqual(len(document.content), 100000)
        
        # Test search performance në përmbajtje të madhe
        import time
        start_time = time.time()
        
        results = Document.objects.filter(content__icontains='AAAA')
        list(results)  # Force evaluation
        
        search_time = time.time() - start_time
        self.assertLess(search_time, 1.0)  # Duhet të jetë më pak se 1 sekondë

class DocumentSecurityTest(TestCase):
    """Security tests"""
    
    def setUp(self):
        self.user_lawyer = User.objects.create_user(
            username='security_lawyer',
            password='testpass123',
            role='lawyer'
        )
        self.user_unauthorized = User.objects.create_user(
            username='unauthorized_user',
            password='testpass123',
            role='client'
        )
        
        self.doc_type = DocumentType.objects.create(name='Security Test Type')
        self.doc_status = DocumentStatus.objects.create(name='Draft')
        
        self.document = Document.objects.create(
            title='Secure Document',
            content='Confidential content',
            document_type=self.doc_type,
            status=self.doc_status,
            created_by=self.user_lawyer,
            owned_by=self.user_lawyer
        )

    def test_unauthorized_access_prevention(self):
        """Test parandalimi i aksesit të paautorizuar"""
        client = Client()
        client.login(username='unauthorized_user', password='testpass123')
        
        # Provo të marrësh dokumentin
        url = reverse('document_editor:load_document', kwargs={'document_id': self.document.id})
        response = client.get(url)
        
        self.assertEqual(response.status_code, 403)

    def test_xss_prevention(self):
        """Test parandalimi i XSS"""
        malicious_content = '<script>alert("XSS")</script>'
        
        document = Document.objects.create(
            title='XSS Test Document',
            content=malicious_content,
            document_type=self.doc_type,
            status=self.doc_status,
            created_by=self.user_lawyer,
            owned_by=self.user_lawyer
        )
        
        # Përmbajtja duhet të ruhet ashtu siç është
        self.assertEqual(document.content, malicious_content)
        
        # Por në template duhet të escapohet
        client = Client()
        client.login(username='security_lawyer', password='testpass123')
        
        url = reverse('document_editor:edit_document', kwargs={'document_id': document.id})
        response = client.get(url)
        
        # Nuk duhet të përmbajë script tag të pa-escaped
        self.assertNotContains(response, '<script>alert("XSS")</script>', html=True)

    def test_sql_injection_prevention(self):
        """Test parandalimi i SQL Injection"""
        # Django ORM automatikisht parandalon SQL injection
        malicious_title = "'; DROP TABLE documents; --"
        
        document = Document.objects.create(
            title=malicious_title,
            document_type=self.doc_type,
            status=self.doc_status,
            created_by=self.user_lawyer,
            owned_by=self.user_lawyer
        )
        
        # Tabela duhet të ekzistojë ende
        self.assertTrue(Document.objects.filter(title=malicious_title).exists())
        self.assertTrue(Document.objects.count() >= 1)

# Test utilities

class DocumentTestUtils:
    """Utility methods për teste"""
    
    @staticmethod
    def create_test_document(user, title="Test Document", content="Test content"):
        """Krijo një dokument për test"""
        doc_type, _ = DocumentType.objects.get_or_create(
            name='Test Type',
            defaults={'description': 'Type for testing'}
        )
        doc_status, _ = DocumentStatus.objects.get_or_create(
            name='Draft',
            defaults={'description': 'Draft status', 'color': '#ffc107'}
        )
        
        return Document.objects.create(
            title=title,
            content=content,
            document_type=doc_type,
            status=doc_status,
            created_by=user,
            owned_by=user
        )
    
    @staticmethod
    def create_test_user(username, role='lawyer'):
        """Krijo një përdorues për test"""
        return User.objects.create_user(
            username=username,
            email=f'{username}@example.com',
            password='testpass123',
            role=role
        )
    
    @staticmethod
    def create_test_template(name="Test Template", category="Test"):
        """Krijo një template për test"""
        return DocumentTemplate.objects.create(
            name=name,
            category=category,
            content='Template content with {variable}',
            variables={'variable': 'default_value'},
            is_active=True
        )

# Custom test runner
class DocumentTestRunner:
    """Custom test runner për module-specific tests"""
    
    def __init__(self):
        self.test_suites = [
            'document_editor_module.tests.DocumentModelTest',
            'document_editor_module.tests.DocumentServiceTest',
            'document_editor_module.tests.DocumentViewTest',
        ]
    
    def run_tests(self):
        """Ekzekuto të gjitha testet e modulit"""
        from django.test.utils import get_runner
        from django.conf import settings
        
        TestRunner = get_runner(settings)
        test_runner = TestRunner()
        failures = test_runner.run_tests(self.test_suites)
        return failures

# Test configurations për environment të ndryshme

TEST_SETTINGS = {
    'TESTING': True,
    'DATABASES': {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    },
    'PASSWORD_HASHERS': [
        'django.contrib.auth.hashers.MD5PasswordHasher',  # Më shpejtë për teste
    ],
    'EMAIL_BACKEND': 'django.core.mail.backends.locmem.EmailBackend',
    'CELERY_TASK_ALWAYS_EAGER': True,
    'CELERY_TASK_EAGER_PROPAGATES': True,
}
