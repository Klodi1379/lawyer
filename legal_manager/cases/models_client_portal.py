"""
Client Portal Models për Legal Case Manager
Përfshin: Client dashboard, secure document sharing, payment tracking, notifications
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinLengthValidator
import uuid
from .models import Case, Client, CaseDocument
from .models_billing import AdvancedInvoice, Payment

User = get_user_model()

class ClientPortalAccess(models.Model):
    """
    Aksesi i klientëve në portal
    """
    client = models.OneToOneField(Client, on_delete=models.CASCADE, related_name='portal_access')
    is_enabled = models.BooleanField(default=True, verbose_name="Portal i Aktivizuar")
    
    # Kontrollet e aksesit
    can_view_documents = models.BooleanField(default=True, verbose_name="Mund të shikojë dokumente")
    can_download_documents = models.BooleanField(default=True, verbose_name="Mund të shkarkojë dokumente")
    can_view_invoices = models.BooleanField(default=True, verbose_name="Mund të shikojë faturat")
    can_view_payments = models.BooleanField(default=True, verbose_name="Mund të shikojë pagesat")
    can_upload_documents = models.BooleanField(default=False, verbose_name="Mund të ngarkojë dokumente")
    can_message_lawyer = models.BooleanField(default=True, verbose_name="Mund të dërgojë mesazhe")
    
    # Preferences
    email_notifications = models.BooleanField(default=True, verbose_name="Njoftimet via Email")
    sms_notifications = models.BooleanField(default=False, verbose_name="Njoftimet via SMS")
    
    last_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Aksesi në Portal të Klientit"
        verbose_name_plural = "Aksesets në Portal të Klientëve"
    
    def __str__(self):
        return f"Portal Access - {self.client.name}"

class ClientDocumentShare(models.Model):
    """
    Dokumentet e ndarë me klientët në mënyrë të sigurt
    """
    SHARE_TYPE_CHOICES = [
        ('view_only', 'Vetëm Shikimi'),
        ('download', 'Shkarkim i Lejuar'),
        ('comment', 'Me Komente'),
    ]
    
    document = models.ForeignKey(CaseDocument, on_delete=models.CASCADE, related_name='client_shares')
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    case = models.ForeignKey(Case, on_delete=models.CASCADE)
    
    share_type = models.CharField(max_length=20, choices=SHARE_TYPE_CHOICES, default='view_only')
    shared_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Ndarë nga")
    
    # Kontrollet e aksesit
    access_token = models.UUIDField(default=uuid.uuid4, unique=True)
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="Skadon më")
    max_downloads = models.PositiveIntegerField(null=True, blank=True, verbose_name="Shkarkime Maksimale")
    download_count = models.PositiveIntegerField(default=0)
    
    # Metadata
    is_active = models.BooleanField(default=True)
    shared_at = models.DateTimeField(auto_now_add=True)
    last_accessed = models.DateTimeField(null=True, blank=True)
    
    # Shënime dhe mesazhe
    share_message = models.TextField(blank=True, verbose_name="Mesazhi i Ndarjes")
    
    class Meta:
        verbose_name = "Ndarje Dokumenti me Klient"
        verbose_name_plural = "Ndarjet e Dokumenteve me Klientët"
        unique_together = ['document', 'client']
        ordering = ['-shared_at']
    
    def is_accessible(self):
        """Kontrollon nëse dokumenti është ende i aksesueshëm"""
        if not self.is_active:
            return False
        
        if self.expires_at and self.expires_at < timezone.now():
            return False
        
        if self.max_downloads and self.download_count >= self.max_downloads:
            return False
        
        return True
    
    def record_access(self):
        """Regjistron aksesimin e dokumentit"""
        self.last_accessed = timezone.now()
        if self.share_type == 'download':
            self.download_count += 1
        self.save()
    
    def __str__(self):
        return f"{self.document.filename} → {self.client.name}"

class ClientMessage(models.Model):
    """
    Mesazhet midis klientëve dhe avokatëve
    """
    MESSAGE_TYPE_CHOICES = [
        ('client_to_lawyer', 'Klient → Avokat'),
        ('lawyer_to_client', 'Avokat → Klient'),
        ('system', 'Sistemi'),
    ]
    
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='client_messages')
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    sender = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Dërguesi")
    
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES)
    subject = models.CharField(max_length=255, verbose_name="Subjekti")
    content = models.TextField(verbose_name="Përmbajtja")
    
    # Bashkëngjitjet
    attachments = models.ManyToManyField('ClientMessageAttachment', blank=True)
    
    # Status
    is_read = models.BooleanField(default=False)
    is_urgent = models.BooleanField(default=False, verbose_name="Urgjent")
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    sent_at = models.DateTimeField(auto_now_add=True)
    
    # Reply thread
    parent_message = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='replies'
    )
    
    class Meta:
        verbose_name = "Mesazhi i Klientit"
        verbose_name_plural = "Mesazhet e Klientëve"
        ordering = ['-sent_at']
    
    def mark_as_read(self, user=None):
        """Shënon mesazhin si të lexuar"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()
    
    def __str__(self):
        return f"{self.subject} - {self.sender.get_full_name()}"

