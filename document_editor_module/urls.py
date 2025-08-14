"""
URLs për Document Editor Module
Routing për të gjitha views: documents, templates, workflows, signatures
"""

from django.urls import path, include
from django.views.generic import TemplateView

from .views import (
    document_views,
    template_views,
    workflow_views,
    signature_views
)

app_name = 'document_editor'

# Document URLs
document_urlpatterns = [
    # Document CRUD
    path('', document_views.DocumentListView.as_view(), name='document_list'),
    path('create/', document_views.DocumentCreateView.as_view(), name='document_create'),
    path('<int:pk>/', document_views.DocumentDetailView.as_view(), name='document_detail'),
    path('<int:pk>/edit/', document_views.DocumentUpdateView.as_view(), name='document_update'),
    path('<int:pk>/delete/', document_views.DocumentDeleteView.as_view(), name='document_delete'),
    
    # Document Actions
    path('<int:document_id>/lock-toggle/', document_views.document_lock_toggle, name='document_lock_toggle'),
    path('<int:document_id>/comments/add/', document_views.document_comment_add, name='document_comment_add'),
    path('comments/<int:comment_id>/resolve/', document_views.document_comment_resolve, name='document_comment_resolve'),
    
    # Version Control
    path('<int:document_id>/versions/<int:version_number>/restore/', 
         document_views.document_version_restore, name='document_version_restore'),
    
    # AI Features
    path('<int:document_id>/ai/suggestions/', document_views.document_ai_suggestions, name='document_ai_suggestions'),
    path('<int:document_id>/ai/generate/', document_views.document_ai_generate_content, name='document_ai_generate'),
    
    # Export
    path('<int:document_id>/export/', document_views.document_export, name='document_export'),
    
    # Upload
    path('upload/', TemplateView.as_view(template_name='document_editor/documents/upload.html'), name='document_upload'),
]

# Template URLs
template_urlpatterns = [
    # Template CRUD
    path('', template_views.TemplateListView.as_view(), name='template_list'),
    path('create/', template_views.TemplateCreateView.as_view(), name='template_create'),
    path('<int:pk>/', template_views.TemplateDetailView.as_view(), name='template_detail'),
    path('<int:pk>/edit/', template_views.TemplateUpdateView.as_view(), name='template_update'),
    path('<int:pk>/delete/', template_views.TemplateDeleteView.as_view(), name='template_delete'),
    
    # Template Actions
    path('<int:template_id>/preview/', template_views.template_preview, name='template_preview'),
    path('<int:template_id>/ai-enhance/', template_views.template_ai_enhance, name='template_ai_enhance'),
    path('<int:template_id>/clone/', template_views.template_clone, name='template_clone'),
    path('<int:template_id>/export/', template_views.template_export, name='template_export'),
    path('<int:template_id>/variables/analyze/', template_views.template_variables_analyze, name='template_variables_analyze'),
    
    # Template Creation from Document
    path('create-from-document/<int:document_id>/', 
         template_views.template_create_from_document, name='template_create_from_document'),
    
    # AI Features
    path('ai-suggestions/', template_views.template_ai_suggestions, name='template_ai_suggestions'),
    
    # Import/Export
    path('import/', template_views.TemplateImportView.as_view(), name='template_import'),
    path('library/', template_views.TemplateLibraryView.as_view(), name='template_library'),
]

# Workflow URLs
workflow_urlpatterns = [
    # Dashboard
    path('dashboard/', workflow_views.WorkflowDashboardView.as_view(), name='workflow_dashboard'),
    
    # Workflow CRUD
    path('', workflow_views.WorkflowListView.as_view(), name='workflow_list'),
    path('<int:pk>/', workflow_views.WorkflowDetailView.as_view(), name='workflow_detail'),
    path('create/<int:document_id>/', workflow_views.workflow_create, name='workflow_create'),
    path('<int:workflow_id>/cancel/', workflow_views.workflow_cancel, name='workflow_cancel'),
    path('<int:workflow_id>/export/', workflow_views.workflow_export, name='workflow_export'),
    
    # Workflow Actions
    path('steps/<int:step_id>/action/', workflow_views.workflow_action_execute, name='workflow_action_execute'),
    path('steps/<int:step_id>/details/', workflow_views.workflow_step_details, name='workflow_step_details'),
    path('steps/<int:step_id>/assign/', workflow_views.workflow_step_assign, name='workflow_step_assign'),
    
    # Analytics
    path('analytics/', workflow_views.workflow_analytics, name='workflow_analytics'),
    
    # Templates
    path('templates/', workflow_views.WorkflowTemplateListView.as_view(), name='workflow_template_list'),
    path('templates/create/', workflow_views.WorkflowTemplateCreateView.as_view(), name='workflow_template_create'),
    path('templates/<int:pk>/', workflow_views.WorkflowTemplateDetailView.as_view(), name='workflow_template_detail'),
]

