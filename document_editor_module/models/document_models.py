"""
Advanced Document Models për Sistemin e Menaxhimit të Rasteve Juridike
Përfshin: Document editing, versioning, collaboration, templates, dhe LLM integration
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.core.validators import MinLengthValidator
import uuid
import json

User = get_user_model()

class DocumentTemplate(models.Model):
    """
    Template për dokumente standard juridike (padi, ankesa, kontrata, etj.)
    """
    name = models.CharField(max_length=255, verbose_name="Emri i Template")
    description = models.TextField(blank=True, verbose_name="Përshkrimi")
    category = models.CharField(max_length=100, verbose_name="Kategoria")
    content = models.TextField(verbose_name="Përmbajtja e Template")
    variables = models.JSONField(default=dict, blank=True, verbose_name="Variablat")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Krijuar nga")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Krijuar më")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Përditësuar më")
    
    class Meta:
        verbose_name = "Template Dokumenti"
        verbose_name_plural = "Template Dokumentesh"
        ordering = ['category', 'name']
    
    def __str__(self):
        return f"{self.category} - {self.name}"

class DocumentType(models.Model):
    """
    Llojet e dokumenteve (Padi, Ankesa, Kontratë, etj.)
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Emri")
    description = models.TextField(blank=True, verbose_name="Përshkrimi")
    default_template = models.ForeignKey(
        DocumentTemplate, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Template Default"
    )
    requires_signature = models.BooleanField(default=False, verbose_name="Kërkon Nënshkrim")
    is_legal_document = models.BooleanField(default=True, verbose_name="Dokument Ligjor")
    
    class Meta:
        verbose_name = "Tipi i Dokumentit"
        verbose_name_plural = "Llojet e Dokumenteve"
        ordering = ['name']
    
    def __str__(self):
        return self.name

class DocumentStatus(models.Model):
    """
    Statuset e dokumenteve (Draft, Review, Approved, Signed, etj.)
    """
    name = models.CharField(max_length=50, unique=True, verbose_name="Emri")
    description = models.TextField(blank=True, verbose_name="Përshkrimi")
    color = models.CharField(max_length=7, default="#6c757d", verbose_name="Ngjyra")
    is_final = models.BooleanField(default=False, verbose_name="Status Final")
    order = models.PositiveIntegerField(default=0, verbose_name="Renditja")
    
    class Meta:
        verbose_name = "Statusi i Dokumentit"
        verbose_name_plural = "Statuset e Dokumenteve"
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name

