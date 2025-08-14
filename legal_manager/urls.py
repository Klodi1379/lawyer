"""
URL configuration for legal_manager project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('legal_manager.cases.urls')),
    path('', include('legal_manager.cases.urls')),  # For web interface
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Custom admin site headers
admin.site.site_header = "Legal Case Manager Administration"
admin.site.site_title = "Legal Case Manager"
admin.site.index_title = "Welcome to Legal Case Manager Administration"
