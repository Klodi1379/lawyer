# admin_improved.py - Django Admin Configuration për sistemin e përmirësuar
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count
from django.utils.safestring import mark_safe
from .models_improved import (
    User, Client, Case, Document, DocumentCategory, DocumentType,
    DocumentStatus, DocumentCaseRelation, DocumentAccess, DocumentAuditLog,
    AuditLog
)

# ==========================================
# CUSTOM ADMIN CLASSES
# ==========================================

class CustomUserAdmin(UserAdmin):
    """Custom admin për User model"""
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'is_2fa_enabled', 'last_login')
    list_filter = ('role', 'is_active', 'is_2fa_enabled', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)
    
    fieldsets = UserAdmin.fieldsets + (
        ('Legal System Info', {
            'fields': ('role', 'is_2fa_enabled', 'last_login_ip')
        }),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Legal System Info', {
            'fields': ('role', 'email', 'first_name', 'last_name')
        }),
    )
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(
            cases_count=Count('assigned_cases'),
            documents_count=Count('created_documents')
        )

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'phone', 'organization', 'cases_count', 'created_at')
    list_filter = ('created_at', 'organization')
    search_fields = ('full_name', 'email', 'phone', 'organization')
    readonly_fields = ('created_at',)
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(cases_count=Count('cases'))
    
    def cases_count(self, obj):
        return obj.cases_count
    cases_count.short_description = 'Cases'
    cases_count.admin_order_field = 'cases_count'

class DocumentCaseRelationInline(admin.TabularInline):
    """Inline për lidhjet dokument-case"""
    model = DocumentCaseRelation
    extra = 0
    readonly_fields = ('added_by', 'added_at')
    autocomplete_fields = ('document',)

@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ('uid', 'title', 'client_link', 'assigned_to', 'case_type', 'status', 'documents_count', 'created_at')
    list_filter = ('case_type', 'status', 'created_at', 'assigned_to')
    search_fields = ('uid', 'title', 'description', 'client__full_name')
    readonly_fields = ('uid', 'created_at', 'updated_at')
    autocomplete_fields = ('client', 'assigned_to')
    inlines = [DocumentCaseRelationInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('uid', 'title', 'description')
        }),
        ('Assignment', {
            'fields': ('client', 'assigned_to')
        }),
        ('Classification', {
            'fields': ('case_type', 'status')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('client', 'assigned_to').annotate(
            documents_count=Count('documentcaserelation')
        )
    
    def client_link(self, obj):
        url = reverse('admin:legal_manager_client_change', args=[obj.client.pk])
        return format_html('<a href="{}">{}</a>', url, obj.client.full_name)
    client_link.short_description = 'Client'
    client_link.admin_order_field = 'client__full_name'
    
    def documents_count(self, obj):
        return obj.documents_count
    documents_count.short_description = 'Documents'
    documents_count.admin_order_field = 'documents_count'

@admin.register(DocumentCategory)
class DocumentCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'color_preview', 'types_count', 'description')
    search_fields = ('name', 'description')
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(types_count=Count('types'))
    
    def color_preview(self, obj):
        return format_html(
            '<div style="width: 20px; height: 20px; background-color: {}; border: 1px solid #ccc; display: inline-block;"></div>',
            obj.color
        )
    color_preview.short_description = 'Color'
    
    def types_count(self, obj):
        return obj.types_count
    types_count.short_description = 'Types'
    types_count.admin_order_field = 'types_count'

@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'is_template', 'documents_count')
    list_filter = ('category', 'is_template')
    search_fields = ('name',)
    autocomplete_fields = ('category',)
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('category').annotate(
            documents_count=Count('document')
        )
    
    def documents_count(self, obj):
        return obj.documents_count
    documents_count.short_description = 'Documents'
    documents_count.admin_order_field = 'documents_count'

@admin.register(DocumentStatus)
class DocumentStatusAdmin(admin.ModelAdmin):
    list_display = ('name', 'color_preview', 'is_final', 'documents_count')
    list_filter = ('is_final',)
    search_fields = ('name',)
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(documents_count=Count('document'))
    
    def color_preview(self, obj):
        return format_html(
            '<div style="width: 20px; height: 20px; background-color: {}; border: 1px solid #ccc; display: inline-block;"></div>',
            obj.color
        )
    color_preview.short_description = 'Color'
    
    def documents_count(self, obj):
        return obj.documents_count
    documents_count.short_description = 'Documents'
    documents_count.admin_order_field = 'documents_count'

class DocumentAccessInline(admin.TabularInline):
    """Inline për access controls"""
    model = DocumentAccess
    extra = 0
    readonly_fields = ('granted_by', 'granted_at')

