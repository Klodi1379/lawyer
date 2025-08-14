from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    # Web Views
    RegistrationView, CustomLoginView, CustomLogoutView,
    ProfileView, ProfileUpdateView, UserListView, UserUpdateView,
    CustomPasswordChangeView, CaseListView, CaseDetailView, CaseCreateView, 
    CaseUpdateView,
    
    # Client Views
    ClientListView, ClientCreateView, ClientDetailView, ClientUpdateView,
    
    # Document Views
    DocumentListView, DocumentUploadView, DocumentDetailView, DocumentUpdateView,
    DocumentDeleteView, DocumentVersionCreateView, document_download, document_version_download,
    
    # Event Views
    EventCreateView, EventListView, EventCalendarView, EventDetailView,
    EventUpdateView, EventDeleteView, calendar_api,
    
    # API ViewSets
    UserViewSet, ClientViewSet, CaseViewSet, CaseDocumentViewSet,
    CaseEventViewSet, TimeEntryViewSet, InvoiceViewSet
)

# Dashboard Views - Simple and Enhanced
from .dashboard_views import DashboardView, dashboard_stats_api as quick_stats_api

# Enhanced API Stats
from .views_api_stats import (
    enhanced_stats_api, navbar_stats_api, search_api, 
    notifications_api, quick_stats_api as dashboard_quick_stats
)

# Enhanced Dashboard Views
from .dashboard_views_enhanced import (
    EnhancedDashboardView, dashboard_widget_api, calendar_widget_api,
    quick_actions_api, notifications_api, mini_calendar_api,
    dashboard_export_api, dashboard_refresh_api
)

# New Views for Billing, Analytics, Portal
from .views_billing import (
    BillingDashboardView, billing_dashboard, InvoicesListView, 
    GenerateInvoiceView, InvoiceDetailView, record_payment, 
    send_invoice, download_invoice_pdf, get_time_entries,
    ExpensesListView, CreateExpenseView, ExpenseDetailView, mark_expense_reimbursed,
    PaymentsListView, payment_details, payment_receipt, export_payments, RecordManualPaymentView,
    ExpenseCategoriesListView, CreateExpenseCategoryView, UpdateExpenseCategoryView, 
    delete_expense_category, expense_export, expense_analytics, duplicate_expense
)
from .views_analytics import AnalyticsDashboardView, analytics_dashboard
from .views_portal import ClientPortalView, client_portal_dashboard

# LLM and AI Views
from .llm_views import (
    DocumentEditorView, llm_chat_api, document_save_api, document_export_api,
    document_templates_api, quick_stats_api, llm_document_analysis_api
)

from .health_views import health_check, ready_check, live_check

# API Router
router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'clients', ClientViewSet)
router.register(r'cases', CaseViewSet, basename='case')
router.register(r'documents', CaseDocumentViewSet)
router.register(r'events', CaseEventViewSet)
router.register(r'time-entries', TimeEntryViewSet)
router.register(r'invoices', InvoiceViewSet)

