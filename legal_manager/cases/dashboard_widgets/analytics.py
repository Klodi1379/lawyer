# dashboard_widgets/analytics.py - Advanced Analytics Widgets
from django.db.models import Count, Sum, Avg, Q, F
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import json

from ..models import Case, Client, CaseDocument, CaseEvent, TimeEntry, Invoice, User


class AnalyticsWidget:
    """Base class për analytics widgets"""
    
    def __init__(self, user, date_range=None):
        self.user = user
        self.date_range = date_range or self.get_default_date_range()
    
    def get_default_date_range(self):
        """Default date range - last 30 days"""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        return (start_date, end_date)
    
    def filter_by_user_role(self, queryset, model_field='assigned_to'):
        """Filter queryset based on user role"""
        if self.user.role == 'admin':
            return queryset
        elif self.user.role in ['lawyer', 'paralegal']:
            filter_kwargs = {model_field: self.user}
            return queryset.filter(**filter_kwargs)
        else:  # client
            try:
                client = Client.objects.get(email=self.user.email)
                return queryset.filter(client=client)
            except Client.DoesNotExist:
                return queryset.none()


class CasePerformanceWidget(AnalyticsWidget):
    """Widget për case performance metrics"""
    
    def get_data(self):
        start_date, end_date = self.date_range
        
        # Filter cases based on user role
        cases = self.filter_by_user_role(Case.objects.all())
        
        # Case resolution metrics
        total_cases = cases.count()
        closed_cases = cases.filter(status='closed').count()
        resolution_rate = (closed_cases / total_cases * 100) if total_cases > 0 else 0
        
        # Average case duration
        closed_cases_with_duration = cases.filter(
            status='closed',
            updated_at__isnull=False
        ).annotate(
            duration=F('updated_at') - F('created_at')
        )
        
        avg_duration_days = 0
        if closed_cases_with_duration.exists():
            durations = [case.duration.days for case in closed_cases_with_duration]
            avg_duration_days = sum(durations) / len(durations)
        
        # Case type distribution
        case_types = cases.values('case_type').annotate(
            count=Count('id'),
            success_rate=Count('id', filter=Q(status='closed')) * 100.0 / Count('id')
        ).order_by('-count')
        
        # Monthly case trends
        monthly_trends = []
        for i in range(6):
            month_start = start_date.replace(day=1) - timedelta(days=30*i)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            month_cases = cases.filter(created_at__range=[month_start, month_end])
            
            monthly_trends.append({
                'month': month_start.strftime('%b %Y'),
                'total': month_cases.count(),
                'opened': month_cases.count(),
                'closed': month_cases.filter(status='closed').count(),
                'success_rate': month_cases.filter(status='closed').count() / max(month_cases.count(), 1) * 100
            })
        
        return {
            'total_cases': total_cases,
            'closed_cases': closed_cases,
            'resolution_rate': round(resolution_rate, 1),
            'avg_duration_days': round(avg_duration_days, 1),
            'case_types': list(case_types),
            'monthly_trends': list(reversed(monthly_trends))
        }


