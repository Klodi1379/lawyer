from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    User, UserProfile, Client, Case, CaseDocument, 
    CaseEvent, EventType, TimeEntry, Invoice, AuditLog, UserAuditLog
)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'is_staff', 'is_2fa_enabled', 'date_joined')
    list_filter = ('role', 'is_2fa_enabled', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    
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

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'created_at')
    search_fields = ('user__username', 'user__email', 'phone')
    list_filter = ('created_at',)

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'phone', 'organization', 'created_at')
    search_fields = ('full_name', 'email', 'organization')
    list_filter = ('created_at',)
    ordering = ('-created_at',)

@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ('uid', 'title', 'client', 'assigned_to', 'case_type', 'status', 'created_at')
    list_filter = ('case_type', 'status', 'created_at', 'assigned_to')
    search_fields = ('uid', 'title', 'client__full_name', 'description')
    readonly_fields = ('uid', 'created_at', 'updated_at')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('uid', 'title', 'description', 'client')
        }),
        ('Assignment & Status', {
            'fields': ('assigned_to', 'case_type', 'status')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(CaseDocument)
class CaseDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'case', 'uploaded_by', 'doc_type', 'version', 'created_at')
    list_filter = ('doc_type', 'created_at', 'uploaded_by')
    search_fields = ('title', 'case__title', 'case__uid')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)

@admin.register(EventType)
class EventTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'color', 'is_deadline')
    list_filter = ('is_deadline',)
    search_fields = ('name',)

@admin.register(CaseEvent)
class CaseEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'case', 'event_type', 'priority', 'starts_at', 'is_deadline', 'created_by')
    list_filter = ('event_type', 'priority', 'is_deadline', 'is_all_day', 'starts_at', 'created_by')
    search_fields = ('title', 'case__title', 'case__uid', 'description')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-starts_at',)
    filter_horizontal = ('attendees',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'case', 'event_type', 'priority')
        }),
        ('Date & Time', {
            'fields': ('starts_at', 'ends_at', 'is_all_day', 'location')
        }),
        ('Participants & Reminders', {
            'fields': ('attendees', 'reminder_minutes', 'reminder_sent')
        }),
        ('Options', {
            'fields': ('is_deadline', 'is_recurring')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ('case', 'user', 'minutes', 'created_at')
    list_filter = ('user', 'created_at')
    search_fields = ('case__title', 'case__uid', 'description')
    ordering = ('-created_at',)

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('case', 'issued_to', 'total_amount', 'paid', 'issued_at')
    list_filter = ('paid', 'issued_at')
    search_fields = ('case__title', 'case__uid', 'issued_to__full_name')
    ordering = ('-issued_at',)

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'target_type', 'target_id', 'created_at')
    list_filter = ('action', 'target_type', 'created_at')
    search_fields = ('user__username', 'action', 'target_id')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)

@admin.register(UserAuditLog)
class UserAuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'ip_address', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('user__username', 'action', 'ip_address')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
