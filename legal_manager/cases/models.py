from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice
import uuid

# Custom User model with extended functionality
class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('lawyer', 'Lawyer'),
        ('paralegal', 'Paralegal'),
        ('client', 'Client'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='lawyer')
    is_2fa_enabled = models.BooleanField(default=False)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    # Override related_name to avoid conflicts
    groups = models.ManyToManyField(
        Group,
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name="custom_user_groups",
        related_query_name="user",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name="custom_user_permissions",
        related_query_name="user",
    )

    def __str__(self):
        return f"{self.username} ({self.role})"
    
    # Statistical methods for dashboard and profile
    def get_assigned_cases_count(self):
        return self.assigned_cases.count()
    
    def get_open_cases_count(self):
        return self.assigned_cases.filter(status='open').count()
    
    def get_closed_cases_count(self):
        return self.assigned_cases.filter(status='closed').count()
    
    def get_time_entries_count(self):
        return self.timeentry_set.count()
    
    def get_uploaded_documents_count(self):
        return self.casedocument_set.count()

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile of {self.user.username}"

class Client(models.Model):
    full_name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True)
    organization = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name

class Case(models.Model):
    CASE_TYPE = [
        ("civil", "Civil"), 
        ("criminal", "Criminal"), 
        ("family", "Family"), 
        ("commercial", "Commercial")
    ]
    STATUS = [
        ("open", "Open"), 
        ("in_court", "In court"), 
        ("appeal", "Appeal"), 
        ("closed", "Closed")
    ]

    uid = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=512)
    description = models.TextField(blank=True)
    client = models.ForeignKey(Client, related_name="cases", on_delete=models.CASCADE)
    assigned_to = models.ForeignKey(
        User, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL, 
        related_name="assigned_cases"
    )
    case_type = models.CharField(max_length=30, choices=CASE_TYPE, default="civil")
    status = models.CharField(max_length=30, choices=STATUS, default="open")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.uid:
            self.uid = str(uuid.uuid4().hex)[:32]  # Generate unique UID automatically
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.uid} - {self.title}"

class CaseDocument(models.Model):
    """Enhanced Document model with version control and file management"""
    
    DOCUMENT_TYPES = [
        ('contract', 'Contract'),
        ('legal_brief', 'Legal Brief'),
        ('evidence', 'Evidence'),
        ('correspondence', 'Correspondence'),
        ('court_filing', 'Court Filing'),
        ('report', 'Report'),
        ('invoice', 'Invoice'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('review', 'Under Review'),
        ('approved', 'Approved'),
        ('final', 'Final'),
        ('archived', 'Archived'),
    ]
    
    case = models.ForeignKey(Case, related_name="documents", on_delete=models.CASCADE)
    uploaded_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    file = models.FileField(upload_to="case_documents/%Y/%m/%d/")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    doc_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES, default='other')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    version = models.PositiveIntegerField(default=1)
    file_size = models.PositiveIntegerField(null=True, blank=True)  # in bytes
    file_hash = models.CharField(max_length=64, blank=True)  # SHA256 hash for integrity
    is_confidential = models.BooleanField(default=False)
    download_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.file:
            self.file_size = self.file.size
            # Generate hash for file integrity (will implement in views)
        super().save(*args, **kwargs)

    def get_file_extension(self):
        if self.file:
            return self.file.name.split('.')[-1].lower()
        return None
    
    def get_file_icon(self):
        """Return Bootstrap icon class based on file type"""
        ext = self.get_file_extension()
        icon_map = {
            'pdf': 'bi-file-earmark-pdf',
            'doc': 'bi-file-earmark-word',
            'docx': 'bi-file-earmark-word',
            'xls': 'bi-file-earmark-excel',
            'xlsx': 'bi-file-earmark-excel',
            'ppt': 'bi-file-earmark-ppt',
            'pptx': 'bi-file-earmark-ppt',
            'txt': 'bi-file-earmark-text',
            'jpg': 'bi-file-earmark-image',
            'jpeg': 'bi-file-earmark-image',
            'png': 'bi-file-earmark-image',
            'zip': 'bi-file-earmark-zip',
        }
        return icon_map.get(ext, 'bi-file-earmark')
    
    def get_human_readable_size(self):
        """Convert file size to human readable format"""
        if not self.file_size:
            return "Unknown"
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if self.file_size < 1024.0:
                return f"{self.file_size:.1f} {unit}"
            self.file_size /= 1024.0
        return f"{self.file_size:.1f} TB"

    def __str__(self):
        return f"{self.title} (v{self.version})"

    class Meta:
        ordering = ["-created_at"]
        unique_together = ['case', 'title', 'version']

