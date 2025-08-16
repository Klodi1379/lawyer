# analytics_service.py - Moduli i Analytics për sistemin ligjor

from django.db.models import Count, Sum, Avg, Q, F, Value, DecimalField
from django.db.models.functions import TruncMonth, TruncWeek, TruncDay, Coalesce
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Case, CaseEvent, TimeEntry, Invoice, Client, User, CaseDocument
import json
from decimal import Decimal

class LegalAnalytics:
    """
    Klasa kryesore për analizat dhe raportet e sistemit ligjor
    """
    
    def __init__(self, user=None, date_from=None, date_to=None):
        self.user = user
        self.date_from = date_from or timezone.now() - timedelta(days=365)
        self.date_to = date_to or timezone.now()
    
    def get_case_statistics(self):
        """Statistika të përgjithshme të rasteve"""
        queryset = Case.objects.filter(
            created_at__range=[self.date_from, self.date_to]
        )
        
        if self.user and self.user.role != 'admin':
            queryset = queryset.filter(assigned_to=self.user)
        
        # Statistika bazë
        total_cases = queryset.count()
        open_cases = queryset.filter(status='open').count()
        closed_cases = queryset.filter(status='closed').count()
        in_court_cases = queryset.filter(status='in_court').count()
        appeal_cases = queryset.filter(status='appeal').count()
        
        # Raste sipas tipit
        cases_by_type = dict(
            queryset.values('case_type')
                   .annotate(count=Count('id'))
                   .values_list('case_type', 'count')
        )
        
        # Raste sipas muajit
        cases_by_month = self._get_cases_by_month(queryset)
        
        # Kohëzgjatja mesatare
        avg_duration = self._calculate_avg_duration(queryset)
        
        # Përqindja e suksesit
        success_rate = self._calculate_success_rate(queryset)
        
        return {
            'total_cases': total_cases,
            'open_cases': open_cases,
            'closed_cases': closed_cases,
            'in_court_cases': in_court_cases,
            'appeal_cases': appeal_cases,
            'cases_by_type': cases_by_type,
            'cases_by_month': cases_by_month,
            'avg_case_duration': avg_duration,
            'success_rate': success_rate,
            'pending_cases': open_cases + in_court_cases + appeal_cases,
            'completion_rate': round((closed_cases / total_cases * 100) if total_cases > 0 else 0, 2)
        }
    
    def get_financial_overview(self):
        """Përmbledhje financiare"""
        invoices = Invoice.objects.filter(
            issued_at__range=[self.date_from, self.date_to]
        )
        
        time_entries = TimeEntry.objects.filter(
            created_at__range=[self.date_from, self.date_to]
        )
        
        if self.user and self.user.role not in ['admin', 'lawyer']:
            invoices = invoices.filter(case__assigned_to=self.user)
            time_entries = time_entries.filter(user=self.user)
        
        # Të dhëna financiare bazë
        total_revenue = invoices.aggregate(
            total=Coalesce(Sum('total_amount'), Value(0, output_field=DecimalField()))
        )['total']
        
        paid_revenue = invoices.filter(paid=True).aggregate(
            total=Coalesce(Sum('total_amount'), Value(0, output_field=DecimalField()))
        )['total']
        
        pending_revenue = total_revenue - paid_revenue
        
        # Orët
        total_minutes = time_entries.aggregate(
            total=Coalesce(Sum('minutes'), Value(0))
        )['total']
        total_hours = round(total_minutes / 60, 1)
        
        # Tarifa mesatare për orë
        avg_hourly_rate = float(paid_revenue / Decimal(str(total_hours))) if total_hours > 0 else 0
        
        # Të ardhurat sipas muajit
        revenue_by_month = self._get_revenue_by_month(invoices)
        
        # Top klientët
        top_clients = self._get_top_clients(invoices)
        
        # Fatura të papaguara
        overdue_invoices = invoices.filter(
            paid=False,
            issued_at__lt=timezone.now() - timedelta(days=30)
        ).count()
        
        return {
            'total_revenue': float(total_revenue),
            'paid_revenue': float(paid_revenue),
            'pending_revenue': float(pending_revenue),
            'total_hours': total_hours,
            'avg_hourly_rate': round(avg_hourly_rate, 2),
            'revenue_by_month': revenue_by_month,
            'top_clients': top_clients,
            'total_invoices': invoices.count(),
            'paid_invoices': invoices.filter(paid=True).count(),
            'overdue_invoices': overdue_invoices,
            'collection_rate': round((paid_revenue / total_revenue * 100) if total_revenue > 0 else 0, 2)
        }
    
    def get_productivity_metrics(self):
        """Metrika produktiviteti"""
        if self.user and self.user.role not in ['admin']:
            time_entries = TimeEntry.objects.filter(
                user=self.user,
                created_at__range=[self.date_from, self.date_to]
            )
            cases = Case.objects.filter(
                assigned_to=self.user,
                created_at__range=[self.date_from, self.date_to]
            )
        else:
            time_entries = TimeEntry.objects.filter(
                created_at__range=[self.date_from, self.date_to]
            )
            cases = Case.objects.filter(
                created_at__range=[self.date_from, self.date_to]
            )
        
        total_minutes = time_entries.aggregate(
            total=Coalesce(Sum('minutes'), Value(0))
        )['total']
        
        hours_logged = round(total_minutes / 60, 1)
        cases_count = cases.count()
        avg_hours_per_case = round(hours_logged / cases_count, 1) if cases_count > 0 else 0
        
        # Orët sipas javëve
        weekly_hours = self._get_weekly_hours(time_entries)
        
        # Aktiviteti ditor
        daily_activity = self._get_daily_activity(time_entries)
        
        # Eficienca (raste të mbyllura vs të hapura)
        closed_cases = cases.filter(status='closed').count()
        efficiency_rate = round((closed_cases / cases_count * 100) if cases_count > 0 else 0, 2)
        
        return {
            'hours_logged': hours_logged,
            'cases_handled': cases_count,
            'avg_hours_per_case': avg_hours_per_case,
            'weekly_hours': weekly_hours,
            'daily_activity': daily_activity,
            'billable_rate': 85.0,  # Placeholder - duhet integruar me sistemin e faturimit
            'efficiency_rate': efficiency_rate,
            'avg_daily_hours': round(hours_logged / 30, 1) if hours_logged > 0 else 0
        }
    
    def get_deadline_overview(self):
        """Përmbledhje e afateve"""
        upcoming_events = CaseEvent.objects.filter(
            starts_at__gte=timezone.now(),
            starts_at__lte=timezone.now() + timedelta(days=30),
            is_deadline=True
        ).select_related('case')
        
        overdue_events = CaseEvent.objects.filter(
            starts_at__lt=timezone.now(),
            is_deadline=True
        ).select_related('case')
        
        if self.user and self.user.role not in ['admin']:
            upcoming_events = upcoming_events.filter(case__assigned_to=self.user)
            overdue_events = overdue_events.filter(case__assigned_to=self.user)
        
        # Statistika
        upcoming_count = upcoming_events.count()
        overdue_count = overdue_events.count()
        next_7_days = upcoming_events.filter(
            starts_at__lte=timezone.now() + timedelta(days=7)
        ).count()
        
        # Lista e afateve
        deadline_list = []
        for event in upcoming_events.order_by('starts_at')[:10]:
            days_remaining = (event.starts_at - timezone.now()).days
            deadline_list.append({
                'id': event.id,
                'title': event.title,
                'case': event.case.title,
                'case_uid': event.case.uid,
                'date': event.starts_at.isoformat(),
                'days_remaining': days_remaining,
                'priority': event.priority if hasattr(event, 'priority') else 'medium'
            })
        
        return {
            'upcoming_deadlines': upcoming_count,
            'overdue_deadlines': overdue_count,
            'next_7_days': next_7_days,
            'deadline_list': deadline_list,
            'deadline_compliance_rate': round(
                (1 - (overdue_count / (upcoming_count + overdue_count))) * 100 
                if (upcoming_count + overdue_count) > 0 else 100, 2
            )
        }
    
    def get_document_metrics(self):
        """Metrika për dokumentet"""
        documents = CaseDocument.objects.filter(
            created_at__range=[self.date_from, self.date_to]
        )
        
        if self.user and self.user.role not in ['admin']:
            documents = documents.filter(case__assigned_to=self.user)
        
        # Dokumentet sipas tipit
        docs_by_type = dict(
            documents.values('doc_type')
                    .annotate(count=Count('id'))
                    .values_list('doc_type', 'count')
        )
        
        # Dokumentet sipas statusit
        docs_by_status = dict(
            documents.values('status')
                    .annotate(count=Count('id'))
                    .values_list('status', 'count')
        )
        
        # Konvertojmë recent_uploads në format JSON-serializable
        recent_uploads_list = []
        for doc in documents.order_by('-created_at')[:5]:
            recent_uploads_list.append({
                'id': doc.id,
                'title': doc.title,
                'created_at': doc.created_at.isoformat(),
                'case__title': doc.case.title
            })

        return {
            'total_documents': documents.count(),
            'docs_by_type': docs_by_type,
            'docs_by_status': docs_by_status,
            'recent_uploads': recent_uploads_list
        }
    
    def get_team_performance(self):
        """Performance i ekipit (vetëm për admin)"""
        if self.user and self.user.role != 'admin':
            return {}
        
        lawyers = User.objects.filter(role='lawyer')
        team_stats = []
        
        for lawyer in lawyers:
            lawyer_cases = Case.objects.filter(
                assigned_to=lawyer,
                created_at__range=[self.date_from, self.date_to]
            )
            
            lawyer_time = TimeEntry.objects.filter(
                user=lawyer,
                created_at__range=[self.date_from, self.date_to]
            ).aggregate(total=Coalesce(Sum('minutes'), Value(0)))['total']
            
            team_stats.append({
                'lawyer': lawyer.get_full_name() or lawyer.username,
                'cases_assigned': lawyer_cases.count(),
                'cases_closed': lawyer_cases.filter(status='closed').count(),
                'hours_logged': round(lawyer_time / 60, 1),
                'efficiency': round(
                    (lawyer_cases.filter(status='closed').count() / lawyer_cases.count() * 100)
                    if lawyer_cases.count() > 0 else 0, 2
                )
            })
        
        return {
            'team_stats': sorted(team_stats, key=lambda x: x['efficiency'], reverse=True),
            'total_team_hours': sum([stat['hours_logged'] for stat in team_stats]),
            'avg_team_efficiency': round(
                sum([stat['efficiency'] for stat in team_stats]) / len(team_stats)
                if team_stats else 0, 2
            )
        }
    
    # Helper methods
    def _get_cases_by_month(self, queryset):
        """Helper për raste sipas muajit"""
        from django.db.models.functions import TruncMonth
        results = queryset.annotate(month=TruncMonth('created_at')).values('month').annotate(count=Count('id')).order_by('month')
        return {result['month'].strftime('%Y-%m') if result['month'] else 'Unknown': result['count'] for result in results}
    
    def _get_revenue_by_month(self, queryset):
        """Helper për të ardhurat sipas muajit"""
        from django.db.models.functions import TruncMonth
        results = queryset.filter(paid=True).annotate(month=TruncMonth('issued_at')).values('month').annotate(revenue=Sum('total_amount')).order_by('month')
        return {result['month'].strftime('%Y-%m') if result['month'] else 'Unknown': float(result['revenue']) for result in results}
    
    def _get_top_clients(self, invoices):
        """Top klientët sipas të ardhurave"""
        return list(
            invoices.filter(paid=True)
                   .values('issued_to__full_name')
                   .annotate(total=Sum('total_amount'))
                   .order_by('-total')[:5]
                   .values('issued_to__full_name', 'total')
        )
    
    def _calculate_avg_duration(self, queryset):
        """Kohëzgjatja mesatare e rasteve"""
        closed_cases = queryset.filter(status='closed')
        if not closed_cases.exists():
            return 0
        
        durations = []
        for case in closed_cases:
            if case.updated_at and case.created_at:
                duration = (case.updated_at - case.created_at).days
                durations.append(duration)
        
        return round(sum(durations) / len(durations), 1) if durations else 0
    
    def _calculate_success_rate(self, queryset):
        """Përmirëso këtë bazuar në kriteret tuaja të suksesit"""
        total = queryset.count()
        successful = queryset.filter(status='closed').count()  # Supozim: closed = successful
        return round((successful / total * 100) if total > 0 else 0, 2)
    
    def _get_weekly_hours(self, time_entries):
        """Orët sipas javëve"""
        from django.db.models.functions import TruncWeek
        results = time_entries.annotate(week=TruncWeek('created_at')).values('week').annotate(hours=Sum('minutes')).order_by('week')
        return {result['week'].strftime('%Y-W%U') if result['week'] else 'Unknown': result['hours'] for result in results}
    
    def _get_daily_activity(self, time_entries):
        """Aktiviteti ditor"""
        from django.db.models.functions import TruncDay
        results = time_entries.annotate(day=TruncDay('created_at')).values('day').annotate(hours=Sum('minutes')).order_by('day')
        return {result['day'].strftime('%Y-%m-%d') if result['day'] else 'Unknown': result['hours'] for result in results}


