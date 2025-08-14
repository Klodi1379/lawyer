"""
Tests për Document Editor Module
Përfshin unit tests, integration tests dhe functional tests
"""

import os
import json
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, Mock, MagicMock

from django.test import TestCase, TransactionTestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied

from ..models.document_models import (
    Document, DocumentTemplate, DocumentType, DocumentStatus,
    DocumentComment, DocumentVersion, DocumentSignature, DocumentAuditLog
)
from ..services.document_service import DocumentEditingService
from ..advanced_features.template_engine import LegalTemplateEngine, TemplateContext
from ..advanced_features.workflow_system import WorkflowEngine, WorkflowTemplate
from ..advanced_features.signature_system import SignatureService, SignerInfo
from ..advanced_features.document_automation import DocumentAutomationEngine
from ..services.llm_service import LegalLLMService, DocumentContext

User = get_user_model()

class DocumentModelTest(TestCase):
    """Test cases për Document model"""

    def setUp(self):
        """Setup test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        if hasattr(self.user, 'role'):
            self.user.role = 'lawyer'
            self.user.save()

        # Create test client
        from cases.models import Client
        self.client_obj = Client.objects.create(
            full_name='Test Client',
            email='client@example.com'
        )

        # Create test case
        from cases.models import Case
        self.case = Case.objects.create(
            title='Test Case',
            client=self.client_obj,
            assigned_to=self.user
        )

        # Create document type and status
        self.doc_type = DocumentType.objects.create(
            name='Test Document',
            description='Test document type'
        )
        self.doc_status = DocumentStatus.objects.create(
            name='Draft',
            description='Draft status'
        )

    def test_document_creation(self):
        """Test document creation"""
        document = Document.objects.create(
            title='Test Document',
            content='Test content',
            case=self.case,
            document_type=self.doc_type,
            status=self.doc_status,
            created_by=self.user,
            owned_by=self.user
        )
        
        self.assertEqual(document.title, 'Test Document')
        self.assertEqual(document.content, 'Test content')
        self.assertEqual(document.case, self.case)
        self.assertEqual(document.created_by, self.user)
        self.assertTrue(document.can_edit(self.user))

    def test_document_version_creation(self):
        """Test automatic version creation"""
        document = Document.objects.create(
            title='Versioned Document',
            content='Original content',
            case=self.case,
            document_type=self.doc_type,
            status=self.doc_status,
            created_by=self.user,
            owned_by=self.user
        )
        
        self.assertEqual(document.version_number, 1)
        
        # Update content should create new version
        document.content = 'Updated content'
        document.save()
        
        # Version should increment
        self.assertEqual(document.version_number, 2)
        
        # Check version history
        versions = document.version_history.all()
        self.assertEqual(versions.count(), 2)

    def test_document_locking(self):
        """Test document locking mechanism"""
        document = Document.objects.create(
            title='Lockable Document',
            content='Content to lock',
            case=self.case,
            document_type=self.doc_type,
            status=self.doc_status,
            created_by=self.user,
            owned_by=self.user
        )
        
        # Lock document
        self.assertTrue(document.lock_document(self.user))
        self.assertTrue(document.is_locked)
        self.assertEqual(document.locked_by, self.user)
        
        # Try to lock again should fail
        self.assertFalse(document.lock_document(self.user))
        
        # Unlock document
        self.assertTrue(document.unlock_document(self.user))
        self.assertFalse(document.is_locked)
        self.assertIsNone(document.locked_by)

    def test_document_permissions(self):
        """Test document permissions"""
        document = Document.objects.create(
            title='Permission Test Document',
            content='Content',
            case=self.case,
            document_type=self.doc_type,
            status=self.doc_status,
            created_by=self.user,
            owned_by=self.user
        )
        
        # Owner can edit
        self.assertTrue(document.can_edit(self.user))
        
        # Create another user
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        if hasattr(other_user, 'role'):
            other_user.role = 'lawyer'
            other_user.save()
        
        # Other user cannot edit initially
        self.assertFalse(document.can_edit(other_user))
        
        # Add as editor
        from ..models.document_models import DocumentEditor
        DocumentEditor.objects.create(document=document, user=other_user)
        
        # Now other user can edit
        self.assertTrue(document.can_edit(other_user))

class DocumentTemplateModelTest(TestCase):
    """Test cases për DocumentTemplate model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='templateuser',
            email='template@example.com',
            password='testpass123'
        )

    def test_template_creation(self):
        """Test template creation"""
        template = DocumentTemplate.objects.create(
            name='Test Template',
            description='Test template description',
            category='Contract',
            content='Hello {{ name }}, this is a template.',
            created_by=self.user
        )
        
        self.assertEqual(template.name, 'Test Template')
        self.assertEqual(template.category, 'Contract')
        self.assertTrue(template.is_active)

    def test_template_validation(self):
        """Test template content validation"""
        # Valid Jinja2 syntax should pass
        template = DocumentTemplate(
            name='Valid Template',
            content='Hello {{ name }}!',
            created_by=self.user
        )
        # Should not raise exception
        template.full_clean()
        
        # Invalid syntax should fail validation
        # This would be tested in forms or template engine tests

