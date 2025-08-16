# views_analytics_enhanced.py - Views të përmirësuara për Analytics

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views.generic import TemplateView
from django.utils import timezone
from datetime import timedelta, datetime, date
from .analytics_service import LegalAnalytics, get_dashboard_data, get_analytics_charts_data
import json
from decimal import Decimal

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, timezone.datetime):
            return obj.isoformat()
        return super().default(obj)

class AnalyticsDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'analytics_enhanced/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Merr të dhënat e analytics
        analytics_data = get_dashboard_data(self.request.user)
        
        # Shto në context
        context.update(analytics_data)
        
        # Konfiguro datat për charts
        context['charts_data'] = json.dumps(
            get_analytics_charts_data(self.request.user), 
            cls=DecimalEncoder
        )
        
        # Periudha për filtrim
        context['date_ranges'] = [
            {'value': 'week', 'label': 'Javën e fundit'},
            {'value': 'month', 'label': 'Muajin e fundit'},
            {'value': 'quarter', 'label': '3 muajt e fundit'},
            {'value': 'year', 'label': 'Vitin e fundit'},
            {'value': 'custom', 'label': 'Periudhë custom'},
        ]
        
        return context

@login_required
def analytics_api(request):
    """API endpoint për të dhënat e analytics"""
    period = request.GET.get('period', 'month')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Parse custom dates nëse jepen
    if date_from and date_to:
        try:
            from datetime import datetime
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        except ValueError:
            date_from = date_to = None
    
    # Krijo analytics instance
    analytics = LegalAnalytics(
        user=request.user,
        date_from=date_from,
        date_to=date_to
    )
    
    # Merr të dhënat
    data = {
        'case_stats': analytics.get_case_statistics(),
        'financial_overview': analytics.get_financial_overview(),
        'productivity': analytics.get_productivity_metrics(),
        'deadlines': analytics.get_deadline_overview(),
        'documents': analytics.get_document_metrics(),
    }
    
    # Shto team performance vetëm për admin
    if request.user.role == 'admin':
        data['team_performance'] = analytics.get_team_performance()
    
    return JsonResponse(data, encoder=DecimalEncoder)

@login_required
def case_analytics_api(request):
    """API specifike për analizën e rasteve"""
    analytics = LegalAnalytics(user=request.user)
    case_stats = analytics.get_case_statistics()
    
    # Shto të dhëna shtesë për analizën e rasteve
    from .models import Case
    
    # Raste të reja këtë muaj
    this_month_cases = Case.objects.filter(
        created_at__gte=timezone.now().replace(day=1)
    )
    if request.user.role != 'admin':
        this_month_cases = this_month_cases.filter(assigned_to=request.user)
    
    case_stats['this_month_new'] = this_month_cases.count()
    case_stats['this_month_closed'] = this_month_cases.filter(status='closed').count()
    
    # Trend comparison (muaji i kaluar)
    last_month_start = (timezone.now().replace(day=1) - timedelta(days=1)).replace(day=1)
    last_month_end = timezone.now().replace(day=1) - timedelta(days=1)
    
    last_month_cases = Case.objects.filter(
        created_at__range=[last_month_start, last_month_end]
    )
    if request.user.role != 'admin':
        last_month_cases = last_month_cases.filter(assigned_to=request.user)
    
    case_stats['last_month_new'] = last_month_cases.count()
    case_stats['growth_rate'] = (
        ((case_stats['this_month_new'] - case_stats['last_month_new']) / case_stats['last_month_new'] * 100)
        if case_stats['last_month_new'] > 0 else 0
    )
    
    return JsonResponse(case_stats, encoder=DecimalEncoder)

@login_required
def financial_analytics_api(request):
    """API specifike për analizën financiare"""
    analytics = LegalAnalytics(user=request.user)
    financial_data = analytics.get_financial_overview()
    
    # Shto KPIs shtesë
    from .models import Invoice, TimeEntry
    
    # Revenue projections
    current_month_revenue = Invoice.objects.filter(
        issued_at__month=timezone.now().month,
        issued_at__year=timezone.now().year,
        paid=True
    )
    
    if request.user.role != 'admin':
        current_month_revenue = current_month_revenue.filter(case__assigned_to=request.user)
    
    current_month_total = current_month_revenue.aggregate(
        total=models.Sum('total_amount')
    )['total'] or 0
    
    # Average invoice value
    avg_invoice_value = Invoice.objects.all()
    if request.user.role != 'admin':
        avg_invoice_value = avg_invoice_value.filter(case__assigned_to=request.user)
    
    avg_invoice = avg_invoice_value.aggregate(avg=models.Avg('total_amount'))['avg'] or 0
    
    financial_data.update({
        'current_month_revenue': float(current_month_total),
        'avg_invoice_value': round(float(avg_invoice), 2),
        'projected_monthly_revenue': float(current_month_total) * 1.1,  # Simple projection
    })
    
    return JsonResponse(financial_data, encoder=DecimalEncoder)

