# utils.py - Utility Functions për Legal Case Manager
import os
import hashlib
import uuid
import mimetypes
import magic
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, QuerySet
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)

# ==========================================
# FILE HANDLING UTILITIES
# ==========================================

def validate_document_file(uploaded_file: UploadedFile) -> Dict[str, Any]:
    """
    Validon dokumentin e ngarkuar
    
    Returns:
        Dict me informacion për file-in ose errors
    """
    result = {
        'valid': False,
        'errors': [],
        'file_info': {}
    }
    
    # Check file size
    max_size = settings.LEGAL_MANAGER.get('MAX_DOCUMENT_SIZE_MB', 50) * 1024 * 1024  # Convert to bytes
    if uploaded_file.size > max_size:
        result['errors'].append(f"File size exceeds maximum allowed size of {max_size // (1024*1024)}MB")
        return result
    
    # Detect file type
    try:
        # Use python-magic për file type detection
        mime_type = magic.from_buffer(uploaded_file.read(1024), mime=True)
        uploaded_file.seek(0)  # Reset file pointer
        
        # Get file extension
        file_extension = os.path.splitext(uploaded_file.name)[1].lower().lstrip('.')
        
        # Check if file type is allowed
        allowed_types = settings.LEGAL_MANAGER.get('ALLOWED_DOCUMENT_TYPES', [])
        if file_extension not in allowed_types:
            result['errors'].append(f"File type '{file_extension}' is not allowed")
            return result
        
        # Calculate file hash për duplicate detection
        file_hash = calculate_file_hash(uploaded_file)
        
        result['file_info'] = {
            'mime_type': mime_type,
            'file_extension': file_extension,
            'file_size': uploaded_file.size,
            'file_hash': file_hash,
            'original_name': uploaded_file.name
        }
        
        result['valid'] = True
        
    except Exception as e:
        result['errors'].append(f"Error validating file: {str(e)}")
    
    return result

def calculate_file_hash(uploaded_file: UploadedFile) -> str:
    """
    Llogarit SHA-256 hash të file-it për duplicate detection
    """
    hash_sha256 = hashlib.sha256()
    
    # Read file në chunks për të mos ngarkuar të gjithë file-in në memory
    for chunk in uploaded_file.chunks():
        hash_sha256.update(chunk)
    
    uploaded_file.seek(0)  # Reset file pointer
    return hash_sha256.hexdigest()

def generate_unique_filename(original_filename: str, user_id: int = None) -> str:
    """
    Gjeneron filename unik për të shmangur conflicts
    """
    # Get file extension
    name, ext = os.path.splitext(original_filename)
    
    # Create unique identifier
    unique_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if user_id:
        return f"{timestamp}_{user_id}_{unique_id}_{name}{ext}"
    else:
        return f"{timestamp}_{unique_id}_{name}{ext}"

