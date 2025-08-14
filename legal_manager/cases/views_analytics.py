from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

class AnalyticsDashboardView(LoginRequiredMixin, TemplateView):
    """Analytics Dashboard View"""
    template_name = 'analytics/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'Analytics Dashboard',
            'breadcrumbs': [
                {'name': 'Dashboard', 'url': '/'},
                {'name': 'Analytics', 'url': None}
            ]
        })
        return context

@login_required
def analytics_dashboard(request):
    """Simple function-based view for analytics dashboard"""
    return render(request, 'analytics/dashboard.html', {
        'page_title': 'Analytics Dashboard'
    })