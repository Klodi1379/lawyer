# models_improved.py - Struktura e përmirësuar e dokumenteve
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid

# Custom user with role-based access
class User(AbstractUser):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("lawyer", "Lawyer"),
        ("paralegal", "Paralegal"),
        ("client", "Client"),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="lawyer")
    is_2fa_enabled = models.BooleanField(default=False)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"{self.username} ({self.role})"

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
    CASE_TYPE = [("civil", "Civil"), ("criminal", "Criminal"), ("family", "Family"), ("commercial", "Commercial")]
    STATUS = [("open", "Open"), ("in_court", "In court"), ("appeal", "Appeal"), ("closed", "Closed")]

    uid = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=512)
    description = models.TextField(blank=True)
    client = models.ForeignKey(Client, related_name="cases", on_delete=models.CASCADE)
    assigned_to = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_cases")
    case_type = models.CharField(max_length=30, choices=CASE_TYPE, default="civil")
    status = models.CharField(max_length=30, choices=STATUS, default="open")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.uid:
            self.uid = str(uuid.uuid4().hex)[:32]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.uid} - {self.title}"

    class Meta:
        ordering = ['-created_at']

# ==========================================
# STRUKTURA E RE E DOKUMENTEVE - MË FLEKSIBILE
# ==========================================

class DocumentCategory(models.Model):
    """Kategoritë e dokumenteve (p.sh. Templates, Legal Docs, Internal, etc.)"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default="#007bff")  # Hex color për UI

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Document Categories"

class DocumentType(models.Model):
    """Tipi i dokumentit (p.sh. Padi, Kontratë, Vendim, etc.)"""
    name = models.CharField(max_length=100)
    category = models.ForeignKey(DocumentCategory, on_delete=models.CASCADE, related_name="types")
    is_template = models.BooleanField(default=False)  # A është template që mund të kopjohet
    
    def __str__(self):
        return f"{self.name} ({self.category.name})"

    class Meta:
        unique_together = ['name', 'category']

class DocumentStatus(models.Model):
    """Statusi i dokumentit"""
    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default="#6c757d")  # Hex color
    is_final = models.BooleanField(default=False)  # A është status final

    def __str__(self):
        return self.name

class Document(models.Model):
    """
    Modeli kryesor i dokumentit - më fleksibël:
    - Mund të jetë i lidhur me case ose jo
    - Mund të jetë template i përgjithshëm
    - Mund të lidhet me shumë raste (nëpërmjet DocumentCaseRelation)
    """
    
    # Identifikimi unik
    uid = models.CharField(max_length=32, unique=True, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # File dhe metadata
    file = models.FileField(upload_to='documents/%Y/%m/%d/')
    file_size = models.PositiveIntegerField(null=True, blank=True)  # në bytes
    file_type = models.CharField(max_length=50, blank=True)  # mime type
    
    # Kategorizimi
    document_type = models.ForeignKey(DocumentType, on_delete=models.PROTECT)
    status = models.ForeignKey(DocumentStatus, on_delete=models.PROTECT)
    
    # Versionimi
    version = models.PositiveIntegerField(default=1)
    parent_document = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='versions')
    
    # Template info
    is_template = models.BooleanField(default=False)
    template_variables = models.JSONField(null=True, blank=True)  # Variablat që zëvendësohen në template
    
    # Metadata shtesë
    metadata = models.JSONField(null=True, blank=True)
    tags = models.CharField(max_length=500, blank=True)  # Tags të ndarë me virgulë
    
    # Siguriaq and ownership
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_documents')
    uploaded_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='uploaded_documents')
    is_confidential = models.BooleanField(default=True)
    access_level = models.CharField(max_length=20, choices=[
        ('public', 'Public'),
        ('internal', 'Internal Only'),
        ('restricted', 'Restricted'),
        ('confidential', 'Confidential')
    ], default='confidential')
    
    # Timestampe
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_accessed = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.uid:
            self.uid = str(uuid.uuid4().hex)[:32]
        
        # Auto-detect file info
        if self.file:
            self.file_size = self.file.size
            # Mund të shtojmë file type detection këtu
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} (v{self.version})"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['document_type', 'status']),
            models.Index(fields=['is_template']),
            models.Index(fields=['created_at']),
        ]

class DocumentCaseRelation(models.Model):
    """
    Many-to-Many relationship midis Document dhe Case
    Lejon një dokument të lidhet me shumë raste dhe anasjelltas
    """
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    case = models.ForeignKey(Case, on_delete=models.CASCADE)
    relationship_type = models.CharField(max_length=50, choices=[
        ('primary', 'Primary Document'),      # Dokument kryesor i rastit
        ('supporting', 'Supporting Document'), # Dokument përkrahës
        ('reference', 'Reference'),           # Referencë/shembull
        ('template_used', 'Template Used'),   # Template i përdorur për rastin
    ], default='primary')
    
    added_by = models.ForeignKey(User, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ['document', 'case', 'relationship_type']

class DocumentAccess(models.Model):
    """
    Kontrollon akseset specifike për dokumente
    Përdoret për kontroll të detajuar të aksesit
    """
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='access_controls')
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=User.ROLE_CHOICES, null=True, blank=True)
    
    can_view = models.BooleanField(default=True)
    can_download = models.BooleanField(default=True)
    can_edit = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    can_share = models.BooleanField(default=False)
    
    granted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='granted_accesses')
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['document', 'user']

# ==========================================
# MODELET E TJERA (të pandryshuara)
# ==========================================

class CaseEvent(models.Model):
    case = models.ForeignKey(Case, related_name="events", on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    notes = models.TextField(blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    is_deadline = models.BooleanField(default=False)

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

# Audit log për sensitive actions
class AuditLog(models.Model):
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=255)
    target_type = models.CharField(max_length=100)
    target_id = models.CharField(max_length=255)
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

# Audit log specifik për dokumente
class DocumentAuditLog(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='audit_logs')
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=255, choices=[
        ('created', 'Created'),
        ('viewed', 'Viewed'),
        ('downloaded', 'Downloaded'),
        ('updated', 'Updated'),
        ('deleted', 'Deleted'),
        ('shared', 'Shared'),
        ('access_granted', 'Access Granted'),
        ('access_revoked', 'Access Revoked'),
    ])
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