def format_file_size(size_bytes: int) -> str:
    """
    Formatizuje file size në human-readable format
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

def extract_text_from_file(file_path: str) -> Optional[str]:
    """
    Ekstrakton tekst nga file (PDF, DOC, etc.)
    """
    try:
        file_extension = os.path.splitext(file_path)[1].lower()
        
        if file_extension == '.pdf':
            import PyPDF2
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text()
                return text
                
        elif file_extension in ['.doc', '.docx']:
            from docx import Document
            doc = Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
            
        elif file_extension == '.txt':
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
                
        else:
            logger.warning(f"Text extraction not supported for file type: {file_extension}")
            return None
            
    except Exception as e:
        logger.error(f"Error extracting text from file {file_path}: {str(e)}")
        return None

# ==========================================
# SEARCH & FILTERING UTILITIES
# ==========================================

def build_search_query(model_class, search_fields: List[str], search_term: str) -> Q:
    """
    Ndërton Q object për search në multiple fields
    """
    if not search_term:
        return Q()
    
    query = Q()
    search_terms = search_term.split()
    
    for term in search_terms:
        term_query = Q()
        for field in search_fields:
            term_query |= Q(**{f"{field}__icontains": term})
        query &= term_query
    
    return query

def apply_date_filters(queryset: QuerySet, date_field: str, date_params: Dict[str, str]) -> QuerySet:
    """
    Aplikor date filters në queryset
    """
    if 'start_date' in date_params and date_params['start_date']:
        try:
            start_date = datetime.strptime(date_params['start_date'], '%Y-%m-%d').date()
            queryset = queryset.filter(**{f"{date_field}__gte": start_date})
        except ValueError:
            pass
    
    if 'end_date' in date_params and date_params['end_date']:
        try:
            end_date = datetime.strptime(date_params['end_date'], '%Y-%m-%d').date()
            queryset = queryset.filter(**{f"{date_field}__lte": end_date})
        except ValueError:
            pass
    
    return queryset

def get_user_accessible_objects(user, model_class, field_name: str = 'created_by') -> QuerySet:
    """
    Merr objektet që user ka akses
    """
    queryset = model_class.objects.all()
    
    if user.role == 'admin':
        return queryset
    elif user.role == 'client':
        # Klientët shohin vetëm objektet e lidhura me ta
        if model_class.__name__ == 'Case':
            return queryset.filter(client__user=user)
        elif model_class.__name__ == 'Document':
            return queryset.filter(
                Q(**{f"{field_name}": user}) |
                Q(access_level='public') |
                Q(documentcaserelation__case__client__user=user)
            ).distinct()
    else:
        # Lawyer/paralegal shohin objektet e tyre dhe ato public
        return queryset.filter(
            Q(**{f"{field_name}": user}) |
            Q(access_level__in=['public', 'internal'])
        ).distinct()
    
    return queryset.none()

# ==========================================
# PERMISSION UTILITIES
# ==========================================

def check_document_permission(user, document, action: str) -> bool:
    """
    Kontrollon nëse user ka permission për action në document
    
    Args:
        user: User object
        document: Document object
        action: 'view', 'download', 'edit', 'delete', 'share'
    """
    # Admin ka akses të plotë
    if user.role == 'admin':
        return True
    
    # Krijuesi ka akses të plotë
    if document.created_by == user:
        return True
    
    # Kontrollo access level
    if action in ['view', 'download']:
        if document.access_level == 'public':
            return True
        
        if document.access_level == 'internal' and user.role in ['lawyer', 'paralegal']:
            return True
    
    # Kontrollo access controls specifike
    from .models_improved import DocumentAccess
    
    # User-specific access
    user_access = DocumentAccess.objects.filter(document=document, user=user).first()
    if user_access:
        if user_access.expires_at and user_access.expires_at < timezone.now():
            return False  # Access expired
        
        return getattr(user_access, f'can_{action}', False)
    
    # Role-based access
    role_access = DocumentAccess.objects.filter(document=document, role=user.role).first()
    if role_access:
        if role_access.expires_at and role_access.expires_at < timezone.now():
            return False  # Access expired
        
        return getattr(role_access, f'can_{action}', False)
    
    return False

def get_user_permissions_for_document(user, document) -> Dict[str, bool]:
    """
    Merr të gjitha permissions që user ka për dokumentin
    """
    permissions = {
        'can_view': check_document_permission(user, document, 'view'),
        'can_download': check_document_permission(user, document, 'download'),
        'can_edit': check_document_permission(user, document, 'edit'),
        'can_delete': check_document_permission(user, document, 'delete'),
        'can_share': check_document_permission(user, document, 'share'),
    }
    
    return permissions

# ==========================================
# DATA EXPORT UTILITIES
# ==========================================

def export_cases_to_csv(queryset: QuerySet) -> str:
    """
    Eksporton rastet në CSV format
    """
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers
    writer.writerow([
        'UID', 'Title', 'Client', 'Assigned To', 'Case Type', 
        'Status', 'Created At', 'Updated At'
    ])
    
    # Data
    for case in queryset.select_related('client', 'assigned_to'):
        writer.writerow([
            case.uid,
            case.title,
            case.client.full_name,
            case.assigned_to.username if case.assigned_to else '',
            case.get_case_type_display(),
            case.get_status_display(),
            case.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            case.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    return output.getvalue()

def export_documents_to_csv(queryset: QuerySet) -> str:
    """
    Eksporton dokumentet në CSV format
    """
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers
    writer.writerow([
        'UID', 'Title', 'Document Type', 'Status', 'Is Template',
        'Access Level', 'Created By', 'File Size', 'Created At'
    ])
    
    # Data
    for doc in queryset.select_related('document_type', 'status', 'created_by'):
        writer.writerow([
            doc.uid,
            doc.title,
            doc.document_type.name,
            doc.status.name,
            'Yes' if doc.is_template else 'No',
            doc.get_access_level_display(),
            doc.created_by.username if doc.created_by else '',
            format_file_size(doc.file_size) if doc.file_size else '',
            doc.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    return output.getvalue()

# ==========================================
# DATE & TIME UTILITIES
# ==========================================

def get_business_days_between(start_date: datetime, end_date: datetime) -> int:
    """
    Llogarit ditët e punës midis dy datave
    """
    from datetime import timedelta
    
    business_days = 0
    current_date = start_date.date()
    end_date = end_date.date()
    
    while current_date <= end_date:
        if current_date.weekday() < 5:  # Monday = 0, Sunday = 6
            business_days += 1
        current_date += timedelta(days=1)
    
    return business_days

def get_next_business_day(date: datetime, days_ahead: int = 1) -> datetime:
    """
    Merr ditën e ardhshme të punës
    """
    from datetime import timedelta
    
    current_date = date
    days_added = 0
    
    while days_added < days_ahead:
        current_date += timedelta(days=1)
        if current_date.weekday() < 5:  # Business day
            days_added += 1
    
    return current_date

def is_deadline_approaching(deadline: datetime, warning_days: int = 3) -> Dict[str, Any]:
    """
    Kontrollon nëse deadline po afrohet
    """
    now = timezone.now()
    days_until = (deadline - now).days
    
    return {
        'is_approaching': days_until <= warning_days and days_until >= 0,
        'is_overdue': days_until < 0,
        'days_until': days_until,
        'urgency_level': (
            'critical' if days_until <= 1 else
            'high' if days_until <= 3 else
            'medium' if days_until <= 7 else
            'low'
        )
    }

# ==========================================
# VALIDATION UTILITIES
# ==========================================

def validate_email_list(email_string: str) -> Tuple[List[str], List[str]]:
    """
    Validon listë email-esh të ndarë me virgulë
    
    Returns:
        Tuple: (valid_emails, invalid_emails)
    """
    import re
    
    email_regex = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    emails = [email.strip() for email in email_string.split(',') if email.strip()]
    valid_emails = []
    invalid_emails = []
    
    for email in emails:
        if email_regex.match(email):
            valid_emails.append(email)
        else:
            invalid_emails.append(email)
    
    return valid_emails, invalid_emails

def validate_json_field(value: str) -> Any:
    """
    Validon JSON field
    """
    if not value:
        return {}
    
    try:
        import json
        return json.loads(value)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON format: {str(e)}")

# ==========================================
# API UTILITIES
# ==========================================

def custom_exception_handler(exc, context):
    """
    Custom exception handler për DRF
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    if response is not None:
        custom_response_data = {
            'error': {
                'status_code': response.status_code,
                'message': 'An error occurred',
                'details': response.data
            }
        }
        
        # Add specific error messages për common cases
        if response.status_code == 400:
            custom_response_data['error']['message'] = 'Bad Request'
        elif response.status_code == 401:
            custom_response_data['error']['message'] = 'Authentication required'
        elif response.status_code == 403:
            custom_response_data['error']['message'] = 'Permission denied'
        elif response.status_code == 404:
            custom_response_data['error']['message'] = 'Resource not found'
        elif response.status_code == 500:
            custom_response_data['error']['message'] = 'Internal server error'
        
        response.data = custom_response_data
    
    return response

