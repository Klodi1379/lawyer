"""
Celery Tasks për Document Editor Module
Background tasks për document processing, notifications, AI operations
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.auth import get_user_model
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models.document_models import (
    Document, DocumentTemplate, DocumentAuditLog, LLMInteraction
)
from .advanced_features.workflow_system import (
    DocumentWorkflow, WorkflowStep, WorkflowStepStatus, WorkflowAction
)
from .advanced_features.signature_system import SignatureRequest, SignatureStatus
from .services.llm_service import LegalLLMService, DocumentContext
from .services.document_service import DocumentEditingService

User = get_user_model()
logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()

# Document Processing Tasks

@shared_task(bind=True, max_retries=3)
def process_document_upload(self, document_id: int, extract_content: bool = True):
    """
    Process uploaded document: extract content, generate preview, analyze
    """
    try:
        document = Document.objects.get(id=document_id)
        
        if extract_content and document.file:
            # Extract text content from file
            content = extract_document_content(document.file.path)
            if content:
                document.content = content
                document.save()
                
                # Log extraction
                DocumentAuditLog.objects.create(
                    document=document,
                    action='content_extracted',
                    details=f'Extracted {len(content)} characters from uploaded file'
                )
        
        # Generate document preview/thumbnail if needed
        generate_document_preview.delay(document_id)
        
        # Analyze document with AI
        analyze_document_with_ai.delay(document_id)
        
        # Send notification to owner
        send_document_notification.delay(
            document_id=document_id,
            notification_type='upload_processed',
            recipient_id=document.owned_by.id
        )
        
        return {'success': True, 'document_id': document_id}
        
    except Document.DoesNotExist:
        logger.error(f"Document {document_id} not found for processing")
        return {'success': False, 'error': 'Document not found'}
    except Exception as e:
        logger.error(f"Document processing error: {e}")
        # Retry task
        raise self.retry(countdown=60, exc=e)

@shared_task
def extract_document_content(file_path: str) -> Optional[str]:
    """
    Extract text content from various document formats
    """
    try:
        import os
        from pathlib import Path
        
        file_extension = Path(file_path).suffix.lower()
        
        if file_extension == '.pdf':
            return extract_pdf_content(file_path)
        elif file_extension in ['.docx', '.doc']:
            return extract_word_content(file_path)
        elif file_extension == '.txt':
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        elif file_extension == '.html':
            return extract_html_content(file_path)
        else:
            logger.warning(f"Unsupported file format: {file_extension}")
            return None
            
    except Exception as e:
        logger.error(f"Content extraction error: {e}")
        return None

def extract_pdf_content(file_path: str) -> str:
    """Extract text from PDF file"""
    try:
        import PyPDF2
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
            return text
    except ImportError:
        logger.warning("PyPDF2 not installed, cannot extract PDF content")
        return ""
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return ""

def extract_word_content(file_path: str) -> str:
    """Extract text from Word document"""
    try:
        import docx
        doc = docx.Document(file_path)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    except ImportError:
        logger.warning("python-docx not installed, cannot extract Word content")
        return ""
    except Exception as e:
        logger.error(f"Word extraction error: {e}")
        return ""

def extract_html_content(file_path: str) -> str:
    """Extract text from HTML file"""
    try:
        from bs4 import BeautifulSoup
        with open(file_path, 'r', encoding='utf-8') as file:
            soup = BeautifulSoup(file.read(), 'html.parser')
            return soup.get_text()
    except ImportError:
        logger.warning("BeautifulSoup not installed, cannot extract HTML content")
        return ""
    except Exception as e:
        logger.error(f"HTML extraction error: {e}")
        return ""

@shared_task
def generate_document_preview(document_id: int):
    """
    Generate preview/thumbnail for document
    """
    try:
        document = Document.objects.get(id=document_id)
        
        # Generate preview based on content
        preview_html = render_to_string('document_editor/previews/document_preview.html', {
            'document': document
        })
        
        # Save preview to document metadata or separate field
        if not document.metadata:
            document.metadata = {}
        
        document.metadata['preview_html'] = preview_html
        document.metadata['preview_generated_at'] = timezone.now().isoformat()
        document.save()
        
        logger.info(f"Preview generated for document {document_id}")
        
    except Document.DoesNotExist:
        logger.error(f"Document {document_id} not found for preview generation")
    except Exception as e:
        logger.error(f"Preview generation error: {e}")

# AI Processing Tasks

@shared_task(bind=True, max_retries=2)
def analyze_document_with_ai(self, document_id: int):
    """
    Analyze document content with AI for improvements and compliance
    """
    try:
        document = Document.objects.get(id=document_id)
        llm_service = LegalLLMService()
        
        context = DocumentContext(
            title=document.title,
            content=document.content,
            document_type=document.document_type.name if document.document_type else 'Unknown',
            case_type=getattr(document.case, 'case_type', 'Unknown')
        )
        
        # Run multiple AI analyses
        analyses = {}
        
        # 1. Document review
        review_response = llm_service.review_document(context)
        if not review_response.error:
            analyses['review'] = review_response.text
            
            # Save LLM interaction
            LLMInteraction.objects.create(
                document=document,
                interaction_type='review',
                prompt="Document review analysis",
                llm_response=review_response.text,
                confidence_score=review_response.confidence,
                processing_time=review_response.processing_time,
                llm_model=review_response.model_used,
                llm_provider=review_response.provider
            )
        
        # 2. Compliance check
        compliance_response = llm_service.analyze_legal_compliance(context)
        if not compliance_response.error:
            analyses['compliance'] = compliance_response.text
            
            LLMInteraction.objects.create(
                document=document,
                interaction_type='compliance',
                prompt="Legal compliance analysis",
                llm_response=compliance_response.text,
                confidence_score=compliance_response.confidence,
                processing_time=compliance_response.processing_time,
                llm_model=compliance_response.model_used,
                llm_provider=compliance_response.provider
            )
        
        # 3. Improvement suggestions
        improvement_response = llm_service.suggest_improvements(context)
        if not improvement_response.error:
            analyses['improvements'] = improvement_response.text
            
            LLMInteraction.objects.create(
                document=document,
                interaction_type='improvements',
                prompt="Document improvement suggestions",
                llm_response=improvement_response.text,
                confidence_score=improvement_response.confidence,
                processing_time=improvement_response.processing_time,
                llm_model=improvement_response.model_used,
                llm_provider=improvement_response.provider
            )
        
        # Save analyses to document metadata
        if not document.metadata:
            document.metadata = {}
        
        document.metadata['ai_analyses'] = analyses
        document.metadata['ai_analysis_date'] = timezone.now().isoformat()
        document.save()
        
        # Notify document owner
        send_ai_analysis_notification.delay(document_id, analyses)
        
        return {'success': True, 'analyses_count': len(analyses)}
        
    except Document.DoesNotExist:
        logger.error(f"Document {document_id} not found for AI analysis")
        return {'success': False, 'error': 'Document not found'}
    except Exception as e:
        logger.error(f"AI analysis error: {e}")
        raise self.retry(countdown=120, exc=e)

@shared_task
def generate_document_content_ai(template_id: int, variables: Dict[str, Any], case_info: Dict[str, Any]):
    """
    Generate document content using AI and template
    """
    try:
        from .advanced_features.document_automation import DocumentAutomationEngine
        
        automation_engine = DocumentAutomationEngine()
        result = automation_engine.generate_document_content(
            template_id=template_id,
            variables=variables,
            case_info=case_info,
            enhancement_level='advanced'
        )
        
        return result
        
    except Exception as e:
        logger.error(f"AI content generation error: {e}")
        return {'success': False, 'error': str(e)}

@shared_task
def batch_analyze_documents(document_ids: List[int]):
    """
    Batch analyze multiple documents with AI
    """
    results = []
    
    for doc_id in document_ids:
        try:
            result = analyze_document_with_ai.delay(doc_id)
            results.append({'document_id': doc_id, 'task_id': result.id})
        except Exception as e:
            logger.error(f"Error queuing AI analysis for document {doc_id}: {e}")
            results.append({'document_id': doc_id, 'error': str(e)})
    
    return results

# Workflow Tasks

@shared_task
def check_workflow_deadlines():
    """
    Check for overdue workflow steps and send notifications
    """
    try:
        now = timezone.now()
        
        # Find overdue workflow steps
        overdue_steps = WorkflowStep.objects.filter(
            deadline__lt=now,
            status__in=[WorkflowStepStatus.PENDING.value, WorkflowStepStatus.IN_PROGRESS.value]
        ).select_related('workflow__document').prefetch_related('assigned_users')
        
        notification_count = 0
        
        for step in overdue_steps:
            # Send notifications to assigned users
            for user in step.assigned_users.all():
                send_workflow_notification.delay(
                    workflow_id=step.workflow.id,
                    step_id=step.id,
                    user_id=user.id,
                    notification_type='deadline_overdue'
                )
                notification_count += 1
            
            # Log audit entry
            DocumentAuditLog.objects.create(
                document=step.workflow.document,
                action='workflow_deadline_overdue',
                details=f'Step "{step.name}" is overdue by {now - step.deadline}',
                metadata={'step_id': step.id, 'deadline': step.deadline.isoformat()}
            )
        
        logger.info(f"Processed {overdue_steps.count()} overdue workflow steps, sent {notification_count} notifications")
        
        return {
            'overdue_steps': overdue_steps.count(),
            'notifications_sent': notification_count
        }
        
    except Exception as e:
        logger.error(f"Workflow deadline check error: {e}")
        return {'error': str(e)}

@shared_task
def send_workflow_reminder(step_id: int, hours_before: int = 24):
    """
    Send reminder before workflow deadline
    """
    try:
        step = WorkflowStep.objects.select_related('workflow__document').get(id=step_id)
        
        # Check if reminder is still relevant
        if step.status not in [WorkflowStepStatus.PENDING.value, WorkflowStepStatus.IN_PROGRESS.value]:
            logger.info(f"Workflow step {step_id} is no longer pending, skipping reminder")
            return {'skipped': True}
        
        # Send notifications to assigned users
        for user in step.assigned_users.all():
            send_workflow_notification.delay(
                workflow_id=step.workflow.id,
                step_id=step.id,
                user_id=user.id,
                notification_type='deadline_reminder',
                extra_data={'hours_before': hours_before}
            )
        
        return {'success': True, 'step_id': step_id}
        
    except WorkflowStep.DoesNotExist:
        logger.error(f"Workflow step {step_id} not found for reminder")
        return {'error': 'Step not found'}
    except Exception as e:
        logger.error(f"Workflow reminder error: {e}")
        return {'error': str(e)}

@shared_task
def auto_progress_workflow(workflow_id: int):
    """
    Auto-progress workflow if conditions are met
    """
    try:
        from .advanced_features.workflow_system import WorkflowEngine
        
        workflow = DocumentWorkflow.objects.get(id=workflow_id)
        engine = WorkflowEngine()
        
        # Check if current step can be auto-progressed
        current_step = workflow.steps.filter(step_number=workflow.current_step).first()
        
        if current_step and current_step.can_auto_progress():
            success = engine.auto_progress_step(current_step)
            
            if success:
                logger.info(f"Auto-progressed workflow {workflow_id} step {current_step.step_number}")
                return {'success': True, 'progressed': True}
        
        return {'success': True, 'progressed': False}
        
    except DocumentWorkflow.DoesNotExist:
        logger.error(f"Workflow {workflow_id} not found for auto-progress")
        return {'error': 'Workflow not found'}
    except Exception as e:
        logger.error(f"Auto-progress workflow error: {e}")
        return {'error': str(e)}

# Signature Tasks

@shared_task
def check_signature_status(request_id: int):
    """
    Check signature request status with external provider
    """
    try:
        from .advanced_features.signature_system import SignatureService
        
        signature_request = SignatureRequest.objects.get(id=request_id)
        service = SignatureService(signature_request.provider)
        
        # Check status with provider
        status_info = service.check_request_status(signature_request.external_id)
        
        if status_info['success']:
            old_status = signature_request.status
            signature_request.status = status_info['status']
            
            if status_info['status'] == SignatureStatus.COMPLETED.value:
                signature_request.completed_at = timezone.now()
            
            signature_request.save()
            
            # If status changed, send notifications
            if old_status != signature_request.status:
                send_signature_status_notification.delay(request_id, old_status, signature_request.status)
        
        return status_info
        
    except SignatureRequest.DoesNotExist:
        logger.error(f"Signature request {request_id} not found for status check")
        return {'error': 'Request not found'}
    except Exception as e:
        logger.error(f"Signature status check error: {e}")
        return {'error': str(e)}

@shared_task
def send_signature_reminders():
    """
    Send reminders for pending signature requests
    """
    try:
        # Find signature requests that need reminders
        cutoff_date = timezone.now() - timedelta(days=3)  # 3 days old
        
        pending_requests = SignatureRequest.objects.filter(
            status__in=[SignatureStatus.SENT.value, SignatureStatus.DELIVERED.value],
            created_at__lte=cutoff_date,
            metadata__last_reminder__isnull=True  # No reminder sent yet
        ).select_related('document')
        
        reminder_count = 0
        
        for request in pending_requests:
            # Send reminder to each signer
            signers = request.signers_data.get('signers', [])
            
            for signer in signers:
                send_signature_reminder_email.delay(
                    request_id=request.id,
                    signer_email=signer['email'],
                    signer_name=signer['name']
                )
                reminder_count += 1
            
            # Mark reminder as sent
            if not request.metadata:
                request.metadata = {}
            request.metadata['last_reminder'] = timezone.now().isoformat()
            request.save()
        
        logger.info(f"Sent {reminder_count} signature reminders for {pending_requests.count()} requests")
        
        return {
            'requests_processed': pending_requests.count(),
            'reminders_sent': reminder_count
        }
        
    except Exception as e:
        logger.error(f"Signature reminder error: {e}")
        return {'error': str(e)}

# Notification Tasks

@shared_task
def send_document_notification(document_id: int, notification_type: str, recipient_id: int, extra_data: Dict = None):
    """
    Send document-related notification
    """
    try:
        document = Document.objects.select_related('owned_by', 'case').get(id=document_id)
        recipient = User.objects.get(id=recipient_id)
        
        # Prepare notification data
        context = {
            'document': document,
            'recipient': recipient,
            'notification_type': notification_type,
            'extra_data': extra_data or {}
        }
        
        # Send email notification
        if recipient.email:
            subject = get_notification_subject(notification_type, document)
            message = render_to_string('document_editor/emails/document_notification.txt', context)
            html_message = render_to_string('document_editor/emails/document_notification.html', context)
            
            send_mail(
                subject=subject,
                message=message,
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient.email],
                fail_silently=False
            )
        
        # Send real-time notification via WebSocket
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f'notifications_{recipient_id}',
                {
                    'type': 'document_notification',
                    'notification': {
                        'type': notification_type,
                        'document_id': document_id,
                        'document_title': document.title,
                        'message': get_notification_message(notification_type, document),
                        'timestamp': timezone.now().isoformat()
                    }
                }
            )
        
        return {'success': True}
        
    except (Document.DoesNotExist, User.DoesNotExist) as e:
        logger.error(f"Notification error - object not found: {e}")
        return {'error': 'Object not found'}
    except Exception as e:
        logger.error(f"Document notification error: {e}")
        return {'error': str(e)}

@shared_task
def send_workflow_notification(workflow_id: int, step_id: int, user_id: int, notification_type: str, extra_data: Dict = None):
    """
    Send workflow-related notification
    """
    try:
        workflow = DocumentWorkflow.objects.select_related('document').get(id=workflow_id)
        step = WorkflowStep.objects.get(id=step_id)
        user = User.objects.get(id=user_id)
        
        context = {
            'workflow': workflow,
            'step': step,
            'user': user,
            'notification_type': notification_type,
            'extra_data': extra_data or {}
        }
        
        # Send email
        if user.email:
            subject = get_workflow_notification_subject(notification_type, workflow, step)
            message = render_to_string('document_editor/emails/workflow_notification.txt', context)
            html_message = render_to_string('document_editor/emails/workflow_notification.html', context)
            
            send_mail(
                subject=subject,
                message=message,
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False
            )
        
        # Send WebSocket notification
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f'notifications_{user_id}',
                {
                    'type': 'workflow_notification',
                    'notification': {
                        'type': notification_type,
                        'workflow_id': workflow_id,
                        'step_id': step_id,
                        'document_title': workflow.document.title,
                        'step_name': step.name,
                        'message': get_workflow_notification_message(notification_type, workflow, step),
                        'timestamp': timezone.now().isoformat()
                    }
                }
            )
        
        return {'success': True}
        
    except Exception as e:
        logger.error(f"Workflow notification error: {e}")
        return {'error': str(e)}

@shared_task
def send_signature_reminder_email(request_id: int, signer_email: str, signer_name: str):
    """
    Send signature reminder email
    """
    try:
        signature_request = SignatureRequest.objects.select_related('document').get(id=request_id)
        
        context = {
            'signature_request': signature_request,
            'signer_name': signer_name,
            'document': signature_request.document,
            'signing_url': f"{settings.SITE_URL}/signatures/sign/{request_id}/"
        }
        
        subject = f"Reminder: Please sign '{signature_request.document.title}'"
        message = render_to_string('document_editor/emails/signature_reminder.txt', context)
        html_message = render_to_string('document_editor/emails/signature_reminder.html', context)
        
        send_mail(
            subject=subject,
            message=message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[signer_email],
            fail_silently=False
        )
        
        return {'success': True}
        
    except Exception as e:
        logger.error(f"Signature reminder email error: {e}")
        return {'error': str(e)}

@shared_task
def send_ai_analysis_notification(document_id: int, analyses: Dict[str, str]):
    """
    Send notification about completed AI analysis
    """
    try:
        document = Document.objects.select_related('owned_by').get(id=document_id)
        
        context = {
            'document': document,
            'analyses': analyses,
            'analysis_count': len(analyses)
        }
        
        if document.owned_by and document.owned_by.email:
            subject = f"AI Analysis Complete: {document.title}"
            message = render_to_string('document_editor/emails/ai_analysis_complete.txt', context)
            html_message = render_to_string('document_editor/emails/ai_analysis_complete.html', context)
            
            send_mail(
                subject=subject,
                message=message,
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[document.owned_by.email],
                fail_silently=False
            )
        
        return {'success': True}
        
    except Exception as e:
        logger.error(f"AI analysis notification error: {e}")
        return {'error': str(e)}

@shared_task
def send_signature_status_notification(request_id: int, old_status: str, new_status: str):
    """
    Send notification about signature status change
    """
    try:
        signature_request = SignatureRequest.objects.select_related('document__owned_by').get(id=request_id)
        
        context = {
            'signature_request': signature_request,
            'old_status': old_status,
            'new_status': new_status,
            'document': signature_request.document
        }
        
        # Notify document owner
        if signature_request.document.owned_by and signature_request.document.owned_by.email:
            subject = f"Signature Status Update: {signature_request.document.title}"
            message = render_to_string('document_editor/emails/signature_status_update.txt', context)
            html_message = render_to_string('document_editor/emails/signature_status_update.html', context)
            
            send_mail(
                subject=subject,
                message=message,
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[signature_request.document.owned_by.email],
                fail_silently=False
            )
        
        # Send WebSocket notification
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f'signature_{request_id}',
                {
                    'type': 'signature_status_update',
                    'status': new_status,
                    'timestamp': timezone.now().isoformat()
                }
            )
        
        return {'success': True}
        
    except Exception as e:
        logger.error(f"Signature status notification error: {e}")
        return {'error': str(e)}

# Maintenance Tasks

@shared_task
def cleanup_old_document_versions():
    """
    Clean up old document versions to save storage
    """
    try:
        from django.conf import settings
        
        # Keep last N versions (configurable)
        keep_versions = getattr(settings, 'DOCUMENT_KEEP_VERSIONS', 10)
        
        # Find documents with more than keep_versions versions
        documents_with_many_versions = Document.objects.annotate(
            version_count=Count('version_history')
        ).filter(version_count__gt=keep_versions)
        
        deleted_count = 0
        
        for document in documents_with_many_versions:
            # Keep the latest versions, delete the rest
            versions_to_delete = document.version_history.order_by('-version_number')[keep_versions:]
            
            for version in versions_to_delete:
                version.delete()
                deleted_count += 1
        
        logger.info(f"Cleaned up {deleted_count} old document versions")
        
        return {'deleted_versions': deleted_count}
        
    except Exception as e:
        logger.error(f"Cleanup versions error: {e}")
        return {'error': str(e)}

@shared_task
def generate_usage_statistics():
    """
    Generate usage statistics for analytics
    """
    try:
        from django.db.models import Count
        from datetime import date
        
        today = date.today()
        
        stats = {
            'date': today.isoformat(),
            'documents': {
                'total': Document.objects.count(),
                'created_today': Document.objects.filter(created_at__date=today).count(),
                'by_type': list(Document.objects.values('document_type__name').annotate(count=Count('id'))),
                'by_status': list(Document.objects.values('status__name').annotate(count=Count('id')))
            },
            'templates': {
                'total': DocumentTemplate.objects.count(),
                'active': DocumentTemplate.objects.filter(is_active=True).count(),
                'usage': list(Document.objects.filter(template_used__isnull=False).values(
                    'template_used__name'
                ).annotate(count=Count('id')))
            },
            'workflows': {
                'active': DocumentWorkflow.objects.exclude(status='completed').count(),
                'completed_today': DocumentWorkflow.objects.filter(
                    completed_at__date=today
                ).count()
            },
            'signatures': {
                'pending': SignatureRequest.objects.filter(
                    status__in=['sent', 'delivered']
                ).count(),
                'completed_today': SignatureRequest.objects.filter(
                    completed_at__date=today
                ).count()
            }
        }
        
        # Save stats to cache or database for dashboard
        from django.core.cache import cache
        cache.set(f'usage_stats_{today.isoformat()}', stats, timeout=86400)  # 24 hours
        
        return stats
        
    except Exception as e:
        logger.error(f"Statistics generation error: {e}")
        return {'error': str(e)}

# Utility functions

def get_notification_subject(notification_type: str, document: Document) -> str:
    """Get email subject for notification type"""
    subjects = {
        'upload_processed': f"Document processed: {document.title}",
        'comment_added': f"New comment on: {document.title}",
        'document_shared': f"Document shared: {document.title}",
        'workflow_assigned': f"Workflow task assigned: {document.title}",
    }
    return subjects.get(notification_type, f"Document notification: {document.title}")

def get_notification_message(notification_type: str, document: Document) -> str:
    """Get notification message for type"""
    messages = {
        'upload_processed': f"Your document '{document.title}' has been processed and is ready for review.",
        'comment_added': f"A new comment has been added to '{document.title}'.",
        'document_shared': f"Document '{document.title}' has been shared with you.",
        'workflow_assigned': f"You have been assigned a workflow task for '{document.title}'.",
    }
    return messages.get(notification_type, f"Update for document '{document.title}'")

def get_workflow_notification_subject(notification_type: str, workflow: DocumentWorkflow, step: WorkflowStep) -> str:
    """Get workflow notification subject"""
    subjects = {
        'deadline_reminder': f"Workflow reminder: {step.name} - {workflow.document.title}",
        'deadline_overdue': f"OVERDUE: {step.name} - {workflow.document.title}",
        'step_assigned': f"New task assigned: {step.name} - {workflow.document.title}",
        'step_completed': f"Task completed: {step.name} - {workflow.document.title}",
    }
    return subjects.get(notification_type, f"Workflow update: {workflow.document.title}")

def get_workflow_notification_message(notification_type: str, workflow: DocumentWorkflow, step: WorkflowStep) -> str:
    """Get workflow notification message"""
    messages = {
        'deadline_reminder': f"Reminder: Your task '{step.name}' is due soon.",
        'deadline_overdue': f"URGENT: Your task '{step.name}' is overdue.",
        'step_assigned': f"You have been assigned to complete '{step.name}'.",
        'step_completed': f"Task '{step.name}' has been completed.",
    }
    return messages.get(notification_type, f"Workflow update for '{step.name}'")

# Periodic tasks setup (add to CELERY_BEAT_SCHEDULE in settings)
"""
CELERY_BEAT_SCHEDULE = {
    'check-workflow-deadlines': {
        'task': 'document_editor.tasks.check_workflow_deadlines',
        'schedule': crontab(minute=0),  # Every hour
    },
    'send-signature-reminders': {
        'task': 'document_editor.tasks.send_signature_reminders',
        'schedule': crontab(hour=9, minute=0),  # Daily at 9 AM
    },
    'cleanup-old-versions': {
        'task': 'document_editor.tasks.cleanup_old_document_versions',
        'schedule': crontab(hour=2, minute=0, day_of_week=1),  # Weekly on Monday at 2 AM
    },
    'generate-usage-stats': {
        'task': 'document_editor.tasks.generate_usage_statistics',
        'schedule': crontab(hour=23, minute=0),  # Daily at 11 PM
    },
}
"""