urlpatterns = [
    # Health check endpoints
    path('health/', health_check, name='health_check'),
    path('ready/', ready_check, name='ready_check'),
    path('live/', live_check, name='live_check'),
    
    # API URLs
    path('api/', include(router.urls)),
    path('api-auth/', include('rest_framework.urls')),
    
    # Dashboard URLs - Using Simple Dashboard
    path('', DashboardView.as_view(), name='dashboard'),
    path('dashboard/', DashboardView.as_view(), name='simple_dashboard'),
    path('dashboard/enhanced/', EnhancedDashboardView.as_view(), name='enhanced_dashboard'),
    path('dashboard/api/quick-stats/', quick_stats_api, name='dashboard_quick_stats_api'),
    path('dashboard/api/widgets/<str:widget_name>/', dashboard_widget_api, name='dashboard_widget_api'),
    path('dashboard/api/calendar/', calendar_widget_api, name='dashboard_calendar_api'),
    path('dashboard/api/quick-actions/', quick_actions_api, name='dashboard_quick_actions_api'),
    path('dashboard/api/notifications/', notifications_api, name='dashboard_notifications_api'),
    path('dashboard/api/mini-calendar/', mini_calendar_api, name='dashboard_mini_calendar_api'),
    path('dashboard/api/export/', dashboard_export_api, name='dashboard_export_api'),
    path('dashboard/api/refresh/', dashboard_refresh_api, name='dashboard_refresh_api'),
    path('dashboard/api/quick-stats/', quick_stats_api, name='dashboard_quick_stats_api'),
    
    # LLM and AI URLs
    path('document-editor/', DocumentEditorView.as_view(), name='document_editor'),
    path('document-editor/<int:document_id>/', DocumentEditorView.as_view(), name='document_editor_edit'),
    path('api/llm/chat/', llm_chat_api, name='llm_chat_api'),
    path('api/llm/analysis/', llm_document_analysis_api, name='llm_analysis_api'),
    path('api/documents/save/', document_save_api, name='document_save_api'),
    path('api/documents/<int:document_id>/export/', document_export_api, name='document_export_api'),
    path('api/templates/', document_templates_api, name='document_templates_api'),
    
    # User Management URLs
    path('register/', RegistrationView.as_view(), name='register'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/update/', ProfileUpdateView.as_view(), name='profile_update'),
    path('users/', UserListView.as_view(), name='user_list'),
    path('users/<int:pk>/update/', UserUpdateView.as_view(), name='user_update'),
    path('password/change/', CustomPasswordChangeView.as_view(), name='password_change'),
    
    # Case Management URLs
    path('cases/', CaseListView.as_view(), name='case_list'),
    path('cases/create/', CaseCreateView.as_view(), name='case_create'),
    path('cases/<int:pk>/', CaseDetailView.as_view(), name='case_detail'),
    path('cases/<int:pk>/edit/', CaseUpdateView.as_view(), name='case_update'),
    
    # Client Management URLs
    path('clients/', ClientListView.as_view(), name='client_list'),
    path('clients/create/', ClientCreateView.as_view(), name='client_create'),
    path('clients/<int:pk>/', ClientDetailView.as_view(), name='client_detail'),
    path('clients/<int:pk>/edit/', ClientUpdateView.as_view(), name='client_update'),
    
    # Document Management URLs
    path('documents/', DocumentListView.as_view(), name='document_list'),
    path('documents/upload/', DocumentUploadView.as_view(), name='document_upload'),
    path('documents/<int:pk>/', DocumentDetailView.as_view(), name='document_detail'),
    path('documents/<int:pk>/download/', document_download, name='document_download'),
    path('documents/<int:pk>/edit/', DocumentUpdateView.as_view(), name='document_update'),
    path('documents/<int:pk>/delete/', DocumentDeleteView.as_view(), name='document_delete'),
    path('documents/<int:document_pk>/new-version/', DocumentVersionCreateView.as_view(), name='document_version_upload'),
    path('document-versions/<int:pk>/download/', document_version_download, name='document_version_download'),
    path('cases/<int:case_pk>/documents/upload/', DocumentUploadView.as_view(), name='case_document_upload'),
    
    # Event Management URLs
    path('calendar/', EventCalendarView.as_view(), name='event_calendar'),
    path('events/', EventListView.as_view(), name='event_list'),
    path('events/create/', EventCreateView.as_view(), name='event_create'),
    path('events/<int:pk>/', EventDetailView.as_view(), name='event_detail'),
    path('events/<int:pk>/edit/', EventUpdateView.as_view(), name='event_update'),
    path('events/<int:pk>/delete/', EventDeleteView.as_view(), name='event_delete'),
    path('cases/<int:case_pk>/events/create/', EventCreateView.as_view(), name='case_event_create'),
    
    # Calendar API
    path('api/calendar/', calendar_api, name='calendar_api'),
    
    # Enhanced API Stats Endpoints
    path('api/dashboard/enhanced-stats/', enhanced_stats_api, name='enhanced_stats_api'),
    path('api/dashboard/navbar-stats/', navbar_stats_api, name='navbar_stats_api'), 
    path('api/dashboard/quick-stats/', dashboard_quick_stats, name='dashboard_quick_stats'),
    path('api/search/', search_api, name='search_api'),
    path('api/notifications/', notifications_api, name='notifications_api'),
    
    # Billing URLs
    path('billing/', BillingDashboardView.as_view(), name='billing_dashboard'),
    path('billing/dashboard/', billing_dashboard, name='billing_dashboard_func'),
    
    # Invoice Management URLs
    path('billing/invoices/', InvoicesListView.as_view(), name='invoices_list'),
    path('billing/invoices/create/', GenerateInvoiceView.as_view(), name='generate_invoice'),
    path('billing/invoices/<int:pk>/', InvoiceDetailView.as_view(), name='invoice_detail'),
    path('billing/invoices/<int:pk>/edit/', GenerateInvoiceView.as_view(), name='invoice_edit'),
    
    # Invoice Actions (AJAX)
    path('billing/invoices/<int:invoice_id>/payment/', record_payment, name='record_payment'),
    path('billing/invoices/<int:invoice_id>/send/', send_invoice, name='send_invoice'),
    path('billing/invoices/<int:invoice_id>/pdf/', download_invoice_pdf, name='download_invoice_pdf'),
    
    # Time Entries API for billing
    path('billing/time-entries/<int:case_id>/', get_time_entries, name='get_time_entries'),
    
    # Expense Management URLs
    path('billing/expenses/', ExpensesListView.as_view(), name='expenses_list'),
    path('billing/expenses/create/', CreateExpenseView.as_view(), name='create_expense'),
    path('billing/expenses/<int:pk>/', ExpenseDetailView.as_view(), name='expense_detail'),
    path('billing/expenses/<int:pk>/edit/', CreateExpenseView.as_view(), name='expense_edit'),
    path('billing/expenses/<int:expense_id>/reimburse/', mark_expense_reimbursed, name='mark_expense_reimbursed'),
    path('billing/expenses/<int:expense_id>/duplicate/', duplicate_expense, name='duplicate_expense'),
    path('billing/expenses/export/', expense_export, name='expense_export'),
    path('billing/expenses/analytics/', expense_analytics, name='expense_analytics'),
    
    # Expense Categories Management URLs
    path('billing/categories/', ExpenseCategoriesListView.as_view(), name='expense_categories'),
    path('billing/categories/create/', CreateExpenseCategoryView.as_view(), name='create_expense_category'),
    path('billing/categories/<int:pk>/edit/', UpdateExpenseCategoryView.as_view(), name='update_expense_category'),
    path('billing/categories/<int:category_id>/delete/', delete_expense_category, name='delete_expense_category'),
    
    # Payment Management URLs
    path('billing/payments/', PaymentsListView.as_view(), name='payments_list'),
    path('billing/payments/record/', RecordManualPaymentView.as_view(), name='record_manual_payment'),
    path('billing/payments/<int:payment_id>/details/', payment_details, name='payment_details'),
    path('billing/payments/<int:payment_id>/receipt/', payment_receipt, name='payment_receipt'),
    path('billing/payments/export/', export_payments, name='export_payments'),
    
    # Analytics URLs
    path('analytics/', AnalyticsDashboardView.as_view(), name='analytics_dashboard'),
    path('analytics/dashboard/', analytics_dashboard, name='analytics_dashboard_func'),
    
    # Client Portal URLs
    path('portal/', ClientPortalView.as_view(), name='client_portal'),
    path('portal/dashboard/', client_portal_dashboard, name='client_portal_func'),
]

# Add test URLs if test_views.py exists
import os
if os.path.exists('test_views.py'):
    try:
        from test_views import layout_test_view, health_check as test_health_check
        urlpatterns += [
            path('test-layout/', layout_test_view, name='test_layout'),
            path('test-health/', test_health_check, name='test_health'),
        ]
    except ImportError:
        pass
