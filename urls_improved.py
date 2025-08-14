# urls_improved.py - URL Configuration për sistemin e përmirësuar
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views_improved

# ==========================================
# API ROUTER CONFIGURATION
# ==========================================

router = DefaultRouter()
router.register(r'users', views_improved.UserViewSet)
router.register(r'clients', views_improved.ClientViewSet)
router.register(r'cases', views_improved.CaseViewSet)
router.register(r'documents', views_improved.DocumentViewSet)
router.register(r'document-categories', views_improved.DocumentCategoryViewSet)
router.register(r'document-types', views_improved.DocumentTypeViewSet)
router.register(r'document-statuses', views_improved.DocumentStatusViewSet)

# ==========================================
# MAIN URL PATTERNS
# ==========================================

app_name = 'legal_manager'

urlpatterns = [
    # API endpoints
    path('api/', include(router.urls)),
    
    # Authentication endpoints
    path('api/auth/', include('rest_framework.urls')),
    
    # Custom API endpoints (non-CRUD)
    path('api/documents/bulk-action/', views_improved.DocumentViewSet.as_view({'post': 'bulk_action'}), name='document_bulk_action'),
    path('api/documents/create-from-template/', views_improved.DocumentViewSet.as_view({'post': 'create_from_template'}), name='document_create_from_template'),
    path('api/documents/<int:pk>/download/', views_improved.DocumentViewSet.as_view({'get': 'download'}), name='document_download'),
    path('api/documents/<int:pk>/grant-access/', views_improved.DocumentViewSet.as_view({'post': 'grant_access'}), name='document_grant_access'),
    path('api/cases/<int:pk>/add-document/', views_improved.CaseViewSet.as_view({'post': 'add_document'}), name='case_add_document'),
]

# ==========================================
# DOCUMENTATION URL PATTERNS
# ==========================================

# Nëse do të shtosh Swagger/OpenAPI documentation
try:
    from drf_yasg.views import get_schema_view
    from drf_yasg import openapi
    from rest_framework import permissions
    
    schema_view = get_schema_view(
        openapi.Info(
            title="Legal Case Manager API",
            default_version='v1',
            description="API për sistemin e menaxhimit të rasteve juridike",
            terms_of_service="https://www.yourcompany.com/terms/",
            contact=openapi.Contact(email="contact@yourcompany.com"),
            license=openapi.License(name="Proprietary License"),
        ),
        public=True,
        permission_classes=(permissions.AllowAny,),
    )
    
    urlpatterns += [
        path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
        path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
        path('api/schema/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    ]
    
except ImportError:
    # drf_yasg not installed, skip documentation URLs
    pass

# ==========================================
# HEALTH CHECK AND STATUS
# ==========================================

from django.http import JsonResponse
from django.db import connection
from django.utils import timezone

def health_check(request):
    """Health check endpoint për monitoring"""
    try:
        # Test database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        return JsonResponse({
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'database': 'connected',
            'version': '1.0.0'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'unhealthy',
            'timestamp': timezone.now().isoformat(),
            'error': str(e)
        }, status=503)

def api_info(request):
    """API info endpoint"""
    return JsonResponse({
        'name': 'Legal Case Manager API',
        'version': '1.0.0',
        'description': 'API për sistemin e menaxhimit të rasteve juridike',
        'endpoints': {
            'users': '/api/users/',
            'clients': '/api/clients/',
            'cases': '/api/cases/',
            'documents': '/api/documents/',
            'document_categories': '/api/document-categories/',
            'document_types': '/api/document-types/',
            'document_statuses': '/api/document-statuses/',
        },
        'documentation': {
            'swagger': '/api/docs/',
            'redoc': '/api/redoc/',
        }
    })

urlpatterns += [
    path('api/health/', health_check, name='health_check'),
    path('api/', api_info, name='api_info'),
]
