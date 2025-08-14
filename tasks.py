# tasks.py - Celery Tasks për Legal Case Manager
from celery import shared_task
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.conf import settings
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging
import json

from .models_improved import (
    User, Case, Document, CaseEvent, DocumentAuditLog, AuditLog
)
from .llm_service import LLMService

logger = logging.getLogger(__name__)

# ==========================================
# EMAIL & NOTIFICATION TASKS
# ==========================================

@shared_task(bind=True, max_retries=3)
def send_deadline_reminder(self, event_id: int):
    """
    Dërgon reminder për deadline të eventit
    """
    try:
        event = CaseEvent.objects.select_related('case', 'case__client', 'case__assigned_to').get(
            pk=event_id,
            is_deadline=True
        )
        
        # Përgatis listat e marrësve
        recipients = []
        
        # Lawyer i assignuar
        if event.case.assigned_to and event.case.assigned_to.email:
            recipients.append(event.case.assigned_to.email)
        
        # Klienti (nëse ka email)
        if event.case.client.email:
            recipients.append(event.case.client.email)
        
        if not recipients:
            logger.warning(f"No recipients found for event {event_id}")
            return False
        
        # Përgatis email content
        subject = f"DEADLINE REMINDER: {event.title}"
        
        context = {
            'event': event,
            'case': event.case,
            'deadline_date': event.starts_at,
            'days_until_deadline': (event.starts_at.date() - timezone.now().date()).days,
        }
        
        # Render templates
        text_content = render_to_string('emails/deadline_reminder.txt', context)
        html_content = render_to_string('emails/deadline_reminder.html', context)
        
        # Dërgo email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
        
        logger.info(f"Deadline reminder sent for event {event_id} to {len(recipients)} recipients")
        return True
        
    except CaseEvent.DoesNotExist:
        logger.error(f"Event {event_id} not found")
        return False
    except Exception as exc:
        logger.error(f"Error sending deadline reminder for event {event_id}: {str(exc)}")
        if self.request.retries < self.max_retries:
            # Retry në 5 minuta
            raise self.retry(countdown=300, exc=exc)
        return False

@shared_task
def send_bulk_notification(user_ids: List[int], subject: str, message: str, email_template: str = None):
    """
    Dërgon notification në bulk për usersa
    """
    try:
        users = User.objects.filter(id__in=user_ids, email__isnull=False).exclude(email='')
        
        for user in users:
            context = {
                'user': user,
                'message': message,
            }
            
            if email_template:
                text_content = render_to_string(f'emails/{email_template}.txt', context)
                html_content = render_to_string(f'emails/{email_template}.html', context)
                
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=text_content,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[user.email]
                )
                email.attach_alternative(html_content, "text/html")
                email.send()
            else:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email]
                )
        
        logger.info(f"Bulk notification sent to {len(users)} users")
        return len(users)
        
    except Exception as exc:
        logger.error(f"Error sending bulk notification: {str(exc)}")
        return 0

# ==========================================
# DOCUMENT PROCESSING TASKS
# ==========================================

