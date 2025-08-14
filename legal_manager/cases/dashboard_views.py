# dashboard_views.py - Professional Dashboard për Legal Case Manager (RREGULLUAR)
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.db.models import Count, Sum, Q, Avg, Max, Min, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import json

from .models import (
    User, Client, Case, CaseDocument, CaseEvent, 
    TimeEntry, Invoice, AuditLog, UserAuditLog
)

# ==========================================
# DASHBOARD VIEW (RREGULLUAR)
# ==========================================

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get date ranges
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        year_ago = today - timedelta(days=365)
        
        if user.role == 'admin':
            context.update(self.get_admin_dashboard_data(today, week_ago, month_ago, year_ago))
        elif user.role in ['lawyer', 'paralegal']:
            context.update(self.get_lawyer_dashboard_data(user, today, week_ago, month_ago, year_ago))
        elif user.role == 'client':
            context.update(self.get_client_dashboard_data(user, today, week_ago, month_ago, year_ago))
        
        # Common data for all roles
        context.update({
            'user': user,
            'today': today,
            'current_time': timezone.now(),
            # Recent cases for all roles
            'recent_cases': self.get_recent_cases(user),
            # Upcoming deadlines for all roles  
            'upcoming_deadlines': self.get_upcoming_deadlines(user, today),
        })
        
        return context
    
    def get_recent_cases(self, user):
        """Get recent cases based on user role"""
        if user.role == 'admin':
            return Case.objects.select_related('client', 'assigned_to').order_by('-updated_at')[:10]
        elif user.role in ['lawyer', 'paralegal']:
            return Case.objects.filter(assigned_to=user).select_related('client').order_by('-updated_at')[:10]
        elif user.role == 'client':
            try:
                client = Client.objects.get(email=user.email)
                return Case.objects.filter(client=client).select_related('assigned_to').order_by('-updated_at')[:10]
            except Client.DoesNotExist:
                return Case.objects.none()
        return Case.objects.none()
    
    def get_upcoming_deadlines(self, user, today):
        """Get upcoming deadlines based on user role"""
        base_query = CaseEvent.objects.filter(
            is_deadline=True,
            starts_at__gte=today,
            starts_at__lte=today + timedelta(days=14)
        ).select_related('case')
        
        if user.role == 'admin':
            return base_query.order_by('starts_at')[:5]
        elif user.role in ['lawyer', 'paralegal']:
            return base_query.filter(case__assigned_to=user).order_by('starts_at')[:5]
        elif user.role == 'client':
            try:
                client = Client.objects.get(email=user.email)
                return base_query.filter(case__client=client).order_by('starts_at')[:5]
            except Client.DoesNotExist:
                return CaseEvent.objects.none()
        return CaseEvent.objects.none()
    
    def get_admin_dashboard_data(self, today, week_ago, month_ago, year_ago):
        """Dashboard data për admin users"""
        
        # Basic statistics
        total_cases = Case.objects.count()
        total_clients = Client.objects.count()
        total_documents = CaseDocument.objects.count()
        total_users = User.objects.filter(is_active=True).count()
        
        # Recent statistics
        new_cases_week = Case.objects.filter(created_at__gte=week_ago).count()
        new_clients_week = Client.objects.filter(created_at__gte=week_ago).count()
        new_documents_week = CaseDocument.objects.filter(created_at__gte=week_ago).count()
        
        # Case status breakdown
        case_status_data = Case.objects.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        # Case type breakdown
        case_type_data = Case.objects.values('case_type').annotate(
            count=Count('id')
        ).order_by('case_type')
        
        # Monthly case trends (últimos 12 meses)
        monthly_cases = []
        for i in range(12):
            month_start = today.replace(day=1) - timedelta(days=30*i)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            count = Case.objects.filter(
                created_at__range=[month_start, month_end]
            ).count()
            monthly_cases.append({
                'month': month_start.strftime('%b %Y'),
                'count': count
            })
        
        # Top lawyers by cases
        top_lawyers = User.objects.filter(
            role__in=['lawyer', 'paralegal']
        ).annotate(
            case_count=Count('assigned_cases')
        ).order_by('-case_count')[:5]
        
        # ✅ RREGULLUAR: Financial overview me aggregation të saktë
        total_invoices = Invoice.objects.aggregate(
            total=Coalesce(Sum('total_amount'), 0, output_field=DecimalField()),
            # ✅ KORREKT: Sum amounts nga paid invoices (jo boolean field)
            paid_amount=Coalesce(Sum('total_amount', filter=Q(paid=True)), 0, output_field=DecimalField()),
            unpaid=Coalesce(Sum('total_amount', filter=Q(paid=False)), 0, output_field=DecimalField()),
            # ✅ KORREKT: Count paid/unpaid invoices
            paid_count=Count('id', filter=Q(paid=True)),
            unpaid_count=Count('id', filter=Q(paid=False)),
            total_count=Count('id')
        )
        
        # Recent activities
        recent_activities = AuditLog.objects.select_related('user').order_by('-created_at')[:10]
        
        # Upcoming deadlines
        upcoming_deadlines = CaseEvent.objects.filter(
            is_deadline=True,
            starts_at__gte=today,
            starts_at__lte=today + timedelta(days=7)
        ).select_related('case').order_by('starts_at')[:5]
        
        # Document type breakdown
        doc_type_data = CaseDocument.objects.values('doc_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return {
            'dashboard_type': 'admin',
            'total_cases': total_cases,
            'total_clients': total_clients,
            'total_documents': total_documents,
            'total_users': total_users,
            'new_cases_week': new_cases_week,
            'new_clients_week': new_clients_week,
            'new_documents_week': new_documents_week,
            'case_status_data': case_status_data,
            'case_type_data': case_type_data,
            'monthly_cases': json.dumps(list(reversed(monthly_cases))),
            'top_lawyers': top_lawyers,
            'total_invoices': total_invoices,
            'recent_activities': recent_activities,
            'upcoming_deadlines': upcoming_deadlines,
            'doc_type_data': doc_type_data,
        }
    
    def get_lawyer_dashboard_data(self, user, today, week_ago, month_ago, year_ago):
        """Dashboard data për lawyer/paralegal users"""
        
        # User's cases
        my_cases = Case.objects.filter(assigned_to=user)
        total_my_cases = my_cases.count()
        open_cases = my_cases.filter(status='open').count()
        closed_cases = my_cases.filter(status='closed').count()
        
        # Recent activity on my cases
        recent_documents = CaseDocument.objects.filter(
            case__assigned_to=user
        ).order_by('-created_at')[:5]
        
        # My upcoming deadlines
        my_deadlines = CaseEvent.objects.filter(
            case__assigned_to=user,
            is_deadline=True,
            starts_at__gte=today,
            starts_at__lte=today + timedelta(days=14)
        ).select_related('case').order_by('starts_at')[:10]
        
        # Time entries this week
        my_time_entries = TimeEntry.objects.filter(
            user=user,
            created_at__gte=week_ago
        )
        total_hours_week = sum(entry.minutes for entry in my_time_entries) / 60
        
        # Case status breakdown for my cases
        my_case_status = my_cases.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        # Recent activities on my cases
        my_activities = AuditLog.objects.filter(
            target_type='case',
            target_id__in=my_cases.values_list('id', flat=True)
        ).select_related('user').order_by('-created_at')[:8]
        
        # Case load by month (últimos 6 meses)
        monthly_workload = []
        for i in range(6):
            month_start = today.replace(day=1) - timedelta(days=30*i)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            cases_opened = my_cases.filter(created_at__range=[month_start, month_end]).count()
            cases_closed = my_cases.filter(
                status='closed',
                updated_at__range=[month_start, month_end]
            ).count()
            
            monthly_workload.append({
                'month': month_start.strftime('%b'),
                'opened': cases_opened,
                'closed': cases_closed
            })
        
        return {
            'dashboard_type': 'lawyer',
            'total_my_cases': total_my_cases,
            'open_cases': open_cases,
            'closed_cases': closed_cases,
            'recent_documents': recent_documents,
            'my_deadlines': my_deadlines,
            'total_hours_week': round(total_hours_week, 1),
            'my_case_status': my_case_status,
            'my_activities': my_activities,
            'monthly_workload': json.dumps(list(reversed(monthly_workload))),
        }
    
    def get_client_dashboard_data(self, user, today, week_ago, month_ago, year_ago):
        """Dashboard data për client users"""
        
        # Client's cases (assuming client is linked via email)
        try:
            client = Client.objects.get(email=user.email)
            my_cases = Case.objects.filter(client=client)
        except Client.DoesNotExist:
            my_cases = Case.objects.none()
            client = None
        
        total_cases = my_cases.count()
        active_cases = my_cases.exclude(status='closed').count()
        
        # Recent documents for my cases
        recent_documents = CaseDocument.objects.filter(
            case__in=my_cases
        ).order_by('-created_at')[:5]
        
        # My upcoming events/deadlines
        my_events = CaseEvent.objects.filter(
            case__in=my_cases,
            starts_at__gte=today
        ).select_related('case').order_by('starts_at')[:10]
        
        # Case timeline
        case_timeline = my_cases.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        # ✅ RREGULLUAR: Invoices overview me aggregation të saktë
        my_invoices = Invoice.objects.filter(issued_to=client) if client else Invoice.objects.none()
        invoice_summary = my_invoices.aggregate(
            total=Coalesce(Sum('total_amount'), 0, output_field=DecimalField()),
            # ✅ KORREKT: Sum amounts nga paid invoices
            paid_amount=Coalesce(Sum('total_amount', filter=Q(paid=True)), 0, output_field=DecimalField()),
            unpaid=Coalesce(Sum('total_amount', filter=Q(paid=False)), 0, output_field=DecimalField()),
            # ✅ KORREKT: Count invoices
            paid_count=Count('id', filter=Q(paid=True)),
            unpaid_count=Count('id', filter=Q(paid=False)),
            total_count=Count('id')
        )
        
        return {
            'dashboard_type': 'client',
            'client': client,
            'total_cases': total_cases,
            'active_cases': active_cases,
            'recent_documents': recent_documents,
            'my_events': my_events,
            'case_timeline': case_timeline,
            'invoice_summary': invoice_summary,
            'my_invoices': my_invoices.order_by('-issued_at')[:5],
        }