@login_required
def productivity_analytics_api(request):
    """API specifike për analizën e produktivitetit"""
    analytics = LegalAnalytics(user=request.user)
    productivity_data = analytics.get_productivity_metrics()
    
    # Shto metrika shtesë
    from .models import TimeEntry, Case
    
    # Billable vs non-billable hours (nëse ka fusha për këtë)
    total_time_entries = TimeEntry.objects.filter(
        created_at__gte=timezone.now() - timedelta(days=30)
    )
    
    if request.user.role != 'admin':
        total_time_entries = total_time_entries.filter(user=request.user)
    
    # Productivity trends (7 ditët e fundit)
    last_7_days = []
    for i in range(7):
        date = timezone.now().date() - timedelta(days=i)
        day_entries = total_time_entries.filter(created_at__date=date)
        day_hours = sum([entry.minutes for entry in day_entries]) / 60
        last_7_days.append({
            'date': date.strftime('%Y-%m-%d'),
            'hours': round(day_hours, 1)
        })
    
    productivity_data['last_7_days_trend'] = list(reversed(last_7_days))
    
    return JsonResponse(productivity_data, encoder=DecimalEncoder)

@login_required
def team_analytics_api(request):
    """API për analizën e ekipit (vetëm admin)"""
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    analytics = LegalAnalytics(user=request.user)
    team_data = analytics.get_team_performance()
    
    # Shto comparison metrics
    from .models import User, Case, TimeEntry
    
    all_lawyers = User.objects.filter(role='lawyer')
    team_comparison = []
    
    for lawyer in all_lawyers:
        lawyer_cases = Case.objects.filter(assigned_to=lawyer)
        lawyer_time = TimeEntry.objects.filter(
            user=lawyer,
            created_at__gte=timezone.now() - timedelta(days=30)
        )
        
        total_minutes = sum([entry.minutes for entry in lawyer_time])
        
        team_comparison.append({
            'name': lawyer.get_full_name() or lawyer.username,
            'active_cases': lawyer_cases.filter(status__in=['open', 'in_court']).count(),
            'completed_cases': lawyer_cases.filter(status='closed').count(),
            'hours_this_month': round(total_minutes / 60, 1),
            'avg_case_duration': analytics._calculate_avg_duration(lawyer_cases)
        })
    
    team_data['team_comparison'] = team_comparison
    
    return JsonResponse(team_data, encoder=DecimalEncoder)

@login_required
def export_analytics_pdf(request):
    """Export analytics në PDF"""
    from django.http import HttpResponse
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    import io
    
    # Merr të dhënat
    analytics_data = get_dashboard_data(request.user)
    
    # Krijo PDF
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    # Title
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 750, "Legal Analytics Report")
    p.setFont("Helvetica", 12)
    p.drawString(100, 730, f"Generated on: {timezone.now().strftime('%Y-%m-%d %H:%M')}")
    
    # Case Statistics
    y_position = 700
    p.setFont("Helvetica-Bold", 14)
    p.drawString(100, y_position, "Case Statistics")
    y_position -= 30
    
    case_stats = analytics_data['case_stats']
    p.setFont("Helvetica", 12)
    p.drawString(120, y_position, f"Total Cases: {case_stats['total_cases']}")
    y_position -= 20
    p.drawString(120, y_position, f"Open Cases: {case_stats['open_cases']}")
    y_position -= 20
    p.drawString(120, y_position, f"Closed Cases: {case_stats['closed_cases']}")
    y_position -= 40
    
    # Financial Overview
    p.setFont("Helvetica-Bold", 14)
    p.drawString(100, y_position, "Financial Overview")
    y_position -= 30
    
    financial = analytics_data['financial_overview']
    p.setFont("Helvetica", 12)
    p.drawString(120, y_position, f"Total Revenue: €{financial['total_revenue']:.2f}")
    y_position -= 20
    p.drawString(120, y_position, f"Paid Revenue: €{financial['paid_revenue']:.2f}")
    y_position -= 20
    p.drawString(120, y_position, f"Pending Revenue: €{financial['pending_revenue']:.2f}")
    
    p.showPage()
    p.save()
    
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="analytics_report_{timezone.now().strftime("%Y%m%d")}.pdf"'
    
    return response

# Additional utility functions
@login_required
def analytics_widget_api(request, widget_type):
    """API për widget specifike të analytics"""
    analytics = LegalAnalytics(user=request.user)
    
    if widget_type == 'cases':
        data = analytics.get_case_statistics()
    elif widget_type == 'financial':
        data = analytics.get_financial_overview()
    elif widget_type == 'productivity':
        data = analytics.get_productivity_metrics()
    elif widget_type == 'deadlines':
        data = analytics.get_deadline_overview()
    elif widget_type == 'documents':
        data = analytics.get_document_metrics()
    else:
        return JsonResponse({'error': 'Invalid widget type'}, status=400)
    
    return JsonResponse(data, encoder=DecimalEncoder)

@login_required
def refresh_analytics_cache(request):
    """Refresh cache të analytics (nëse përdoret caching)"""
    # Implemento cache refresh nëse nevojitet
    from django.core.cache import cache
    
    cache_keys = [
        f'analytics_{request.user.id}_cases',
        f'analytics_{request.user.id}_financial',
        f'analytics_{request.user.id}_productivity',
    ]
    
    cache.delete_many(cache_keys)
    
    return JsonResponse({'status': 'success', 'message': 'Analytics cache refreshed'})