class DocumentAuditLogInline(admin.TabularInline):
    """Inline për audit logs"""
    model = DocumentAuditLog
    extra = 0
    readonly_fields = ('user', 'action', 'ip_address', 'created_at')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'document_type', 'status_colored', 'is_template', 
        'access_level', 'created_by', 'file_size_formatted', 'created_at'
    )
    list_filter = (
        'document_type__category', 'document_type', 'status', 'is_template', 
        'access_level', 'is_confidential', 'created_at'
    )
    search_fields = ('title', 'description', 'tags', 'uid')
    readonly_fields = ('uid', 'file_size', 'file_type', 'created_at', 'updated_at', 'last_accessed')
    autocomplete_fields = ('document_type', 'status', 'created_by', 'uploaded_by', 'parent_document')
    inlines = [DocumentAccessInline, DocumentAuditLogInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('uid', 'title', 'description', 'tags')
        }),
        ('File Information', {
            'fields': ('file', 'file_size', 'file_type')
        }),
        ('Classification', {
            'fields': ('document_type', 'status', 'is_template', 'parent_document')
        }),
        ('Access Control', {
            'fields': ('is_confidential', 'access_level')
        }),
        ('Template Data', {
            'fields': ('template_variables',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Ownership', {
            'fields': ('created_by', 'uploaded_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_accessed'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related(
            'document_type__category', 'status', 'created_by', 'uploaded_by'
        )
    
    def status_colored(self, obj):
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            obj.status.color,
            obj.status.name
        )
    status_colored.short_description = 'Status'
    status_colored.admin_order_field = 'status__name'
    
    def file_size_formatted(self, obj):
        if not obj.file_size:
            return "Unknown"
        
        size = obj.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    file_size_formatted.short_description = 'File Size'
    file_size_formatted.admin_order_field = 'file_size'

@admin.register(DocumentCaseRelation)
class DocumentCaseRelationAdmin(admin.ModelAdmin):
    list_display = ('document_title', 'case_title', 'relationship_type', 'added_by', 'added_at')
    list_filter = ('relationship_type', 'added_at')
    search_fields = ('document__title', 'case__title', 'case__uid')
    autocomplete_fields = ('document', 'case', 'added_by')
    readonly_fields = ('added_at',)
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('document', 'case', 'added_by')
    
    def document_title(self, obj):
        return obj.document.title
    document_title.short_description = 'Document'
    document_title.admin_order_field = 'document__title'
    
    def case_title(self, obj):
        return f"{obj.case.uid} - {obj.case.title}"
    case_title.short_description = 'Case'
    case_title.admin_order_field = 'case__title'

@admin.register(DocumentAccess)
class DocumentAccessAdmin(admin.ModelAdmin):
    list_display = ('document_title', 'user_or_role', 'permissions_summary', 'granted_by', 'granted_at', 'expires_at')
    list_filter = ('can_view', 'can_download', 'can_edit', 'can_delete', 'granted_at')
    search_fields = ('document__title', 'user__username', 'role')
    autocomplete_fields = ('document', 'user', 'granted_by')
    readonly_fields = ('granted_at',)
    
    fieldsets = (
        ('Target', {
            'fields': ('document', 'user', 'role')
        }),
        ('Permissions', {
            'fields': ('can_view', 'can_download', 'can_edit', 'can_delete', 'can_share')
        }),
        ('Metadata', {
            'fields': ('granted_by', 'granted_at', 'expires_at')
        }),
    )
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('document', 'user', 'granted_by')
    
    def document_title(self, obj):
        return obj.document.title
    document_title.short_description = 'Document'
    document_title.admin_order_field = 'document__title'
    
    def user_or_role(self, obj):
        if obj.user:
            return f"User: {obj.user.username}"
        return f"Role: {obj.role}"
    user_or_role.short_description = 'Target'
    
    def permissions_summary(self, obj):
        perms = []
        if obj.can_view: perms.append("View")
        if obj.can_download: perms.append("Download")
        if obj.can_edit: perms.append("Edit")
        if obj.can_delete: perms.append("Delete")
        if obj.can_share: perms.append("Share")
        return ", ".join(perms) if perms else "None"
    permissions_summary.short_description = 'Permissions'

@admin.register(DocumentAuditLog)
class DocumentAuditLogAdmin(admin.ModelAdmin):
    list_display = ('document_title', 'user', 'action', 'ip_address', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('document__title', 'user__username', 'action', 'ip_address')
    readonly_fields = ('document', 'user', 'action', 'ip_address', 'user_agent', 'metadata', 'created_at')
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('document', 'user')
    
    def document_title(self, obj):
        return obj.document.title
    document_title.short_description = 'Document'
    document_title.admin_order_field = 'document__title'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Vetëm superuser mund të fshijë audit logs

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'target_type', 'target_id', 'created_at')
    list_filter = ('action', 'target_type', 'created_at')
    search_fields = ('user__username', 'action', 'target_type', 'target_id')
    readonly_fields = ('user', 'action', 'target_type', 'target_id', 'metadata', 'created_at')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

# ==========================================
# ADMIN SITE CUSTOMIZATION
# ==========================================

# Customize admin site header and title
admin.site.site_header = "Legal Case Manager Administration"
admin.site.site_title = "Legal Manager Admin"
admin.site.index_title = "Welcome to Legal Case Manager Administration"

# Register the custom User admin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

# ==========================================
# ADMIN ACTIONS
# ==========================================

def make_confidential(modeladmin, request, queryset):
    """Bulk action për të bërë dokumentet confidential"""
    updated = queryset.update(is_confidential=True, access_level='confidential')
    modeladmin.message_user(
        request,
        f"{updated} document(s) marked as confidential."
    )
make_confidential.short_description = "Mark selected documents as confidential"

def make_internal(modeladmin, request, queryset):
    """Bulk action për të bërë dokumentet internal"""
    updated = queryset.update(access_level='internal')
    modeladmin.message_user(
        request,
        f"{updated} document(s) marked as internal."
    )
make_internal.short_description = "Mark selected documents as internal"

def archive_cases(modeladmin, request, queryset):
    """Bulk action për të arkivuar rastet"""
    updated = queryset.update(status='closed')
    modeladmin.message_user(
        request,
        f"{updated} case(s) archived."
    )
archive_cases.short_description = "Archive selected cases"

# Add actions to admin classes
DocumentAdmin.actions = [make_confidential, make_internal]
CaseAdmin.actions = [archive_cases]
