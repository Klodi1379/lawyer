"""
Enhanced URL Configuration për Advanced Features
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Import views për tre modulet e reja
from .views_billing import (
    AdvancedInvoiceViewSet, ExpenseViewSet, PaymentViewSet, 
    CurrencyViewSet, BillingRateViewSet,
    InvoiceListView, InvoiceDetailView, ExpenseListView,
    billing_dashboard, generate_recurring_invoices_view
)

from .views_client_portal import (
    ClientPortalViewSet, ClientDashboardView, ClientCasesView,
    ClientCaseDetailView, ClientDocumentsView, ClientInvoicesView,
    ClientPaymentsView, ClientMessagesView, client_document_download,
    client_case_timeline
)

from .views_analytics import (
    AnalyticsViewSet, ReportsViewSet, KPIViewSet,
    analytics_dashboard, financial_reports_view,
    performance_reports_view, case_outcome_reports_view
)

# Router për API endpoints
router = DefaultRouter()

# Billing API routes
router.register(r'billing/invoices', AdvancedInvoiceViewSet, basename='billing-invoices')
router.register(r'billing/expenses', ExpenseViewSet, basename='billing-expenses')
router.register(r'billing/payments', PaymentViewSet, basename='billing-payments')
router.register(r'billing/currencies', CurrencyViewSet, basename='billing-currencies')
router.register(r'billing/rates', BillingRateViewSet, basename='billing-rates')

# Client Portal API routes
router.register(r'client-portal', ClientPortalViewSet, basename='client-portal')

# Analytics API routes
router.register(r'analytics', AnalyticsViewSet, basename='analytics')
router.register(r'reports', ReportsViewSet, basename='reports')
router.register(r'kpi', KPIViewSet, basename='kpi')

# URL Patterns
urlpatterns = [
    # API URLs
    path('api/', include(router.urls)),
    
    # =============================================================================
    # BILLING URLS
    # =============================================================================
    path('billing/', include([
        # Dashboard
        path('', billing_dashboard, name='billing_dashboard'),
        
        # Invoices
        path('invoices/', InvoiceListView.as_view(), name='invoice_list'),
        path('invoices/<int:pk>/', InvoiceDetailView.as_view(), name='invoice_detail'),
        path('invoices/<int:pk>/pdf/', 'views_billing.invoice_pdf_view', name='invoice_pdf'),
        
        # Expenses
        path('expenses/', ExpenseListView.as_view(), name='expense_list'),
        path('expenses/create/', 'views_billing.expense_create_view', name='expense_create'),
        
        # Recurring Invoices
        path('recurring/generate/', generate_recurring_invoices_view, name='generate_recurring_invoices'),
        
        # Reports
        path('reports/', include([
            path('revenue/', 'views_billing.revenue_report_view', name='revenue_report'),
            path('collections/', 'views_billing.collection_report_view', name='collection_report'),
            path('aging/', 'views_billing.aging_report_view', name='aging_report'),
        ])),
    ])),
    
    # =============================================================================
    # CLIENT PORTAL URLS
    # =============================================================================
    path('portal/', include([
        # Main dashboard
        path('', ClientDashboardView.as_view(), name='client_dashboard'),
        
        # Cases
        path('cases/', ClientCasesView.as_view(), name='client_cases'),
        path('cases/<int:pk>/', ClientCaseDetailView.as_view(), name='client_case_detail'),
        
        # Documents
        path('documents/', ClientDocumentsView.as_view(), name='client_documents'),
        path('documents/download/<int:share_id>/', client_document_download, name='client_document_download'),
        
        # Financial
        path('invoices/', ClientInvoicesView.as_view(), name='client_invoices'),
        path('invoices/<int:pk>/', 'views_client_portal.client_invoice_detail', name='client_invoice_detail'),
        path('payments/', ClientPaymentsView.as_view(), name='client_payments'),
        
        # Communication
        path('messages/', ClientMessagesView.as_view(), name='client_messages'),
        path('messages/compose/', 'views_client_portal.client_message_compose', name='client_message_compose'),
        path('messages/<int:pk>/', 'views_client_portal.client_message_detail', name='client_message_detail'),
        
        # Feedback
        path('feedback/', 'views_client_portal.client_feedback_view', name='client_feedback'),
        
        # Settings
        path('settings/', 'views_client_portal.client_settings_view', name='client_settings'),
        
        # API endpoints specifike për client portal
        path('api/timeline/<int:case_id>/', client_case_timeline, name='client_case_timeline'),
    ], namespace='client_portal')),
    
    # =============================================================================
    # ANALYTICS & REPORTING URLS
    # =============================================================================
    path('analytics/', include([
        # Main dashboard
        path('', analytics_dashboard, name='analytics_dashboard'),
        
        # Financial Reports
        path('financial/', include([
            path('', financial_reports_view, name='financial_reports'),
            path('revenue/', 'views_analytics.revenue_analysis_view', name='revenue_analysis'),
            path('profitability/', 'views_analytics.profitability_analysis_view', name='profitability_analysis'),
            path('cash-flow/', 'views_analytics.cash_flow_analysis_view', name='cash_flow_analysis'),
        ])),
        
        # Performance Reports
        path('performance/', include([
            path('', performance_reports_view, name='performance_reports'),
            path('users/', 'views_analytics.user_performance_view', name='user_performance'),
            path('cases/', 'views_analytics.case_performance_view', name='case_performance'),
            path('utilization/', 'views_analytics.time_utilization_view', name='time_utilization'),
        ])),
        
        # Case Outcome Analysis
        path('outcomes/', include([
            path('', case_outcome_reports_view, name='case_outcome_reports'),
            path('success-rates/', 'views_analytics.success_rate_analysis_view', name='success_rate_analysis'),
            path('by-category/', 'views_analytics.outcome_by_category_view', name='outcome_by_category'),
            path('trends/', 'views_analytics.outcome_trends_view', name='outcome_trends'),
        ])),
        
        # KPI Dashboard
        path('kpi/', include([
            path('', 'views_analytics.kpi_dashboard_view', name='kpi_dashboard'),
            path('create/', 'views_analytics.kpi_create_view', name='kpi_create'),
            path('<int:pk>/edit/', 'views_analytics.kpi_edit_view', name='kpi_edit'),
        ])),
        
        # Custom Reports
        path('custom/', include([
            path('', 'views_analytics.custom_reports_view', name='custom_reports'),
            path('builder/', 'views_analytics.report_builder_view', name='report_builder'),
            path('<int:pk>/', 'views_analytics.custom_report_detail_view', name='custom_report_detail'),
        ])),
        
        # Export functionality
        path('export/', include([
            path('excel/<str:report_type>/', 'views_analytics.export_excel_view', name='export_excel'),
            path('pdf/<str:report_type>/', 'views_analytics.export_pdf_view', name='export_pdf'),
            path('csv/<str:report_type>/', 'views_analytics.export_csv_view', name='export_csv'),
        ])),
    ], namespace='analytics')),
    
    # =============================================================================
    # ADMINISTRATION URLS (për konfigurimin e sistemit)
    # =============================================================================
    path('admin-enhanced/', include([
        # Billing Configuration
        path('billing/', include([
            path('currencies/', 'views_admin.currency_management_view', name='admin_currencies'),
            path('rates/', 'views_admin.billing_rates_management_view', name='admin_billing_rates'),
            path('expense-categories/', 'views_admin.expense_categories_view', name='admin_expense_categories'),
            path('invoice-templates/', 'views_admin.invoice_templates_view', name='admin_invoice_templates'),
        ])),
        
        # Client Portal Configuration
        path('portal/', include([
            path('access/', 'views_admin.client_portal_access_view', name='admin_portal_access'),
            path('widgets/', 'views_admin.dashboard_widgets_view', name='admin_dashboard_widgets'),
            path('notifications/', 'views_admin.notification_settings_view', name='admin_notifications'),
        ])),
        
        # Analytics Configuration
        path('analytics/', include([
            path('kpi/', 'views_admin.kpi_management_view', name='admin_kpi_management'),
            path('reports/', 'views_admin.report_templates_view', name='admin_report_templates'),
            path('metrics/', 'views_admin.metrics_configuration_view', name='admin_metrics_config'),
        ])),
        
        # System Settings
        path('system/', include([
            path('backup/', 'views_admin.system_backup_view', name='admin_system_backup'),
            path('maintenance/', 'views_admin.system_maintenance_view', name='admin_system_maintenance'),
            path('integrations/', 'views_admin.integrations_view', name='admin_integrations'),
        ])),
    ], namespace='admin_enhanced')),
    
    # =============================================================================
    # AJAX & API ENDPOINTS për funksionalitet dinamik
    # =============================================================================
    path('ajax/', include([
        # Billing AJAX
        path('billing/', include([
            path('calculate-invoice/', 'views_ajax.calculate_invoice_totals', name='ajax_calculate_invoice'),
            path('validate-payment/', 'views_ajax.validate_payment_data', name='ajax_validate_payment'),
            path('currency-rates/', 'views_ajax.get_currency_rates', name='ajax_currency_rates'),
        ])),
        
        # Client Portal AJAX  
        path('portal/', include([
            path('notifications/mark-read/', 'views_ajax.mark_notifications_read', name='ajax_mark_notifications_read'),
            path('documents/check-access/', 'views_ajax.check_document_access', name='ajax_check_document_access'),
            path('messages/count/', 'views_ajax.get_unread_message_count', name='ajax_message_count'),
        ])),
        
        # Analytics AJAX
        path('analytics/', include([
            path('chart-data/<str:chart_type>/', 'views_ajax.get_chart_data', name='ajax_chart_data'),
            path('kpi-update/', 'views_ajax.update_kpi_values', name='ajax_update_kpi'),
            path('report-progress/', 'views_ajax.get_report_progress', name='ajax_report_progress'),
        ])),
        
        # General AJAX
        path('search/', include([
            path('cases/', 'views_ajax.search_cases', name='ajax_search_cases'),
            path('clients/', 'views_ajax.search_clients', name='ajax_search_clients'),
            path('users/', 'views_ajax.search_users', name='ajax_search_users'),
        ])),
    ])),
]

# Shtojmë URL patterns ekzistuese nëse ekzistojnë
try:
    from .urls import urlpatterns as existing_patterns
    urlpatterns = existing_patterns + urlpatterns
except ImportError:
    # Nëse nuk ka urls.py ekzistues, vazhdojmë me pattern-et e reja
    pass