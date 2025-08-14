from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

class ClientPortalView(LoginRequiredMixin, TemplateView):
    """Client Portal Dashboard View"""
    template_name = 'portal/client_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'Client Portal',
            'breadcrumbs': [
                {'name': 'Dashboard', 'url': '/'},
                {'name': 'Client Portal', 'url': None}
            ]
        })
        return context

@login_required
def client_portal_dashboard(request):
    """Simple function-based view for client portal"""
    return render(request, 'portal/client_dashboard.html', {
        'page_title': 'Client Portal'
    })