class Document(models.Model):
    """
    Model i zgjeruar për dokumente me mbështetje për editim dhe collaboration
    """
    # Identifikimi unik
    uid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    
    # Informacioni bazë
    title = models.CharField(max_length=255, verbose_name="Titulli")
    description = models.TextField(blank=True, verbose_name="Përshkrimi")
    
    # Relacionet
    case = models.ForeignKey(
        'cases.Case', 
        related_name='documents_advanced', 
        on_delete=models.CASCADE,
        verbose_name="Rasti"
    )
    document_type = models.ForeignKey(
        DocumentType, 
        on_delete=models.PROTECT,
        verbose_name="Tipi i Dokumentit"
    )
    status = models.ForeignKey(
        DocumentStatus, 
        on_delete=models.PROTECT,
        verbose_name="Statusi"
    )
    template_used = models.ForeignKey(
        DocumentTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Template i Përdorur"
    )
    
    # Përmbajtja
    content = models.TextField(verbose_name="Përmbajtja")
    content_html = models.TextField(blank=True, verbose_name="Përmbajtja HTML")
    metadata = models.JSONField(default=dict, blank=True, verbose_name="Metadata")
    
    # File attachment (opsional)
    file = models.FileField(
        upload_to='documents/%Y/%m/%d/', 
        blank=True, 
        null=True,
        verbose_name="File i Bashkangjitur"
    )
    
    # Versioning
    version_number = models.PositiveIntegerField(default=1, verbose_name="Numri i Versionit")
    parent_document = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='versions',
        verbose_name="Dokumenti Prind"
    )
    
    # Ownership dhe permissions
    created_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='created_documents',
        verbose_name="Krijuar nga"
    )
    owned_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='owned_documents',
        verbose_name="Në pronësi të"
    )
    editors = models.ManyToManyField(
        User, 
        through='DocumentEditor',
        related_name='editable_documents',
        verbose_name="Editorët"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Krijuar më")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Përditësuar më")
    last_edited_at = models.DateTimeField(null=True, blank=True, verbose_name="Edituar për herë të fundit")
    last_edited_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='last_edited_documents',
        verbose_name="Edituar për herë të fundit nga"
    )
    
    # Collaboration features
    is_locked = models.BooleanField(default=False, verbose_name="I Bllokuar")
    locked_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='locked_documents',
        verbose_name="Bllokuar nga"
    )
    locked_at = models.DateTimeField(null=True, blank=True, verbose_name="Bllokuar më")
    
    # LLM Integration fields
    llm_generated = models.BooleanField(default=False, verbose_name="Gjeneruar nga LLM")
    llm_suggestions = models.JSONField(default=list, blank=True, verbose_name="Sugjerimet e LLM")
    llm_last_analysis = models.DateTimeField(null=True, blank=True, verbose_name="Analiza e fundit e LLM")
    
    class Meta:
        verbose_name = "Dokument"
        verbose_name_plural = "Dokumente"
        ordering = ['-last_edited_at', '-created_at']
        indexes = [
            models.Index(fields=['case', 'status']),
            models.Index(fields=['document_type', 'status']),
            models.Index(fields=['created_by', 'status']),
            models.Index(fields=['last_edited_at']),
        ]
    
    def __str__(self):
        return f"{self.title} (v{self.version_number})"
    
    def save(self, *args, **kwargs):
        # Auto-set last_edited timestamps
        if self.pk:  # Updating existing document
            self.last_edited_at = timezone.now()
        super().save(*args, **kwargs)
    
    def get_latest_version(self):
        """Merr versionin më të fundit të dokumentit"""
        if self.parent_document:
            return self.parent_document.versions.order_by('-version_number').first()
        return self.versions.order_by('-version_number').first() or self
    
    def create_new_version(self, user, reason=""):
        """Krijo një version të ri të dokumentit"""
        latest = self.get_latest_version()
        new_version = Document.objects.create(
            title=self.title,
            description=self.description,
            case=self.case,
            document_type=self.document_type,
            status=self.status,
            template_used=self.template_used,
            content=self.content,
            content_html=self.content_html,
            metadata=self.metadata.copy() if self.metadata else {},
            version_number=(latest.version_number if latest else 0) + 1,
            parent_document=self.parent_document or self,
            created_by=user,
            owned_by=self.owned_by
        )
        return new_version
    
    def can_edit(self, user):
        """Kontrollon nëse user-i mund ta editojë dokumentin"""
        if self.is_locked and self.locked_by != user:
            return False
        return (
            user == self.owned_by or 
            user == self.created_by or 
            self.editors.filter(id=user.id).exists() or
            user.has_perm('documents.change_document')
        )
    
    def lock_document(self, user):
        """Blloko dokumentin për editim ekskluziv"""
        if not self.is_locked:
            self.is_locked = True
            self.locked_by = user
            self.locked_at = timezone.now()
            self.save(update_fields=['is_locked', 'locked_by', 'locked_at'])
            return True
        return False
    
    def unlock_document(self, user):
        """Çblloko dokumentin"""
        if self.is_locked and (self.locked_by == user or user.has_perm('documents.change_document')):
            self.is_locked = False
            self.locked_by = None
            self.locked_at = None
            self.save(update_fields=['is_locked', 'locked_by', 'locked_at'])
            return True
        return False

class DocumentEditor(models.Model):
    """
    Through model për të menaxhuar editorët e dokumenteve
    """
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    permission_level = models.CharField(
        max_length=20,
        choices=[
            ('view', 'Vetëm Shikimi'),
            ('edit', 'Editimi'),
            ('full', 'Kontroll i Plotë')
        ],
        default='edit'
    )
    added_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='added_editors'
    )
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['document', 'user']
        verbose_name = "Editor Dokumenti"
        verbose_name_plural = "Editorët e Dokumenteve"

class DocumentVersion(models.Model):
    """
    Model për të ruajtur historikun e versioneve të dokumenteve
    """
    document = models.ForeignKey(
        Document, 
        on_delete=models.CASCADE,
        related_name='version_history'
    )
    version_number = models.PositiveIntegerField()
    content_snapshot = models.TextField()
    content_html_snapshot = models.TextField(blank=True)
    metadata_snapshot = models.JSONField(default=dict)
    
    changes_summary = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Diff information
    added_content = models.TextField(blank=True)
    removed_content = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['document', 'version_number']
        verbose_name = "Versioni i Dokumentit"
        verbose_name_plural = "Versionet e Dokumenteve"
        ordering = ['-version_number']