class FinancialPerformanceWidget(AnalyticsWidget):
    """Widget për financial performance metrics"""
    
    def get_data(self):
        start_date, end_date = self.date_range
        
        # Get invoices based on user role
        if self.user.role == 'admin':
            invoices = Invoice.objects.all()
        elif self.user.role in ['lawyer', 'paralegal']:
            invoices = Invoice.objects.filter(case__assigned_to=self.user)
        else:  # client
            try:
                client = Client.objects.get(email=self.user.email)
                invoices = Invoice.objects.filter(issued_to=client)
            except Client.DoesNotExist:
                invoices = Invoice.objects.none()
        
        # Financial metrics
        total_revenue = invoices.filter(paid=True).aggregate(
            total=Sum('total_amount')
        )['total'] or Decimal('0')
        
        pending_revenue = invoices.filter(paid=False).aggregate(
            total=Sum('total_amount')
        )['total'] or Decimal('0')
        
        # Monthly revenue trends
        monthly_revenue = []
        for i in range(6):
            month_start = start_date.replace(day=1) - timedelta(days=30*i)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            month_paid = invoices.filter(
                paid=True,
                issued_at__range=[month_start, month_end]
            ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
            
            month_pending = invoices.filter(
                paid=False,
                issued_at__range=[month_start, month_end]
            ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
            
            monthly_revenue.append({
                'month': month_start.strftime('%b %Y'),
                'paid': float(month_paid),
                'pending': float(month_pending),
                'total': float(month_paid + month_pending)
            })
        
        # Client revenue distribution
        client_revenue = invoices.values(
            'issued_to__full_name'
        ).annotate(
            total_revenue=Sum('total_amount', filter=Q(paid=True)),
            pending_revenue=Sum('total_amount', filter=Q(paid=False)),
            invoice_count=Count('id')
        ).order_by('-total_revenue')[:5]
        
        return {
            'total_revenue': float(total_revenue),
            'pending_revenue': float(pending_revenue),
            'collection_rate': float(total_revenue / (total_revenue + pending_revenue) * 100) if (total_revenue + pending_revenue) > 0 else 0,
            'monthly_revenue': list(reversed(monthly_revenue)),
            'top_clients': list(client_revenue)
        }


class ProductivityWidget(AnalyticsWidget):
    """Widget për productivity metrics"""
    
    def get_data(self):
        start_date, end_date = self.date_range
        
        # Get time entries based on user role
        if self.user.role == 'admin':
            time_entries = TimeEntry.objects.all()
            users_scope = User.objects.filter(role__in=['lawyer', 'paralegal'])
        elif self.user.role in ['lawyer', 'paralegal']:
            time_entries = TimeEntry.objects.filter(user=self.user)
            users_scope = User.objects.filter(id=self.user.id)
        else:  # client
            try:
                client = Client.objects.get(email=self.user.email)
                time_entries = TimeEntry.objects.filter(case__client=client)
                users_scope = User.objects.filter(assigned_cases__client=client).distinct()
            except Client.DoesNotExist:
                time_entries = TimeEntry.objects.none()
                users_scope = User.objects.none()
        
        # Filter by date range
        time_entries = time_entries.filter(created_at__range=[start_date, end_date])
        
        # Calculate productivity metrics
        total_hours = time_entries.aggregate(
            total=Sum('minutes')
        )['total'] or 0
        total_hours = total_hours / 60  # Convert to hours
        
        avg_hours_per_case = 0
        if time_entries.exists():
            unique_cases = time_entries.values_list('case', flat=True).distinct().count()
            avg_hours_per_case = total_hours / unique_cases if unique_cases > 0 else 0
        
        # Daily hours trends
        daily_hours = []
        current_date = start_date
        while current_date <= end_date:
            day_hours = time_entries.filter(
                created_at__date=current_date
            ).aggregate(total=Sum('minutes'))['total'] or 0
            
            daily_hours.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'hours': day_hours / 60
            })
            current_date += timedelta(days=1)
        
        # User productivity comparison (for admin)
        user_productivity = []
        if self.user.role == 'admin':
            for user in users_scope:
                user_hours = time_entries.filter(user=user).aggregate(
                    total=Sum('minutes')
                )['total'] or 0
                
                user_cases = time_entries.filter(user=user).values_list(
                    'case', flat=True
                ).distinct().count()
                
                user_productivity.append({
                    'user': user.get_full_name() or user.username,
                    'total_hours': user_hours / 60,
                    'cases_worked': user_cases,
                    'avg_hours_per_case': (user_hours / 60 / user_cases) if user_cases > 0 else 0
                })
        
        return {
            'total_hours': round(total_hours, 1),
            'avg_hours_per_case': round(avg_hours_per_case, 1),
            'billable_hours': round(total_hours * 0.8, 1),  # Assuming 80% billable rate
            'daily_trends': daily_hours[-14:],  # Last 14 days
            'user_productivity': sorted(user_productivity, key=lambda x: x['total_hours'], reverse=True)[:10]
        }