class ClientMessageAttachment(models.Model):
    """
    Bashkëngjitjet e mesazheve
    """
    file = models.FileField(upload_to='client_messages/attachments/')
    filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    content_type = models.CharField(max_length=100)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.filename

class ClientNotification(models.Model):
    """
    Njoftimet për klientët
    """
    NOTIFICATION_TYPE_CHOICES = [
        ('case_update', 'Përditësim Rasti'),
        ('document_shared', 'Dokument i Ndarë'),
        ('invoice_issued', 'Faturë e Lëshuar'),
        ('payment_received', 'Pagesë e Marrë'),
        ('appointment_scheduled', 'Takim i Planifikuar'),
        ('deadline_reminder', 'Kujtues për Afatin'),
        ('message_received', 'Mesazh i Marrë'),
        ('system', 'Sistemi'),
    ]
    
    STATUS_CHOICES = [
        ('unread', 'E palexuar'),
        ('read', 'E lexuar'),
        ('archived', 'E arkivuar'),
    ]
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='notifications')
    case = models.ForeignKey(Case, on_delete=models.CASCADE, null=True, blank=True)
    
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPE_CHOICES)
    title = models.CharField(max_length=255, verbose_name="Titulli")
    message = models.TextField(verbose_name="Mesazhi")
    
    # Metadata dhe link
    metadata = models.JSONField(default=dict, blank=True)
    action_url = models.URLField(blank=True, verbose_name="URL e Veprimit")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unread')
    
    # Delivery
    sent_via_email = models.BooleanField(default=False)
    sent_via_sms = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Njoftimi i Klientit"
        verbose_name_plural = "Njoftimet e Klientëve"
        ordering = ['-created_at']
    
    def mark_as_read(self):
        """Shënon njoftimin si të lexuar"""
        if self.status == 'unread':
            self.status = 'read'
            self.read_at = timezone.now()
            self.save()
    
    def __str__(self):
        return f"{self.title} - {self.client.name}"

