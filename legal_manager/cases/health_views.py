from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import connections
from django.core.cache import cache
from django.conf import settings
from .models import User, Case, Client
import redis
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["GET"])
def health_check(request):
    """
    Health check endpoint for monitoring and load balancers.
    Returns system status and basic metrics.
    """
    health_data = {
        "status": "healthy",
        "timestamp": "2024-01-01T00:00:00Z",
        "version": "1.0.0",
        "checks": {}
    }
    
    # Database check
    try:
        db_conn = connections['default']
        db_conn.cursor()
        health_data["checks"]["database"] = {
            "status": "healthy",
            "connection": "ok"
        }
    except Exception as e:
        health_data["checks"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_data["status"] = "unhealthy"
    
    # Cache check (Redis)
    try:
        cache.set('health_check', 'ok', 30)
        cache_value = cache.get('health_check')
        if cache_value == 'ok':
            health_data["checks"]["cache"] = {"status": "healthy"}
        else:
            raise Exception("Cache test failed")
    except Exception as e:
        health_data["checks"]["cache"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_data["status"] = "unhealthy"
    
    # Basic metrics (only if database is healthy)
    if health_data["checks"]["database"]["status"] == "healthy":
        try:
            health_data["metrics"] = {
                "users_count": User.objects.count(),
                "cases_count": Case.objects.count(),
                "clients_count": Client.objects.count(),
                "active_cases": Case.objects.filter(status='open').count()
            }
        except Exception as e:
            logger.warning(f"Failed to get metrics: {e}")
    
    # Set appropriate HTTP status code
    status_code = 200 if health_data["status"] == "healthy" else 503
    
    return JsonResponse(health_data, status=status_code)

@csrf_exempt  
@require_http_methods(["GET"])
def ready_check(request):
    """
    Readiness check - determines if the service is ready to accept traffic.
    More strict than health check.
    """
    try:
        # Check database connectivity and basic query
        User.objects.count()
        
        # Check cache
        cache.set('ready_check', 'ok', 10)
        if cache.get('ready_check') != 'ok':
            raise Exception("Cache not ready")
        
        return JsonResponse({"status": "ready"})
    except Exception as e:
        return JsonResponse(
            {"status": "not_ready", "error": str(e)}, 
            status=503
        )

@csrf_exempt
@require_http_methods(["GET"])  
def live_check(request):
    """
    Liveness check - determines if the service is alive.
    Should be very lightweight.
    """
    return JsonResponse({"status": "alive"})