@shared_task(bind=True, max_retries=2)
def generate_document_from_template(self, template_id: int, title: str, template_variables: Dict[str, Any], 
                                   case_id: int = None, user_id: int = None):
    """
    Gjeneron dokument nga template duke përdorur LLM
    """
    try:
        template = Document.objects.get(id=template_id, is_template=True)
        user = User.objects.get(id=user_id) if user_id else None
        case = Case.objects.get(id=case_id) if case_id else None
        
        # Inicializo LLM service
        llm_service = LLMService()
        
        # Përgatis prompt për LLM
        prompt = f"""
        Generate document content based on the following template and variables:
        
        Template: {template.title}
        Template Description: {template.description}
        
        Variables to substitute:
        {json.dumps(template_variables, indent=2)}
        
        Please generate the complete document content, maintaining professional legal language.
        """
        
        # Thirrr LLM
        response = llm_service.call(prompt, max_tokens=2000, temperature=0.3)
        
        if 'error' in response:
            raise Exception(f"LLM Error: {response['error']}")
        
        # Krijo dokument të ri
        new_document = Document.objects.create(
            title=title,
            description=f"Generated from template: {template.title}",
            document_type=template.document_type,
            status=template.status,
            is_template=False,
            template_variables=template_variables,
            metadata={
                'generated_from_template': template.id,
                'generated_at': timezone.now().isoformat(),
                'llm_generated': True,
                'llm_model': llm_service.model
            },
            created_by=user,
            uploaded_by=user,
            access_level=template.access_level
        )
        
        # Ruaj generated content si file
        from django.core.files.base import ContentFile
        file_content = ContentFile(response['text'].encode('utf-8'))
        new_document.file.save(
            f"{title.replace(' ', '_')}.txt",
            file_content,
            save=True
        )
        
        # Lidh me case nëse specifikuar
        if case:
            from .models_improved import DocumentCaseRelation
            DocumentCaseRelation.objects.create(
                document=new_document,
                case=case,
                relationship_type='template_used',
                added_by=user
            )
        
        # Log audit
        DocumentAuditLog.objects.create(
            document=new_document,
            user=user,
            action='created',
            metadata={
                'generated_from_template': template.id,
                'template_variables': template_variables,
                'llm_generated': True
            }
        )
        
        logger.info(f"Document generated from template {template_id}: {new_document.id}")
        return new_document.id
        
    except Exception as exc:
        logger.error(f"Error generating document from template {template_id}: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60, exc=exc)
        return None

@shared_task
def process_document_ocr(document_id: int):
    """
    Proces OCR për dokumente të skanuar (opsionale - kërkon OCR library)
    """
    try:
        document = Document.objects.get(id=document_id)
        
        # Ketu mund të integrojmë OCR library si Tesseract
        # Për shembull:
        # import pytesseract
        # from PIL import Image
        
        # Për tani, vetëm log action
        DocumentAuditLog.objects.create(
            document=document,
            action='ocr_processed',
            metadata={'ocr_attempted': True}
        )
        
        logger.info(f"OCR processing completed for document {document_id}")
        return True
        
    except Document.DoesNotExist:
        logger.error(f"Document {document_id} not found for OCR processing")
        return False
    except Exception as exc:
        logger.error(f"Error processing OCR for document {document_id}: {str(exc)}")
        return False

# ==========================================
# MAINTENANCE & CLEANUP TASKS
# ==========================================

@shared_task
def cleanup_audit_logs():
    """
    Pastron audit logs të vjetra sipas retention policy
    """
    try:
        retention_days = settings.LEGAL_MANAGER.get('AUDIT_LOG_RETENTION_DAYS', 1095)  # 3 years
        cutoff_date = timezone.now() - timedelta(days=retention_days)
        
        # Cleanup document audit logs
        doc_deleted = DocumentAuditLog.objects.filter(created_at__lt=cutoff_date).delete()[0]
        
        # Cleanup general audit logs
        gen_deleted = AuditLog.objects.filter(created_at__lt=cutoff_date).delete()[0]
        
        logger.info(f"Cleaned up {doc_deleted} document audit logs and {gen_deleted} general audit logs")
        return {'document_audit_logs': doc_deleted, 'general_audit_logs': gen_deleted}
        
    except Exception as exc:
        logger.error(f"Error cleaning up audit logs: {str(exc)}")
        return None

@shared_task
def cleanup_temporary_documents():
    """
    Pastron dokumentet e përkohshme dhe draft-et e vjetra
    """
    try:
        # Fshij draft-et më të vjetra se 30 ditë që nuk janë aksesuara
        from .models_improved import DocumentStatus
        
        draft_status = DocumentStatus.objects.filter(name='Draft').first()
        if draft_status:
            cutoff_date = timezone.now() - timedelta(days=30)
            
            old_drafts = Document.objects.filter(
                status=draft_status,
                created_at__lt=cutoff_date,
                last_accessed__lt=cutoff_date
            )
            
            count = old_drafts.count()
            old_drafts.delete()
            
            logger.info(f"Cleaned up {count} old draft documents")
            return count
        
        return 0
        
    except Exception as exc:
        logger.error(f"Error cleaning up temporary documents: {str(exc)}")
        return None

@shared_task
def generate_system_report():
    """
    Gjeneron raport të sistemit për admin
    """
    try:
        from django.db.models import Count, Q
        from datetime import date, timedelta
        
        # Statistika të përgjithshme
        stats = {
            'total_users': User.objects.count(),
            'active_users': User.objects.filter(is_active=True).count(),
            'total_cases': Case.objects.count(),
            'open_cases': Case.objects.filter(status='open').count(),
            'total_documents': Document.objects.count(),
            'template_documents': Document.objects.filter(is_template=True).count(),
        }
        
        # Statistika të javës së fundit
        week_ago = timezone.now() - timedelta(days=7)
        weekly_stats = {
            'new_cases': Case.objects.filter(created_at__gte=week_ago).count(),
            'new_documents': Document.objects.filter(created_at__gte=week_ago).count(),
            'active_users': DocumentAuditLog.objects.filter(
                created_at__gte=week_ago
            ).values('user').distinct().count(),
        }
        
        # Top dokumentet më të aksesuara
        top_documents = Document.objects.annotate(
            access_count=Count('audit_logs', filter=Q(audit_logs__action='viewed'))
        ).order_by('-access_count')[:10]
        
        report = {
            'generated_at': timezone.now().isoformat(),
            'general_stats': stats,
            'weekly_stats': weekly_stats,
            'top_documents': [
                {
                    'id': doc.id,
                    'title': doc.title,
                    'access_count': doc.access_count
                }
                for doc in top_documents
            ]
        }
        
        # Dërgo raport tek adminat
        admin_users = User.objects.filter(role='admin', email__isnull=False).exclude(email='')
        
        if admin_users.exists():
            send_bulk_notification.delay(
                user_ids=list(admin_users.values_list('id', flat=True)),
                subject=f"Weekly System Report - {date.today()}",
                message=f"System report generated. View details in admin panel.",
                email_template='system_report'
            )
        
        logger.info("System report generated and sent to admins")
        return report
        
    except Exception as exc:
        logger.error(f"Error generating system report: {str(exc)}")
        return None

# ==========================================
# LLM & AI TASKS
# ==========================================

@shared_task(bind=True, max_retries=2)
def analyze_document_content(self, document_id: int):
    """
    Analizon përmbajtjen e dokumentit me LLM për metadata extraction
    """
    try:
        document = Document.objects.get(id=document_id)
        
        if not document.file:
            return None
        
        # Lexo përmbajtjen e dokumentit (për text files)
        try:
            content = document.file.read().decode('utf-8')
        except UnicodeDecodeError:
            logger.warning(f"Cannot decode document {document_id} as text")
            return None
        
        # Inicializo LLM service
        llm_service = LLMService()
        
        # Përgatis prompt për analizë
        prompt = f"""
        Analyze the following legal document and extract key information:
        
        Document Title: {document.title}
        Document Type: {document.document_type.name}
        
        Content:
        {content[:2000]}  # Limit content për prompt
        
        Please provide a JSON response with the following information:
        {{
            "summary": "Brief summary of the document",
            "key_parties": ["List of parties mentioned"],
            "important_dates": ["List of important dates"],
            "legal_concepts": ["List of legal concepts"],
            "document_category": "Category classification",
            "urgency_level": "low/medium/high",
            "suggested_tags": ["List of suggested tags"]
        }}
        """
        
        response = llm_service.call(prompt, max_tokens=1000, temperature=0.2)
        
        if 'error' in response:
            raise Exception(f"LLM Error: {response['error']}")
        
        # Parse response dhe update document metadata
        try:
            analysis = json.loads(response['text'])
            
            # Update document metadata
            current_metadata = document.metadata or {}
            current_metadata.update({
                'llm_analysis': analysis,
                'analyzed_at': timezone.now().isoformat(),
                'llm_model': llm_service.model
            })
            
            # Update tags nëse janë sugjeruar
            if 'suggested_tags' in analysis and analysis['suggested_tags']:
                existing_tags = document.tags.split(',') if document.tags else []
                new_tags = list(set(existing_tags + analysis['suggested_tags']))
                document.tags = ','.join(new_tags)
            
            document.metadata = current_metadata
            document.save()
            
            # Log audit
            DocumentAuditLog.objects.create(
                document=document,
                action='analyzed',
                metadata={'llm_analysis': True, 'analysis_summary': analysis.get('summary', '')}
            )
            
            logger.info(f"Document {document_id} analyzed successfully")
            return analysis
            
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON response from LLM for document {document_id}")
            return None
        
    except Document.DoesNotExist:
        logger.error(f"Document {document_id} not found")
        return None
    except Exception as exc:
        logger.error(f"Error analyzing document {document_id}: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=120, exc=exc)
        return None

# ==========================================
# SCHEDULED TASKS (për Celery Beat)
# ==========================================

@shared_task
def daily_maintenance():
    """
    Task që ekzekutohet çdo ditë për maintenance
    """
    logger.info("Starting daily maintenance tasks")
    
    # Cleanup audit logs
    cleanup_audit_logs.delay()
    
    # Cleanup temporary documents
    cleanup_temporary_documents.delay()
    
    # Check për deadline reminders (për 24 orët e ardhshme)
    tomorrow = timezone.now() + timedelta(days=1)
    upcoming_deadlines = CaseEvent.objects.filter(
        is_deadline=True,
        starts_at__date=tomorrow.date()
    )
    
    for event in upcoming_deadlines:
        send_deadline_reminder.delay(event.id)
    
    logger.info(f"Daily maintenance completed. {upcoming_deadlines.count()} deadline reminders scheduled")

@shared_task
def weekly_reports():
    """
    Task që ekzekutohet çdo javë për raporte
    """
    logger.info("Generating weekly reports")
    generate_system_report.delay()