# Signature URLs
signature_urlpatterns = [
    # Signature Requests
    path('requests/', signature_views.SignatureRequestListView.as_view(), name='signature_request_list'),
    path('requests/create/', signature_views.SignatureRequestCreateView.as_view(), name='signature_request_create'),
    path('requests/<int:pk>/', signature_views.SignatureRequestDetailView.as_view(), name='signature_request_detail'),
    path('requests/<int:request_id>/cancel/', signature_views.signature_request_cancel, name='signature_request_cancel'),
    
    # Signing
    path('sign/<int:request_id>/', signature_views.SignatureSignView.as_view(), name='signature_sign'),
    
    # Signatures
    path('signatures/', signature_views.SignatureListView.as_view(), name='signature_list'),
    path('signatures/<int:pk>/', signature_views.SignatureDetailView.as_view(), name='signature_detail'),
    path('signatures/<int:signature_id>/verify/', signature_views.signature_verify, name='signature_verify'),
    path('signatures/<int:signature_id>/certificate/', 
         signature_views.signature_certificate_download, name='signature_certificate_download'),
    
    # Webhooks and Callbacks
    path('webhook/', signature_views.signature_webhook, name='signature_webhook'),
    
    # Analytics
    path('analytics/', signature_views.signature_analytics, name='signature_analytics'),
]

# API URLs (for AJAX and external integrations)
api_urlpatterns = [
    # Document API
    path('documents/', include([
        path('search/', TemplateView.as_view(template_name='api/search.html'), name='api_document_search'),
        path('<int:document_id>/collaborators/', TemplateView.as_view(), name='api_document_collaborators'),
        path('<int:document_id>/activity/', TemplateView.as_view(), name='api_document_activity'),
        path('<int:document_id>/autosave/', TemplateView.as_view(), name='api_document_autosave'),
    ])),
    
    # Template API
    path('templates/', include([
        path('categories/', TemplateView.as_view(), name='api_template_categories'),
        path('<int:template_id>/render/', TemplateView.as_view(), name='api_template_render'),
        path('validate/', TemplateView.as_view(), name='api_template_validate'),
    ])),
    
    # Workflow API
    path('workflows/', include([
        path('tasks/', TemplateView.as_view(), name='api_workflow_tasks'),
        path('<int:workflow_id>/progress/', TemplateView.as_view(), name='api_workflow_progress'),
        path('notifications/', TemplateView.as_view(), name='api_workflow_notifications'),
    ])),
    
    # AI API
    path('ai/', include([
        path('suggestions/', TemplateView.as_view(), name='api_ai_suggestions'),
        path('generate/', TemplateView.as_view(), name='api_ai_generate'),
        path('analyze/', TemplateView.as_view(), name='api_ai_analyze'),
        path('translate/', TemplateView.as_view(), name='api_ai_translate'),
    ])),
]

# Main URL patterns
urlpatterns = [
    # Dashboard
    path('', TemplateView.as_view(template_name='document_editor/dashboard.html'), name='dashboard'),
    
    # Module sections
    path('documents/', include(document_urlpatterns)),
    path('templates/', include(template_urlpatterns)),
    path('workflows/', include(workflow_urlpatterns)),
    path('signatures/', include(signature_urlpatterns)),
    
    # API endpoints
    path('api/', include(api_urlpatterns)),
    
    # Settings and Configuration
    path('settings/', TemplateView.as_view(template_name='document_editor/settings.html'), name='settings'),
    path('help/', TemplateView.as_view(template_name='document_editor/help.html'), name='help'),
    
    # Reports and Analytics
    path('reports/', include([
        path('', TemplateView.as_view(template_name='document_editor/reports/index.html'), name='reports_index'),
        path('documents/', TemplateView.as_view(template_name='document_editor/reports/documents.html'), name='reports_documents'),
        path('usage/', TemplateView.as_view(template_name='document_editor/reports/usage.html'), name='reports_usage'),
        path('performance/', TemplateView.as_view(template_name='document_editor/reports/performance.html'), name='reports_performance'),
    ])),
    
    # Bulk Operations
    path('bulk/', include([
        path('documents/', TemplateView.as_view(template_name='document_editor/bulk/documents.html'), name='bulk_documents'),
        path('export/', TemplateView.as_view(), name='bulk_export'),
        path('import/', TemplateView.as_view(), name='bulk_import'),
    ])),
]