# Dashboard data aggregator
def get_dashboard_data(user):
    """
    Merr të gjitha të dhënat për dashboard-in
    """
    analytics = LegalAnalytics(user=user)
    
    # Quick stats për navbar
    quick_stats = {
        'total_active_cases': Case.objects.filter(status__in=['open', 'in_court']).count(),
        'pending_invoices': Invoice.objects.filter(paid=False).count(),
        'today_events': CaseEvent.objects.filter(
            starts_at__date=timezone.now().date()
        ).count(),
        'overdue_deadlines': CaseEvent.objects.filter(
            starts_at__lt=timezone.now(),
            is_deadline=True
        ).count()
    }
    
    return {
        'case_stats': analytics.get_case_statistics(),
        'financial_overview': analytics.get_financial_overview(),
        'productivity': analytics.get_productivity_metrics(),
        'deadlines': analytics.get_deadline_overview(),
        'documents': analytics.get_document_metrics(),
        'team_performance': analytics.get_team_performance(),
        'quick_stats': quick_stats,
    }


def get_analytics_charts_data(user, period='month'):
    """
    Merr të dhënat për charts në analytics dashboard
    """
    analytics = LegalAnalytics(user=user)
    
    # Konfiguro periudhën
    if period == 'week':
        date_from = timezone.now() - timedelta(weeks=12)
    elif period == 'year':
        date_from = timezone.now() - timedelta(days=365*2)
    else:  # month
        date_from = timezone.now() - timedelta(days=365)
    
    analytics.date_from = date_from
    
    case_stats = analytics.get_case_statistics()
    financial_stats = analytics.get_financial_overview()
    productivity_stats = analytics.get_productivity_metrics()
    
    return {
        'period': period,
        'case_trends': case_stats['cases_by_month'],
        'revenue_trends': financial_stats['revenue_by_month'],
        'productivity_trends': productivity_stats['weekly_hours'],
        'case_distribution': case_stats['cases_by_type'],
        'top_clients': financial_stats['top_clients'],
        'team_performance': analytics.get_team_performance()
    }
