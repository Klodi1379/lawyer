from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required

def layout_test_view(request):
    """Simple view to test layout functionality"""
    context = {
        'test_data': {
            'cases_count': 5,
            'documents_count': 12,
            'events_count': 8,
        }
    }
    return render(request, 'test_layout.html', context)

def health_check(request):
    """Health check endpoint"""
    return HttpResponse("OK - Legal Case Manager is running")