class DocumentVersion(models.Model):
    """Track document version history"""
    document = models.ForeignKey(CaseDocument, related_name='versions', on_delete=models.CASCADE)
    version_number = models.PositiveIntegerField()
    file = models.FileField(upload_to="document_versions/%Y/%m/%d/")
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    change_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-version_number']
        unique_together = ['document', 'version_number']

class DocumentAccess(models.Model):
    """Track document access and downloads"""
    document = models.ForeignKey(CaseDocument, related_name='access_logs', on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=[
        ('view', 'Viewed'),
        ('download', 'Downloaded'),
        ('edit', 'Edited'),
        ('delete', 'Deleted'),
    ])
    ip_address = models.GenericIPAddressField(null=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

# Event Type classifications
class EventType(models.Model):
    name = models.CharField(max_length=50, unique=True)  # e.g. 'Seancë Gjyqësore', 'Takim Klienti', 'Afat Dorëzimi'
    color = models.CharField(max_length=7, default='#007bff')  # Hex color for calendar display
    is_deadline = models.BooleanField(default=False)  # Whether this type represents a deadline
    
    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Event Type"
        verbose_name_plural = "Event Types"

class CaseEvent(models.Model):
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'), 
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    case = models.ForeignKey(Case, related_name="events", on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)  # Renamed from notes for consistency
    event_type = models.ForeignKey(EventType, null=True, blank=True, on_delete=models.SET_NULL)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    
    # Date and time fields
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    is_all_day = models.BooleanField(default=False)
    
    # Reminder settings
    reminder_minutes = models.PositiveIntegerField(default=60)  # Minutes before event
    reminder_sent = models.BooleanField(default=False)  # Track if reminder was sent
    
    # Additional properties
    location = models.CharField(max_length=255, blank=True)  # Meeting location
    attendees = models.ManyToManyField(User, related_name='events_attending', blank=True)
    is_recurring = models.BooleanField(default=False)  # For future recurring events
    
    # Metadata
    created_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='events_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Legacy field for backward compatibility
    is_deadline = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.title} - {self.starts_at.strftime('%Y-%m-%d %H:%M')}"
    
    def get_calendar_color(self):
        """Return color for calendar display"""
        if self.event_type:
            return self.event_type.color
        elif self.is_deadline or (self.event_type and self.event_type.is_deadline):
            return '#dc3545'  # Red for deadlines
        elif self.priority == 'urgent':
            return '#fd7e14'  # Orange for urgent
        elif self.priority == 'high':
            return '#ffc107'  # Yellow for high
        else:
            return '#007bff'  # Blue for normal
    
    def is_past_due(self):
        """Check if event is past due"""
        from django.utils import timezone
        return self.starts_at < timezone.now()
    
    def get_attendees_list(self):
        """Get comma-separated list of attendees"""
        return ', '.join([user.get_full_name() or user.username for user in self.attendees.all()])
    
    class Meta:
        ordering = ['starts_at']
        indexes = [
            models.Index(fields=['starts_at']),
            models.Index(fields=['case', 'starts_at']),
        ]

class TimeEntry(models.Model):
    case = models.ForeignKey(Case, related_name="time_entries", on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    minutes = models.PositiveIntegerField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Invoice(models.Model):
    case = models.ForeignKey(Case, related_name="invoices", on_delete=models.CASCADE)
    issued_to = models.ForeignKey(Client, on_delete=models.CASCADE)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid = models.BooleanField(default=False)
    issued_at = models.DateTimeField(default=timezone.now)

# Audit log for sensitive actions
class AuditLog(models.Model):
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=255)
    target_type = models.CharField(max_length=100)
    target_id = models.CharField(max_length=255)
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

# User audit log for user-specific actions
class UserAuditLog(models.Model):
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=255)  # e.g. 'login', 'profile_update'
    ip_address = models.GenericIPAddressField(null=True)
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

# Import additional models
from .models_billing import *
from .models_client_portal import *  
from .models_analytics import *