class ClientDashboardWidget(models.Model):
    """
    Widget-et e personalizuara për dashboard-in e klientit
    """
    WIDGET_TYPE_CHOICES = [
        ('case_status', 'Statusi i Rastit'),
        ('recent_documents', 'Dokumente të Fundit'),
        ('upcoming_events', 'Ngjarje të Ardhshme'),
        ('invoices_summary', 'Përmbledhje Faturash'),
        ('payments_summary', 'Përmbledhje Pagesash'),
        ('messages', 'Mesazhet'),
        ('notifications', 'Njoftimet'),
    ]
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='dashboard_widgets')
    widget_type = models.CharField(max_length=30, choices=WIDGET_TYPE_CHOICES)
    
    # Layout dhe pozicionimi
    position = models.PositiveIntegerField(default=0, verbose_name="Pozicioni")
    is_visible = models.BooleanField(default=True, verbose_name="I Dukshëm")
    
    # Konfigurimi i widget-it
    configuration = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Widget i Dashboard-it të Klientit"
        verbose_name_plural = "Widget-et e Dashboard-it të Klientëve"
        ordering = ['client', 'position']
        unique_together = ['client', 'widget_type']
    
    def __str__(self):
        return f"{self.client.name} - {self.get_widget_type_display()}"

class ClientPaymentTracking(models.Model):
    """
    Tracking i pagesave për klientët
    """
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='payment_tracking')
    invoice = models.ForeignKey(AdvancedInvoice, on_delete=models.CASCADE)
    
    # Statusi i gjurmimit
    tracking_enabled = models.BooleanField(default=True)
    auto_reminders = models.BooleanField(default=True, verbose_name="Kujtuesa Automatike")
    
    # Kujtuesa
    reminder_days_before_due = models.PositiveIntegerField(default=7)
    reminder_days_after_due = models.PositiveIntegerField(default=3)
    max_reminders = models.PositiveIntegerField(default=5)
    reminders_sent = models.PositiveIntegerField(default=0)
    
    last_reminder_sent = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Gjurmimi i Pagesave të Klientit"
        verbose_name_plural = "Gjurmimet e Pagesave të Klientëve"
        unique_together = ['client', 'invoice']
    
    def should_send_reminder(self):
        """Kontrollon nëse duhet dërguar kujtues"""
        if not self.tracking_enabled or not self.auto_reminders:
            return False
        
        if self.reminders_sent >= self.max_reminders:
            return False
        
        if self.invoice.status == 'paid':
            return False
        
        now = timezone.now().date()
        due_date = self.invoice.due_date
        
        # Kujtues para skadimit
        if now == due_date - timezone.timedelta(days=self.reminder_days_before_due):
            return True
        
        # Kujtues pas skadimit
        if now == due_date + timezone.timedelta(days=self.reminder_days_after_due):
            return True
        
        return False

class ClientFeedback(models.Model):
    """
    Feedback-u i klientëve për shërbimet
    """
    RATING_CHOICES = [
        (1, '1 - Shumë i dobët'),
        (2, '2 - I dobët'),
        (3, '3 - Mesatar'),
        (4, '4 - I mirë'),
        (5, '5 - Shumë i mirë'),
    ]
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='feedback')
    case = models.ForeignKey(Case, on_delete=models.CASCADE, null=True, blank=True)
    
    # Vlerësimet
    overall_rating = models.PositiveIntegerField(choices=RATING_CHOICES, verbose_name="Vlerësimi i Përgjithshëm")
    communication_rating = models.PositiveIntegerField(choices=RATING_CHOICES, verbose_name="Komunikimi")
    service_quality_rating = models.PositiveIntegerField(choices=RATING_CHOICES, verbose_name="Cilësia e Shërbimit")
    timeliness_rating = models.PositiveIntegerField(choices=RATING_CHOICES, verbose_name="Përpikëria")
    
    # Komentet
    positive_feedback = models.TextField(blank=True, verbose_name="Aspektet Pozitive")
    improvement_suggestions = models.TextField(blank=True, verbose_name="Sugjerime për Përmirësim")
    additional_comments = models.TextField(blank=True, verbose_name="Komente Shtesë")
    
    # Metadata
    would_recommend = models.BooleanField(null=True, verbose_name="Do ta rekomandonte")
    is_anonymous = models.BooleanField(default=False, verbose_name="Anonim")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Feedback-u i Klientit"
        verbose_name_plural = "Feedback-et e Klientëve"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Feedback - {self.client.name} ({self.overall_rating}/5)"