class DocumentAnalyticsWidget(AnalyticsWidget):
    """Widget për document analytics"""
    
    def get_data(self):
        start_date, end_date = self.date_range
        
        # Get documents based on user role
        documents = self.filter_by_user_role(
            CaseDocument.objects.all(), 
            model_field='case__assigned_to'
        )
        
        # Filter by date range
        documents = documents.filter(created_at__range=[start_date, end_date])
        
        # Document type distribution
        doc_types = documents.values('doc_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Document upload trends
        daily_uploads = []
        current_date = start_date
        while current_date <= end_date:
            day_count = documents.filter(created_at__date=current_date).count()
            daily_uploads.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'count': day_count
            })
            current_date += timedelta(days=1)
        
        # Top uploaders (for admin)
        top_uploaders = []
        if self.user.role == 'admin':
            top_uploaders = documents.values(
                'uploaded_by__username',
                'uploaded_by__first_name',
                'uploaded_by__last_name'
            ).annotate(
                upload_count=Count('id')
            ).order_by('-upload_count')[:5]
        
        # Document size analytics
        total_documents = documents.count()
        
        return {
            'total_documents': total_documents,
            'doc_type_distribution': list(doc_types),
            'daily_upload_trends': daily_uploads[-14:],  # Last 14 days
            'top_uploaders': list(top_uploaders),
            'avg_documents_per_case': round(total_documents / max(Case.objects.count(), 1), 1)
        }


class ClientSatisfactionWidget(AnalyticsWidget):
    """Widget për client satisfaction metrics (placeholder for future rating system)"""
    
    def get_data(self):
        # This is a placeholder for future client satisfaction features
        # For now, we'll use case completion rates as a proxy
        
        cases = self.filter_by_user_role(Case.objects.all())
        
        total_cases = cases.count()
        completed_cases = cases.filter(status='closed').count()
        satisfaction_proxy = (completed_cases / total_cases * 100) if total_cases > 0 else 0
        
        # Simulated satisfaction data (replace with real data when rating system is implemented)
        satisfaction_trends = []
        for i in range(6):
            month_start = timezone.now().date().replace(day=1) - timedelta(days=30*i)
            satisfaction_trends.append({
                'month': month_start.strftime('%b %Y'),
                'score': satisfaction_proxy + (i * 2),  # Simulated trending
                'responses': max(total_cases - i * 2, 0)
            })
        
        return {
            'overall_satisfaction': round(satisfaction_proxy, 1),
            'total_responses': total_cases,
            'satisfaction_trends': list(reversed(satisfaction_trends)),
            'needs_improvement': satisfaction_proxy < 80,
            'feedback_summary': {
                'excellent': round(satisfaction_proxy * 0.4, 1),
                'good': round(satisfaction_proxy * 0.3, 1),
                'average': round(satisfaction_proxy * 0.2, 1),
                'poor': round(satisfaction_proxy * 0.1, 1)
            }
        }


# Widget Registry
WIDGET_REGISTRY = {
    'case_performance': CasePerformanceWidget,
    'financial_performance': FinancialPerformanceWidget,
    'productivity': ProductivityWidget,
    'document_analytics': DocumentAnalyticsWidget,
    'client_satisfaction': ClientSatisfactionWidget,
}


def get_widget_data(widget_name, user, date_range=None):
    """Get data from a specific widget"""
    if widget_name not in WIDGET_REGISTRY:
        raise ValueError(f"Widget '{widget_name}' not found")
    
    widget_class = WIDGET_REGISTRY[widget_name]
    widget = widget_class(user, date_range)
    return widget.get_data()


def get_all_widgets_data(user, date_range=None):
    """Get data from all widgets for a user"""
    data = {}
    for widget_name in WIDGET_REGISTRY:
        try:
            data[widget_name] = get_widget_data(widget_name, user, date_range)
        except Exception as e:
            # Log error and continue with other widgets
            data[widget_name] = {'error': str(e)}
    
    return data