class DocumentServiceTest(TestCase):
    """Test cases për DocumentEditingService"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='serviceuser',
            email='service@example.com',
            password='testpass123'
        )
        
        from cases.models import Client, Case
        self.client_obj = Client.objects.create(full_name='Service Client')
        self.case = Case.objects.create(title='Service Case', client=self.client_obj)
        
        self.doc_type = DocumentType.objects.create(name='Service Doc')
        self.doc_status = DocumentStatus.objects.create(name='Draft')
        
        self.document = Document.objects.create(
            title='Service Test Document',
            content='Original content',
            case=self.case,
            document_type=self.doc_type,
            status=self.doc_status,
            created_by=self.user,
            owned_by=self.user
        )
        
        self.service = DocumentEditingService()

    def test_save_document_content(self):
        """Test saving document content"""
        new_content = 'Updated content via service'
        
        self.service.save_document_content(
            document=self.document,
            content=new_content,
            user=self.user
        )
        
        self.document.refresh_from_db()
        self.assertEqual(self.document.content, new_content)
        self.assertEqual(self.document.last_edited_by, self.user)

    def test_create_version(self):
        """Test version creation"""
        original_content = self.document.content
        new_content = 'Version 2 content'
        
        self.service.save_document_content(
            document=self.document,
            content=new_content,
            user=self.user,
            create_version=True
        )
        
        # Check version was created
        versions = self.document.version_history.all()
        self.assertEqual(versions.count(), 2)
        
        # Check latest version has new content
        latest_version = versions.order_by('-version_number').first()
        self.assertEqual(latest_version.content, new_content)

    def test_add_comment(self):
        """Test adding comment"""
        comment_content = 'This is a test comment'
        
        comment = self.service.add_comment(
            document=self.document,
            content=comment_content,
            user=self.user,
            position_start=0,
            position_end=10
        )
        
        self.assertEqual(comment.content, comment_content)
        self.assertEqual(comment.author, self.user)
        self.assertEqual(comment.position_start, 0)
        self.assertEqual(comment.position_end, 10)

    def test_resolve_comment(self):
        """Test resolving comment"""
        # Create comment first
        comment = self.service.add_comment(
            document=self.document,
            content='Comment to resolve',
            user=self.user
        )
        
        # Resolve comment
        resolved_comment = self.service.resolve_comment(comment.id, self.user)
        
        self.assertTrue(resolved_comment.is_resolved)
        self.assertEqual(resolved_comment.resolved_by, self.user)
        self.assertIsNotNone(resolved_comment.resolved_at)

class TemplateEngineTest(TestCase):
    """Test cases për LegalTemplateEngine"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='templateengineuser',
            email='engine@example.com',
            password='testpass123'
        )
        
        self.template = DocumentTemplate.objects.create(
            name='Engine Test Template',
            content='Dear {{ client_name }}, your case {{ case_title }} is {{ status }}.',
            created_by=self.user
        )
        
        self.engine = LegalTemplateEngine()

    def test_render_template(self):
        """Test template rendering"""
        context = TemplateContext(variables={
            'client_name': 'John Doe',
            'case_title': 'Property Dispute',
            'status': 'in progress'
        })
        
        result = self.engine.render_template(self.template, context)
        expected = 'Dear John Doe, your case Property Dispute is in progress.'
        
        self.assertEqual(result, expected)

    def test_parse_template_variables(self):
        """Test parsing template variables"""
        variables = self.engine.parse_template_variables(self.template.content)
        
        var_names = [var.name for var in variables]
        self.assertIn('client_name', var_names)
        self.assertIn('case_title', var_names)
        self.assertIn('status', var_names)

    def test_validate_template_syntax(self):
        """Test template syntax validation"""
        # Valid template
        is_valid, errors = self.engine.validate_template_syntax(
            'Hello {{ name }}!'
        )
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        
        # Invalid template
        is_valid, errors = self.engine.validate_template_syntax(
            'Hello {{ name }!'  # Missing closing brace
        )
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)