# ==========================================
# QUICK STATS API VIEWS
# ==========================================

@login_required
def dashboard_stats_api(request):
    """API endpoint për real-time dashboard stats"""
    
    user = request.user
    today = timezone.now().date()
    
    if user.role == 'admin':
        stats = {
            'total_cases': Case.objects.count(),
            'active_cases': Case.objects.exclude(status='closed').count(),
            'total_documents': CaseDocument.objects.count(),
            'active_users': User.objects.filter(is_active=True).count(),
        }
    elif user.role in ['lawyer', 'paralegal']:
        my_cases = Case.objects.filter(assigned_to=user)
        stats = {
            'my_cases': my_cases.count(),
            'open_cases': my_cases.filter(status='open').count(),
            'my_documents': CaseDocument.objects.filter(case__assigned_to=user).count(),
            'deadlines_week': CaseEvent.objects.filter(
                case__assigned_to=user,
                is_deadline=True,
                starts_at__gte=today,
                starts_at__lte=today + timedelta(days=7)
            ).count(),
        }
    else:  # client
        try:
            client = Client.objects.get(email=user.email)
            my_cases = Case.objects.filter(client=client)
            stats = {
                'my_cases': my_cases.count(),
                'active_cases': my_cases.exclude(status='closed').count(),
                'recent_documents': CaseDocument.objects.filter(case__in=my_cases).count(),
            }
        except Client.DoesNotExist:
            stats = {'my_cases': 0, 'active_cases': 0, 'recent_documents': 0}
    
    return JsonResponse(stats)

@login_required
def case_analytics_api(request):
    """API për case analytics (për grafikë)"""
    
    user = request.user
    
    # Filter cases based on user role
    if user.role == 'admin':
        cases = Case.objects.all()
    elif user.role in ['lawyer', 'paralegal']:
        cases = Case.objects.filter(assigned_to=user)
    else:
        try:
            client = Client.objects.get(email=user.email)
            cases = Case.objects.filter(client=client)
        except Client.DoesNotExist:
            cases = Case.objects.none()
    
    # Case status distribution
    status_data = list(cases.values('status').annotate(count=Count('id')))
    
    # Case type distribution  
    type_data = list(cases.values('case_type').annotate(count=Count('id')))
    
    # Monthly trends (últimos 6 meses)
    monthly_data = []
    today = timezone.now().date()
    
    for i in range(6):
        month_start = today.replace(day=1) - timedelta(days=30*i)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        count = cases.filter(created_at__range=[month_start, month_end]).count()
        monthly_data.append({
            'month': month_start.strftime('%b %Y'),
            'count': count
        })
    
    return JsonResponse({
        'status_data': status_data,
        'type_data': type_data,
        'monthly_data': list(reversed(monthly_data))
    })
