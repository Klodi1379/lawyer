from celery import shared_task
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
import logging
from .models import CaseEvent, AuditLog

logger = logging.getLogger(__name__)

@shared_task
def send_deadline_reminder(event_id):
    """
    Send deadline reminder email for a case event.
    
    Args:
        event_id: ID of the CaseEvent
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        event = CaseEvent.objects.get(pk=event_id)
    except CaseEvent.DoesNotExist:
        logger.error(f"CaseEvent with ID {event_id} does not exist")
        return False
    
    # Collect recipients
    recipients = []
    
    # Add assigned lawyer email
    if event.case.assigned_to and event.case.assigned_to.email:
        recipients.append(event.case.assigned_to.email)
    
    # Add client email
    if event.case.client.email:
        recipients.append(event.case.client.email)
    
    if not recipients:
        logger.warning(f"No recipients found for event {event_id}")
        return False
    
    # Prepare email content
    subject = f"Deadline Reminder: {event.title}"
    message = f"""
    This is a reminder for an upcoming deadline:
    
    Event: {event.title}
    Case: {event.case.uid} - {event.case.title}
    Client: {event.case.client.full_name}
    Deadline: {event.starts_at.strftime('%Y-%m-%d %H:%M')}
    
    Notes: {event.notes or 'No additional notes'}
    
    Please ensure all necessary actions are completed before the deadline.
    
    Best regards,
    Legal Case Management System
    """
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=None,  # Uses DEFAULT_FROM_EMAIL from settings
            recipient_list=recipients,
            fail_silently=False
        )
        
        # Log successful reminder
        AuditLog.objects.create(
            user=event.created_by,
            action='deadline_reminder_sent',
            target_type='CaseEvent',
            target_id=str(event.id),
            metadata={
                'event_title': event.title,
                'case_uid': event.case.uid,
                'recipients': recipients,
                'deadline': event.starts_at.isoformat()
            }
        )
        
        logger.info(f"Deadline reminder sent for event {event_id} to {len(recipients)} recipients")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send deadline reminder for event {event_id}: {str(e)}")
        return False

@shared_task
def check_upcoming_deadlines():
    """
    Check for upcoming deadlines and schedule reminder emails.
    This task should be run periodically (e.g., daily).
    
    Returns:
        int: Number of reminders scheduled
    """
    # Look for deadlines in the next 24-48 hours
    now = timezone.now()
    tomorrow = now + timedelta(days=1)
    day_after = now + timedelta(days=2)
    
    upcoming_events = CaseEvent.objects.filter(
        is_deadline=True,
        starts_at__gte=tomorrow,
        starts_at__lte=day_after
    )
    
    reminders_scheduled = 0
    
    for event in upcoming_events:
        # Check if reminder was already sent (to avoid duplicates)
        reminder_already_sent = AuditLog.objects.filter(
            action='deadline_reminder_sent',
            target_type='CaseEvent',
            target_id=str(event.id),
            created_at__gte=now - timedelta(days=3)  # Check last 3 days
        ).exists()
        
        if not reminder_already_sent:
            # Schedule reminder to be sent
            send_deadline_reminder.delay(event.id)
            reminders_scheduled += 1
    
    logger.info(f"Scheduled {reminders_scheduled} deadline reminders")
    return reminders_scheduled

@shared_task
def cleanup_old_audit_logs(days_to_keep=365):
    """
    Clean up old audit logs to prevent database bloat.
    
    Args:
        days_to_keep: Number of days to keep logs (default: 365)
        
    Returns:
        int: Number of logs deleted
    """
    cutoff_date = timezone.now() - timedelta(days=days_to_keep)
    
    # Delete old audit logs
    deleted_count, _ = AuditLog.objects.filter(created_at__lt=cutoff_date).delete()
    
    logger.info(f"Deleted {deleted_count} old audit log entries")
    return deleted_count

@shared_task
def generate_case_summary_report(case_id, user_id):
    """
    Generate a comprehensive case summary report.
    
    Args:
        case_id: ID of the case
        user_id: ID of the user requesting the report
        
    Returns:
        dict: Report data or error
    """
    try:
        from .models import Case, User
        
        case = Case.objects.get(pk=case_id)
        user = User.objects.get(pk=user_id)
        
        # Collect case data
        documents_count = case.documents.count()
        events_count = case.events.count()
        time_entries = case.time_entries.all()
        total_time_minutes = sum(entry.minutes for entry in time_entries)
        total_hours = total_time_minutes / 60.0
        
        invoices = case.invoices.all()
        total_billed = sum(invoice.total_amount for invoice in invoices)
        paid_amount = sum(invoice.total_amount for invoice in invoices if invoice.paid)
        
        report_data = {
            'case_uid': case.uid,
            'case_title': case.title,
            'client_name': case.client.full_name,
            'assigned_lawyer': case.assigned_to.get_full_name() if case.assigned_to else 'Unassigned',
            'case_type': case.get_case_type_display(),
            'status': case.get_status_display(),
            'created_date': case.created_at.strftime('%Y-%m-%d'),
            'documents_count': documents_count,
            'events_count': events_count,
            'total_hours_worked': round(total_hours, 2),
            'total_billed': float(total_billed),
            'total_paid': float(paid_amount),
            'outstanding_amount': float(total_billed - paid_amount),
        }
        
        # Log report generation
        AuditLog.objects.create(
            user=user,
            action='case_report_generated',
            target_type='Case',
            target_id=str(case.id),
            metadata=report_data
        )
        
        logger.info(f"Generated case summary report for case {case.uid}")
        return report_data
        
    except Exception as e:
        logger.error(f"Failed to generate case summary report: {str(e)}")
        return {'error': str(e)}

@shared_task
def backup_case_data(case_id):
    """
    Create a backup of case data for archival purposes.
    
    Args:
        case_id: ID of the case to backup
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        from .models import Case
        import json
        
        case = Case.objects.get(pk=case_id)
        
        # Serialize case data
        case_data = {
            'case': {
                'uid': case.uid,
                'title': case.title,
                'description': case.description,
                'case_type': case.case_type,
                'status': case.status,
                'created_at': case.created_at.isoformat(),
                'updated_at': case.updated_at.isoformat(),
            },
            'client': {
                'full_name': case.client.full_name,
                'email': case.client.email,
                'phone': case.client.phone,
                'organization': case.client.organization,
            },
            'documents': [
                {
                    'title': doc.title,
                    'doc_type': doc.doc_type,
                    'version': doc.version,
                    'created_at': doc.created_at.isoformat(),
                    'uploaded_by': doc.uploaded_by.username if doc.uploaded_by else None,
                }
                for doc in case.documents.all()
            ],
            'events': [
                {
                    'title': event.title,
                    'notes': event.notes,
                    'starts_at': event.starts_at.isoformat(),
                    'ends_at': event.ends_at.isoformat() if event.ends_at else None,
                    'is_deadline': event.is_deadline,
                }
                for event in case.events.all()
            ],
            'time_entries': [
                {
                    'user': entry.user.username,
                    'minutes': entry.minutes,
                    'description': entry.description,
                    'created_at': entry.created_at.isoformat(),
                }
                for entry in case.time_entries.all()
            ],
        }
        
        # Here you would typically save to a backup storage system
        # For now, we'll just log the backup creation
        
        logger.info(f"Created backup for case {case.uid}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to backup case data: {str(e)}")
        return False
