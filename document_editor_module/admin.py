"""
Django Admin Configuration për Document Editor Module
Konfiguracion i avancuar për menaxhimin e dokumenteve nga admin panel
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Q
from django.contrib.admin import SimpleListFilter
from django.utils import timezone
from datetime import timedelta

from .models.document_models import (
    Document, DocumentTemplate, DocumentType, DocumentStatus,
    DocumentComment, DocumentVersion, DocumentSignature, DocumentAuditLog,
    DocumentEditor, LLMInteraction
)
from .advanced_features.workflow_system import (
    WorkflowTemplate, DocumentWorkflow, WorkflowStep, WorkflowAction
)
from .advanced_features.signature_system import SignatureRequest

# Custom filters

class DocumentStatusFilter(SimpleListFilter):
    title = 'Document Status'
    parameter_name = 'status_filter'

    def lookups(self, request, model_admin):
        statuses = DocumentStatus.objects.all()
        return [(status.id, status.name) for status in statuses]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status_id=self.value())
        return queryset

class DocumentOwnerFilter(SimpleListFilter):
    title = 'Document Owner'
    parameter_name = 'owner'

    def lookups(self, request, model_admin):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        owners = User.objects.filter(owned_documents__isnull=False).distinct()
        return [(owner.id, owner.username) for owner in owners]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(owned_by_id=self.value())
        return queryset

class RecentDocumentsFilter(SimpleListFilter):
    title = 'Recent Activity'
    parameter_name = 'recent'

    def lookups(self, request, model_admin):
        return [
            ('today', 'Today'),
            ('week', 'This Week'),
            ('month', 'This Month'),
        ]

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == 'today':
            return queryset.filter(updated_at__date=now.date())
        elif self.value() == 'week':
            week_ago = now - timedelta(days=7)
            return queryset.filter(updated_at__gte=week_ago)
        elif self.value() == 'month':
            month_ago = now - timedelta(days=30)
            return queryset.filter(updated_at__gte=month_ago)
        return queryset

# Inline admins

class DocumentEditorInline(admin.TabularInline):
    model = DocumentEditor
    extra = 0
    fields = ('user', 'permission_level', 'added_at')
    readonly_fields = ('added_at',)

class DocumentCommentInline(admin.TabularInline):
    model = DocumentComment
    extra = 0
    fields = ('author', 'content_preview', 'position_start', 'position_end', 'is_resolved', 'created_at')
    readonly_fields = ('content_preview', 'created_at')
    
    def content_preview(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content
    content_preview.short_description = "Content Preview"

class DocumentVersionInline(admin.TabularInline):
    model = DocumentVersion
    extra = 0
    fields = ('version_number', 'created_by', 'created_at', 'change_summary')
    readonly_fields = ('created_at',)
    ordering = ('-version_number',)

class LLMInteractionInline(admin.TabularInline):
    model = LLMInteraction
    extra = 0
    fields = ('interaction_type', 'user', 'confidence_score', 'processing_time', 'created_at')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)

# Main admin classes

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'document_type', 'status_colored', 'owned_by', 'case_link',
        'version_number', 'is_locked_display', 'updated_at'
    )
    list_filter = (
        DocumentStatusFilter, 'document_type', DocumentOwnerFilter, 
        RecentDocumentsFilter, 'is_locked', 'created_at'
    )
    search_fields = ('title', 'content', 'case__title', 'owned_by__username')
    readonly_fields = (
        'id', 'version_number', 'created_at', 'updated_at', 'last_edited_at',
        'word_count', 'character_count', 'edit_count'
    )
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'case', 'document_type', 'status')
        }),
        ('Content', {
            'fields': ('content', 'content_html'),
            'classes': ('collapse',)
        }),
        ('Ownership & Access', {
            'fields': ('owned_by', 'created_by', 'assigned_to')
        }),
        ('Template & Workflow', {
            'fields': ('template_used',),
            'classes': ('collapse',)
        }),
        ('Lock Status', {
            'fields': ('is_locked', 'locked_by', 'locked_at'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('version_number', 'created_at', 'updated_at', 'last_edited_at'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('word_count', 'character_count', 'edit_count'),
            'classes': ('collapse',)
        })
    )
    
    inlines = [DocumentEditorInline, DocumentCommentInline, DocumentVersionInline, LLMInteractionInline]
    
    actions = ['lock_documents', 'unlock_documents', 'archive_documents', 'export_documents']
    
    def status_colored(self, obj):
        color = getattr(obj.status, 'color', '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.status.name
        )
    status_colored.short_description = 'Status'
    status_colored.admin_order_field = 'status__name'
    
    def case_link(self, obj):
        if obj.case:
            url = reverse('admin:cases_case_change', args=[obj.case.pk])
            return format_html('<a href="{}">{}</a>', url, obj.case.title)
        return '-'
    case_link.short_description = 'Case'
    case_link.admin_order_field = 'case__title'
    
    def is_locked_display(self, obj):
        if obj.is_locked:
            return format_html(
                '<span style="color: red;">🔒 {}</span>',
                obj.locked_by.username if obj.locked_by else 'Unknown'
            )
        return format_html('<span style="color: green;">🔓 Unlocked</span>')
    is_locked_display.short_description = 'Lock Status'
    is_locked_display.admin_order_field = 'is_locked'
    
    def word_count(self, obj):
        return len(obj.content.split()) if obj.content else 0
    word_count.short_description = 'Words'
    
    def character_count(self, obj):
        return len(obj.content) if obj.content else 0
    character_count.short_description = 'Characters'
    
    def edit_count(self, obj):
        return obj.version_history.count()
    edit_count.short_description = 'Edits'
    
    def lock_documents(self, request, queryset):
        count = 0
        for document in queryset:
            if document.lock_document(request.user):
                count += 1
        self.message_user(request, f'{count} documents locked successfully.')
    lock_documents.short_description = "Lock selected documents"
    
    def unlock_documents(self, request, queryset):
        count = 0
        for document in queryset:
            if document.unlock_document(request.user):
                count += 1
        self.message_user(request, f'{count} documents unlocked successfully.')
    unlock_documents.short_description = "Unlock selected documents"
    
    def archive_documents(self, request, queryset):
        try:
            archived_status = DocumentStatus.objects.get(name='Archived')
            updated = queryset.update(status=archived_status)
            self.message_user(request, f'{updated} documents archived successfully.')
        except DocumentStatus.DoesNotExist:
            self.message_user(request, 'Archived status not found.', level='error')
    archive_documents.short_description = "Archive selected documents"

@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'is_active', 'usage_count', 'created_by', 'updated_at')
    list_filter = ('category', 'is_active', 'created_at')
    search_fields = ('name', 'description', 'category', 'content')
    readonly_fields = ('id', 'created_at', 'updated_at', 'usage_count')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'category', 'is_active')
        }),
        ('Content', {
            'fields': ('content',),
            'classes': ('monospace',)
        }),
        ('Variables', {
            'fields': ('variables',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at', 'usage_count'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['activate_templates', 'deactivate_templates', 'clone_templates']
    
    def usage_count(self, obj):
        return Document.objects.filter(template_used=obj).count()
    usage_count.short_description = 'Usage Count'
    
    def activate_templates(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} templates activated.')
    activate_templates.short_description = "Activate selected templates"
    
    def deactivate_templates(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} templates deactivated.')
    deactivate_templates.short_description = "Deactivate selected templates"

@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'requires_signature', 'is_legal_document', 'document_count')
    list_filter = ('requires_signature', 'is_legal_document')
    search_fields = ('name', 'description')
    
    def document_count(self, obj):
        return obj.documents.count()
    document_count.short_description = 'Documents'

@admin.register(DocumentStatus)
class DocumentStatusAdmin(admin.ModelAdmin):
    list_display = ('name', 'color_display', 'order', 'is_final', 'document_count')
    list_filter = ('is_final',)
    search_fields = ('name', 'description')
    ordering = ('order',)
    
    def color_display(self, obj):
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 3px;">{}</span>',
            obj.color,
            obj.name
        )
    color_display.short_description = 'Color Preview'
    
    def document_count(self, obj):
        return obj.documents.count()
    document_count.short_description = 'Documents'

@admin.register(DocumentComment)
class DocumentCommentAdmin(admin.ModelAdmin):
    list_display = ('document_link', 'author', 'content_preview', 'position_range', 'is_resolved', 'created_at')
    list_filter = ('is_resolved', 'created_at')
    search_fields = ('content', 'document__title', 'author__username')
    readonly_fields = ('created_at', 'resolved_at')
    
    def document_link(self, obj):
        url = reverse('admin:document_editor_document_change', args=[obj.document.pk])
        return format_html('<a href="{}">{}</a>', url, obj.document.title)
    document_link.short_description = 'Document'
    
    def content_preview(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'
    
    def position_range(self, obj):
        if obj.position_start is not None and obj.position_end is not None:
            return f"{obj.position_start}-{obj.position_end}"
        return '-'
    position_range.short_description = 'Position'

@admin.register(DocumentSignature)
class DocumentSignatureAdmin(admin.ModelAdmin):
    list_display = ('document_link', 'signer', 'signed_at', 'ip_address', 'is_valid_display')
    list_filter = ('signed_at', 'is_valid')
    search_fields = ('document__title', 'signer__username', 'signature_id')
    readonly_fields = ('signed_at', 'signature_id', 'certificate_info')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('document', 'signer', 'signature_data', 'signed_at')
        }),
        ('Technical Details', {
            'fields': ('signature_id', 'ip_address', 'user_agent', 'is_valid'),
            'classes': ('collapse',)
        }),
        ('Certificate Information', {
            'fields': ('certificate_info',),
            'classes': ('collapse',)
        })
    )
    
    def document_link(self, obj):
        url = reverse('admin:document_editor_document_change', args=[obj.document.pk])
        return format_html('<a href="{}">{}</a>', url, obj.document.title)
    document_link.short_description = 'Document'
    
    def is_valid_display(self, obj):
        if obj.is_valid:
            return format_html('<span style="color: green;">✓ Valid</span>')
        return format_html('<span style="color: red;">✗ Invalid</span>')
    is_valid_display.short_description = 'Validity'

@admin.register(DocumentAuditLog)
class DocumentAuditLogAdmin(admin.ModelAdmin):
    list_display = ('document_link', 'user', 'action', 'created_at', 'ip_address')
    list_filter = ('action', 'created_at')
    search_fields = ('document__title', 'user__username', 'action', 'details')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('document', 'user', 'action', 'details')
        }),
        ('Technical Details', {
            'fields': ('ip_address', 'user_agent', 'metadata'),
            'classes': ('collapse',)
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        })
    )
    
    def document_link(self, obj):
        if obj.document:
            url = reverse('admin:document_editor_document_change', args=[obj.document.pk])
            return format_html('<a href="{}">{}</a>', url, obj.document.title)
        return '-'
    document_link.short_description = 'Document'

@admin.register(LLMInteraction)
class LLMInteractionAdmin(admin.ModelAdmin):
    list_display = ('document_link', 'user', 'interaction_type', 'confidence_score', 'processing_time', 'llm_provider', 'created_at')
    list_filter = ('interaction_type', 'llm_provider', 'created_at')
    search_fields = ('document__title', 'user__username', 'prompt', 'llm_response')
    readonly_fields = ('created_at', 'processing_time')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('document', 'user', 'interaction_type')
        }),
        ('LLM Details', {
            'fields': ('llm_provider', 'llm_model', 'confidence_score', 'processing_time')
        }),
        ('Content', {
            'fields': ('prompt', 'llm_response'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata', 'created_at'),
            'classes': ('collapse',)
        })
    )
    
    def document_link(self, obj):
        url = reverse('admin:document_editor_document_change', args=[obj.document.pk])
        return format_html('<a href="{}">{}</a>', url, obj.document.title)
    document_link.short_description = 'Document'

# Workflow Admin

@admin.register(WorkflowTemplate)
class WorkflowTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'document_types_list', 'is_active', 'usage_count', 'created_by', 'updated_at')
    list_filter = ('is_active', 'document_types', 'created_at')
    search_fields = ('name', 'description')
    filter_horizontal = ('document_types',)
    readonly_fields = ('created_at', 'updated_at', 'usage_count')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Configuration', {
            'fields': ('document_types', 'steps_config')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at', 'usage_count'),
            'classes': ('collapse',)
        })
    )
    
    def document_types_list(self, obj):
        return ", ".join([dt.name for dt in obj.document_types.all()])
    document_types_list.short_description = 'Document Types'
    
    def usage_count(self, obj):
        return DocumentWorkflow.objects.filter(template=obj).count()
    usage_count.short_description = 'Usage Count'

@admin.register(DocumentWorkflow)
class DocumentWorkflowAdmin(admin.ModelAdmin):
    list_display = ('document_link', 'template', 'status', 'current_step', 'progress_display', 'started_at')
    list_filter = ('status', 'template', 'started_at')
    search_fields = ('document__title', 'template__name')
    readonly_fields = ('started_at', 'completed_at', 'progress_percentage')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('document', 'template', 'status')
        }),
        ('Progress', {
            'fields': ('current_step', 'total_steps', 'completed_steps', 'progress_percentage')
        }),
        ('Timestamps', {
            'fields': ('started_at', 'completed_at')
        })
    )
    
    def document_link(self, obj):
        url = reverse('admin:document_editor_document_change', args=[obj.document.pk])
        return format_html('<a href="{}">{}</a>', url, obj.document.title)
    document_link.short_description = 'Document'
    
    def progress_display(self, obj):
        percentage = obj.progress_percentage
        color = 'green' if percentage == 100 else 'orange' if percentage > 50 else 'red'
        return format_html(
            '<div style="width: 100px; background-color: #f0f0f0; border-radius: 3px;">'
            '<div style="width: {}%; background-color: {}; height: 20px; border-radius: 3px; text-align: center; color: white;">'
            '{}%</div></div>',
            percentage, color, percentage
        )
    progress_display.short_description = 'Progress'

@admin.register(SignatureRequest)
class SignatureRequestAdmin(admin.ModelAdmin):
    list_display = ('document_link', 'status', 'signers_count', 'signed_count', 'progress_display', 'created_at')
    list_filter = ('status', 'provider', 'created_at')
    search_fields = ('document__title', 'title', 'external_id')
    readonly_fields = ('created_at', 'completed_at', 'external_id', 'progress_percentage')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('document', 'title', 'message', 'status')
        }),
        ('Configuration', {
            'fields': ('provider', 'expires_at', 'external_id')
        }),
        ('Signers', {
            'fields': ('signers_data',),
            'classes': ('collapse',)
        }),
        ('Progress', {
            'fields': ('signers_count', 'signed_count', 'progress_percentage')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'completed_at')
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        })
    )
    
    def document_link(self, obj):
        url = reverse('admin:document_editor_document_change', args=[obj.document.pk])
        return format_html('<a href="{}">{}</a>', url, obj.document.title)
    document_link.short_description = 'Document'
    
    def progress_display(self, obj):
        percentage = obj.progress_percentage
        color = 'green' if percentage == 100 else 'orange' if percentage > 50 else 'red'
        return format_html(
            '<div style="width: 100px; background-color: #f0f0f0; border-radius: 3px;">'
            '<div style="width: {}%; background-color: {}; height: 20px; border-radius: 3px; text-align: center; color: white;">'
            '{}%</div></div>',
            percentage, color, percentage
        )
    progress_display.short_description = 'Progress'

# Custom admin site configuration

class DocumentEditorAdminSite(admin.AdminSite):
    site_header = "Document Editor Administration"
    site_title = "Document Editor Admin"
    index_title = "Document Editor Dashboard"
    
    def index(self, request, extra_context=None):
        """Custom admin index with statistics"""
        extra_context = extra_context or {}
        
        # Document statistics
        total_documents = Document.objects.count()
        documents_today = Document.objects.filter(created_at__date=timezone.now().date()).count()
        locked_documents = Document.objects.filter(is_locked=True).count()
        
        # Template statistics  
        total_templates = DocumentTemplate.objects.count()
        active_templates = DocumentTemplate.objects.filter(is_active=True).count()
        
        # Workflow statistics
        active_workflows = DocumentWorkflow.objects.exclude(status='completed').count()
        completed_workflows = DocumentWorkflow.objects.filter(status='completed').count()
        
        # Signature statistics
        pending_signatures = SignatureRequest.objects.filter(
            status__in=['sent', 'delivered']
        ).count()
        completed_signatures = SignatureRequest.objects.filter(status='completed').count()
        
        extra_context.update({
            'document_stats': {
                'total': total_documents,
                'today': documents_today,
                'locked': locked_documents,
            },
            'template_stats': {
                'total': total_templates,
                'active': active_templates,
            },
            'workflow_stats': {
                'active': active_workflows,
                'completed': completed_workflows,
            },
            'signature_stats': {
                'pending': pending_signatures,
                'completed': completed_signatures,
            }
        })
        
        return super().index(request, extra_context)

# Register with custom admin site if needed
# document_editor_admin_site = DocumentEditorAdminSite(name='document_editor_admin')