def paginate_queryset(queryset: QuerySet, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    """
    Manual pagination për queryset
    """
    from django.core.paginator import Paginator
    
    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(page)
    
    return {
        'results': list(page_obj),
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total_pages': paginator.num_pages,
            'total_count': paginator.count,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        }
    }

# ==========================================
# SECURITY UTILITIES
# ==========================================

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename për siguri
    """
    import re
    
    # Remove or replace unsafe characters
    filename = re.sub(r'[^\w\s-.]', '', filename)
    filename = re.sub(r'[-\s]+', '-', filename)
    
    return filename

def get_client_ip(request) -> str:
    """
    Merr IP address të klientit
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def log_user_action(user, action: str, target_type: str = None, target_id: str = None, 
                   metadata: Dict[str, Any] = None, request=None):
    """
    Log user action në audit log
    """
    from .models_improved import AuditLog
    
    audit_data = {
        'user': user,
        'action': action,
        'target_type': target_type,
        'target_id': str(target_id) if target_id else None,
        'metadata': metadata or {}
    }
    
    if request:
        audit_data['metadata']['ip_address'] = get_client_ip(request)
        audit_data['metadata']['user_agent'] = request.META.get('HTTP_USER_AGENT', '')
    
    return AuditLog.objects.create(**audit_data)

# ==========================================
# TEMPLATE UTILITIES
# ==========================================

def process_template_variables(template_content: str, variables: Dict[str, Any]) -> str:
    """
    Proces template variables në content
    """
    import re
    
    def replace_variable(match):
        var_name = match.group(1)
        return str(variables.get(var_name, match.group(0)))
    
    # Replace {{variable_name}} patterns
    processed_content = re.sub(r'\{\{(\w+)\}\}', replace_variable, template_content)
    
    return processed_content

def get_available_template_variables(template_content: str) -> List[str]:
    """
    Ekstrakton available template variables nga content
    """
    import re
    
    variables = re.findall(r'\{\{(\w+)\}\}', template_content)
    return list(set(variables))