class DocumentComment(models.Model):
    """
    Komente në dokumente për collaboration
    """
    document = models.ForeignKey(
        Document, 
        on_delete=models.CASCADE,
        related_name='comments'
    )
    content = models.TextField(validators=[MinLengthValidator(1)])
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Position in document (për inline comments)
    position_start = models.PositiveIntegerField(null=True, blank=True)
    position_end = models.PositiveIntegerField(null=True, blank=True)
    selected_text = models.TextField(blank=True)
    
    # Threading
    parent_comment = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='replies'
    )
    
    # Status
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='resolved_comments'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Koment Dokumenti"
        verbose_name_plural = "Komentet e Dokumenteve"
        ordering = ['position_start', 'created_at']

class LLMInteraction(models.Model):
    """
    Model për të ruajtur interaktimet me LLM për dokumente
    """
    document = models.ForeignKey(
        Document, 
        on_delete=models.CASCADE,
        related_name='llm_interactions'
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Request details
    interaction_type = models.CharField(
        max_length=50,
        choices=[
            ('generate', 'Gjenerim'),
            ('review', 'Rishikim'),
            ('suggest', 'Sugjerim'),
            ('translate', 'Përkthim'),
            ('summarize', 'Përmbledhje'),
            ('analyze', 'Analizë')
        ]
    )
    prompt = models.TextField()
    context_data = models.JSONField(default=dict, blank=True)
    
    # Response details
    llm_response = models.TextField()
    confidence_score = models.FloatField(null=True, blank=True)
    processing_time = models.FloatField(null=True, blank=True)  # në sekonda
    
    # Metadata
    llm_model = models.CharField(max_length=100, blank=True)
    llm_provider = models.CharField(max_length=50, blank=True)
    token_usage = models.JSONField(default=dict, blank=True)
    
    # User feedback
    was_helpful = models.BooleanField(null=True, blank=True)
    user_rating = models.PositiveIntegerField(null=True, blank=True)  # 1-5
    feedback_text = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Interaktim LLM"
        verbose_name_plural = "Interaktimet LLM"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['document', 'interaction_type']),
            models.Index(fields=['user', 'created_at']),
        ]

class DocumentAuditLog(models.Model):
    """
    Audit log i detajuar për dokumente
    """
    document = models.ForeignKey(
        Document, 
        on_delete=models.CASCADE,
        related_name='audit_logs'
    )
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    action = models.CharField(
        max_length=50,
        choices=[
            ('create', 'Krijim'),
            ('view', 'Shikimi'),
            ('edit', 'Editimi'),
            ('delete', 'Fshirje'),
            ('lock', 'Bllokim'),
            ('unlock', 'Çbllokim'),
            ('share', 'Ndarje'),
            ('download', 'Shkarkim'),
            ('print', 'Printim'),
            ('comment', 'Komentim'),
            ('llm_interaction', 'Interaktim LLM')
        ]
    )
    
    details = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Technical details
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Audit Log Dokumenti"
        verbose_name_plural = "Audit Logs Dokumentesh"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['document', 'action']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['timestamp']),
        ]

class DocumentSignature(models.Model):
    """
    Model për nënshkrime elektronike të dokumenteve
    """
    document = models.ForeignKey(
        Document, 
        on_delete=models.CASCADE,
        related_name='signatures'
    )
    signer = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Signature details
    signature_type = models.CharField(
        max_length=20,
        choices=[
            ('electronic', 'Elektronik'),
            ('digital', 'Dixhital'),
            ('biometric', 'Biometrik')
        ],
        default='electronic'
    )
    signature_data = models.TextField()  # Base64 encoded signature image or certificate
    signature_hash = models.CharField(max_length=256)  # Hash për verifikim
    
    # Verification
    is_verified = models.BooleanField(default=False)
    verification_method = models.CharField(max_length=100, blank=True)
    certificate_info = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    signed_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Technical details
    ip_address = models.GenericIPAddressField()
    device_info = models.JSONField(default=dict, blank=True)
    
    class Meta:
        unique_together = ['document', 'signer']
        verbose_name = "Nënshkrim Dokumenti"
        verbose_name_plural = "Nënshkrimet e Dokumenteve"
        ordering = ['-signed_at']