class WorkflowSystemTest(TestCase):
    """Test cases për WorkflowEngine"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='workflowuser',
            email='workflow@example.com',
            password='testpass123'
        )
        
        from cases.models import Client, Case
        self.client_obj = Client.objects.create(full_name='Workflow Client')
        self.case = Case.objects.create(title='Workflow Case', client=self.client_obj)
        
        self.doc_type = DocumentType.objects.create(name='Workflow Doc')
        self.doc_status = DocumentStatus.objects.create(name='Draft')
        
        self.document = Document.objects.create(
            title='Workflow Test Document',
            content='Content for workflow',
            case=self.case,
            document_type=self.doc_type,
            status=self.doc_status,
            created_by=self.user,
            owned_by=self.user
        )
        
        # Create workflow template
        self.workflow_template = WorkflowTemplate.objects.create(
            name='Test Workflow',
            description='Test workflow template',
            steps_config=[
                {
                    'name': 'Review',
                    'type': 'review',
                    'deadline_hours': 24,
                    'assigned_roles': ['lawyer']
                },
                {
                    'name': 'Approve',
                    'type': 'approval',
                    'deadline_hours': 12,
                    'assigned_roles': ['admin']
                }
            ],
            created_by=self.user
        )
        
        self.engine = WorkflowEngine()

    def test_create_workflow(self):
        """Test workflow creation"""
        workflow = self.engine.create_workflow(
            document=self.document,
            template=self.workflow_template
        )
        
        self.assertEqual(workflow.document, self.document)
        self.assertEqual(workflow.template, self.workflow_template)
        self.assertEqual(workflow.total_steps, 2)
        
        # Check steps were created
        steps = workflow.steps.all()
        self.assertEqual(steps.count(), 2)

    @patch('channels.layers.get_channel_layer')
    def test_execute_workflow_action(self, mock_channel_layer):
        """Test workflow action execution"""
        # Create workflow first
        workflow = self.engine.create_workflow(
            document=self.document,
            template=self.workflow_template
        )
        
        # Get first step
        first_step = workflow.steps.filter(step_number=1).first()
        
        # Add user as assigned to step
        from ..advanced_features.workflow_system import WorkflowStepAssignment
        WorkflowStepAssignment.objects.create(
            step=first_step,
            user=self.user
        )
        
        # Execute approval action
        from ..advanced_features.workflow_system import ActionType
        success = self.engine.execute_action(
            step=first_step,
            action_type=ActionType.APPROVE,
            user=self.user,
            comment='Test approval'
        )
        
        self.assertTrue(success)
        
        # Check action was logged
        actions = first_step.actions.all()
        self.assertEqual(actions.count(), 1)
        self.assertEqual(actions.first().action_type, ActionType.APPROVE.value)

class SignatureSystemTest(TestCase):
    """Test cases për SignatureService"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='signatureuser',
            email='signature@example.com',
            password='testpass123'
        )
        
        from cases.models import Client, Case
        self.client_obj = Client.objects.create(full_name='Signature Client')
        self.case = Case.objects.create(title='Signature Case', client=self.client_obj)
        
        self.doc_type = DocumentType.objects.create(name='Signature Doc')
        self.doc_status = DocumentStatus.objects.create(name='Draft')
        
        self.document = Document.objects.create(
            title='Signature Test Document',
            content='Document to be signed',
            case=self.case,
            document_type=self.doc_type,
            status=self.doc_status,
            created_by=self.user,
            owned_by=self.user
        )
        
        self.service = SignatureService()

    @patch('requests.post')
    def test_create_signature_request(self, mock_post):
        """Test signature request creation"""
        # Mock external API response
        mock_response = Mock()
        mock_response.json.return_value = {
            'envelope_id': 'test-envelope-123',
            'status': 'sent'
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        signers = [
            SignerInfo(
                name='John Doe',
                email='john@example.com',
                role='Client',
                order=1
            )
        ]
        
        result = self.service.create_signature_request(
            document=self.document,
            signers=signers,
            title='Test Signature Request',
            message='Please sign this document'
        )
        
        self.assertTrue(result['success'])
        self.assertIn('signature_request_id', result)

    def test_verify_signature(self):
        """Test signature verification"""
        # Create a signature first
        signature = DocumentSignature.objects.create(
            document=self.document,
            signer=self.user,
            signature_data='test_signature_data',
            signed_at=timezone.now(),
            ip_address='127.0.0.1',
            user_agent='Test Agent'
        )
        
        result = self.service.verify_signature(signature.id)
        
        self.assertIn('is_valid', result)
        self.assertIn('signature_id', result)

class DocumentAutomationTest(TestCase):
    """Test cases për DocumentAutomationEngine"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='automationuser',
            email='automation@example.com',
            password='testpass123'
        )
        
        self.doc_type = DocumentType.objects.create(name='Automation Doc')
        
        self.template = DocumentTemplate.objects.create(
            name='Automation Template',
            content='Case: {{ case_title }}, Client: {{ client_name }}',
            category='Contract',
            created_by=self.user
        )
        
        self.engine = DocumentAutomationEngine()

    @patch.object(DocumentAutomationEngine, '_call_llm_for_suggestions')
    def test_suggest_document_template(self, mock_llm):
        """Test document template suggestions"""
        # Mock LLM response
        mock_llm.return_value = [
            {
                'type': 'Contract',
                'title': 'Service Agreement',
                'confidence': 0.85,
                'template_id': self.template.id
            }
        ]
        
        case_info = {
            'title': 'Service Provider Agreement',
            'description': 'Need contract for web development services',
            'case_type': 'commercial'
        }
        
        suggestions = self.engine.suggest_document_template(case_info)
        
        self.assertGreater(len(suggestions), 0)
        self.assertEqual(suggestions[0].type, 'Contract')
        self.assertEqual(suggestions[0].template_id, self.template.id)

    def test_generate_document_content(self):
        """Test document content generation"""
        variables = {
            'case_title': 'Test Case',
            'client_name': 'Test Client'
        }
        
        case_info = {
            'title': 'Test Case',
            'case_type': 'civil'
        }
        
        result = self.engine.generate_document_content(
            template_id=self.template.id,
            variables=variables,
            case_info=case_info
        )
        
        self.assertTrue(result['success'])
        self.assertIn('content', result)
        self.assertIn('Test Case', result['content'])
        self.assertIn('Test Client', result['content'])

class LLMServiceTest(TestCase):
    """Test cases për LegalLLMService"""

    def setUp(self):
        self.service = LegalLLMService()
        
        self.context = DocumentContext(
            title='Test Document',
            content='This is a test legal document.',
            document_type='Contract',
            case_type='commercial'
        )

    @patch('requests.post')
    def test_suggest_improvements(self, mock_post):
        """Test LLM improvement suggestions"""
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': 'Consider adding more specific terms and conditions.'
                }
            }]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        response = self.service.suggest_improvements(self.context)
        
        self.assertIsNotNone(response.text)
        self.assertIn('terms and conditions', response.text)

    @patch('requests.post')
    def test_review_document(self, mock_post):
        """Test LLM document review"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': 'The document structure is good but needs more detail in section 2.'
                }
            }]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        response = self.service.review_document(self.context)
        
        self.assertIsNotNone(response.text)
        self.assertIn('section 2', response.text)

    @patch('requests.post')
    def test_analyze_legal_compliance(self, mock_post):
        """Test legal compliance analysis"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': 'The document complies with basic commercial contract requirements.'
                }
            }]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        response = self.service.analyze_legal_compliance(self.context)
        
        self.assertIsNotNone(response.text)
        self.assertIn('complies', response.text)

class DocumentViewTest(TestCase):
    """Test cases për Document views"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='viewuser',
            email='view@example.com',
            password='testpass123'
        )
        if hasattr(self.user, 'role'):
            self.user.role = 'lawyer'
            self.user.save()
        
        from cases.models import Client, Case
        self.client_obj = Client.objects.create(full_name='View Client')
        self.case = Case.objects.create(title='View Case', client=self.client_obj)
        
        self.doc_type = DocumentType.objects.create(name='View Doc')
        self.doc_status = DocumentStatus.objects.create(name='Draft')
        
        self.document = Document.objects.create(
            title='View Test Document',
            content='Content for view testing',
            case=self.case,
            document_type=self.doc_type,
            status=self.doc_status,
            created_by=self.user,
            owned_by=self.user
        )

    def test_document_list_view(self):
        """Test document list view"""
        self.client.login(username='viewuser', password='testpass123')
        
        url = reverse('document_editor:document_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.document.title)

    def test_document_detail_view(self):
        """Test document detail view"""
        self.client.login(username='viewuser', password='testpass123')
        
        url = reverse('document_editor:document_detail', kwargs={'pk': self.document.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.document.title)
        self.assertContains(response, self.document.content)

    def test_document_create_view(self):
        """Test document create view"""
        self.client.login(username='viewuser', password='testpass123')
        
        url = reverse('document_editor:document_create')
        
        # GET request
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # POST request
        data = {
            'title': 'New Document',
            'content': 'New document content',
            'case': self.case.id,
            'document_type': self.doc_type.id,
            'status': self.doc_status.id
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)  # Redirect after creation
        
        # Check document was created
        self.assertTrue(Document.objects.filter(title='New Document').exists())

    def test_document_update_view(self):
        """Test document update view"""
        self.client.login(username='viewuser', password='testpass123')
        
        url = reverse('document_editor:document_update', kwargs={'pk': self.document.pk})
        
        # GET request
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # POST request
        data = {
            'title': 'Updated Document Title',
            'content': 'Updated content',
            'case': self.case.id,
            'document_type': self.doc_type.id,
            'status': self.doc_status.id
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)  # Redirect after update
        
        # Check document was updated
        self.document.refresh_from_db()
        self.assertEqual(self.document.title, 'Updated Document Title')

class DocumentFormTest(TestCase):
    """Test cases për Document forms"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='formuser',
            email='form@example.com',
            password='testpass123'
        )
        
        from cases.models import Client, Case
        self.client_obj = Client.objects.create(full_name='Form Client')
        self.case = Case.objects.create(title='Form Case', client=self.client_obj)
        
        self.doc_type = DocumentType.objects.create(name='Form Doc')
        self.doc_status = DocumentStatus.objects.create(name='Draft')

    def test_document_form_valid(self):
        """Test valid document form"""
        from ..forms import DocumentForm
        
        data = {
            'title': 'Form Test Document',
            'content': 'Content for form testing',
            'case': self.case.id,
            'document_type': self.doc_type.id,
            'status': self.doc_status.id
        }
        
        form = DocumentForm(data=data, user=self.user)
        self.assertTrue(form.is_valid())

    def test_document_form_invalid(self):
        """Test invalid document form"""
        from ..forms import DocumentForm
        
        # Missing required fields
        data = {
            'title': '',  # Empty title
            'content': 'Content'
        }
        
        form = DocumentForm(data=data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)

    def test_document_comment_form(self):
        """Test document comment form"""
        from ..forms import DocumentCommentForm
        
        data = {
            'content': 'This is a test comment',
            'position_start': 10,
            'position_end': 20
        }
        
        form = DocumentCommentForm(data=data)
        self.assertTrue(form.is_valid())

class IntegrationTest(TransactionTestCase):
    """Integration tests for complete workflows"""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True
        )
        if hasattr(self.admin_user, 'role'):
            self.admin_user.role = 'admin'
            self.admin_user.save()
        
        self.lawyer_user = User.objects.create_user(
            username='lawyer',
            email='lawyer@example.com',
            password='lawyerpass123'
        )
        if hasattr(self.lawyer_user, 'role'):
            self.lawyer_user.role = 'lawyer'
            self.lawyer_user.save()

    def test_complete_document_workflow(self):
        """Test complete document creation and workflow"""
        # Setup initial data
        from cases.models import Client, Case
        client = Client.objects.create(full_name='Integration Client')
        case = Case.objects.create(title='Integration Case', client=client)
        
        doc_type = DocumentType.objects.create(name='Integration Doc')
        doc_status = DocumentStatus.objects.create(name='Draft')
        
        # Create document template
        template = DocumentTemplate.objects.create(
            name='Integration Template',
            content='Client: {{ client_name }}, Case: {{ case_title }}',
            created_by=self.admin_user
        )
        
        # Create document using automation engine
        automation_engine = DocumentAutomationEngine()
        
        variables = {
            'client_name': client.full_name,
            'case_title': case.title
        }
        
        result = automation_engine.generate_document_content(
            template_id=template.id,
            variables=variables,
            case_info={'title': case.title, 'case_type': 'civil'}
        )
        
        self.assertTrue(result['success'])
        
        # Create actual document
        document = Document.objects.create(
            title='Integration Test Document',
            content=result['content'],
            case=case,
            document_type=doc_type,
            status=doc_status,
            created_by=self.lawyer_user,
            owned_by=self.lawyer_user,
            template_used=template
        )
        
        # Create workflow
        workflow_template = WorkflowTemplate.objects.create(
            name='Integration Workflow',
            description='Integration test workflow',
            steps_config=[
                {
                    'name': 'Review',
                    'type': 'review',
                    'deadline_hours': 24
                }
            ],
            created_by=self.admin_user
        )
        
        workflow_engine = WorkflowEngine()
        workflow = workflow_engine.create_workflow(
            document=document,
            template=workflow_template
        )
        
        self.assertIsNotNone(workflow)
        self.assertEqual(workflow.document, document)
        
        # Verify all components work together
        self.assertEqual(document.template_used, template)
        self.assertTrue(hasattr(document, 'workflow'))
        self.assertIn(client.full_name, document.content)
        self.assertIn(case.title, document.content)

# Utility test mixins and helpers

class DocumentTestMixin:
    """Mixin with common document test utilities"""
    
    def create_test_document(self, **kwargs):
        """Create a test document with default values"""
        defaults = {
            'title': 'Test Document',
            'content': 'Test content',
            'created_by': getattr(self, 'user', None),
            'owned_by': getattr(self, 'user', None)
        }
        defaults.update(kwargs)
        return Document.objects.create(**defaults)
    
    def create_test_user(self, username='testuser', role='lawyer'):
        """Create a test user"""
        user = User.objects.create_user(
            username=username,
            email=f'{username}@example.com',
            password='testpass123'
        )
        if hasattr(user, 'role'):
            user.role = role
            user.save()
        return user

class MockLLMTestCase(TestCase):
    """Base test case with mocked LLM calls"""
    
    def setUp(self):
        super().setUp()
        
        # Mock LLM service
        self.llm_patcher = patch('requests.post')
        self.mock_llm_post = self.llm_patcher.start()
        
        # Default mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': 'Mocked LLM response'
                }
            }]
        }
        mock_response.raise_for_status.return_value = None
        self.mock_llm_post.return_value = mock_response
    
    def tearDown(self):
        super().tearDown()
        self.llm_patcher.stop()
