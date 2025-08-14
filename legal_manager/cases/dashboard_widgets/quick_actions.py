# dashboard_widgets/quick_actions.py - Quick Actions Panel
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, timedelta

from ..models import Case, Client, CaseDocument, CaseEvent, User


class QuickActionsWidget:
    """Quick actions panel për dashboard"""
    
    def __init__(self, user):
        self.user = user
    
    def get_actions(self):
        """Get available quick actions based on user role"""
        actions = []
        
        if self.user.role in ['admin', 'lawyer']:
            actions.extend(self.get_lawyer_actions())
        elif self.user.role == 'paralegal':
            actions.extend(self.get_paralegal_actions())
        elif self.user.role == 'client':
            actions.extend(self.get_client_actions())
        
        # Common actions for all users
        actions.extend(self.get_common_actions())
        
        return actions
    
    def get_lawyer_actions(self):
        """Actions available to lawyers and admins"""
        return [
            {
                'id': 'create_case',
                'title': 'Krijo Rast të Ri',
                'description': 'Krijo një rast të ri për një klient',
                'icon': 'bi-folder-plus',
                'color': 'primary',
                'url': reverse('case_create'),
                'shortcut': 'Ctrl+N',
                'category': 'case_management'
            },
            {
                'id': 'add_client',
                'title': 'Shto Klient',
                'description': 'Regjistro një klient të ri në sistem',
                'icon': 'bi-person-plus',
                'color': 'success',
                'url': reverse('client_create'),
                'shortcut': 'Ctrl+Shift+C',
                'category': 'client_management'
            },
            {
                'id': 'schedule_meeting',
                'title': 'Planifiko Takimi',
                'description': 'Krijo një takim ose event të ri',
                'icon': 'bi-calendar-plus',
                'color': 'info',
                'url': reverse('event_create'),
                'shortcut': 'Ctrl+E',
                'category': 'calendar'
            },
            {
                'id': 'upload_document',
                'title': 'Ngarko Dokument',
                'description': 'Ngarko një dokument të ri',
                'icon': 'bi-cloud-upload',
                'color': 'warning',
                'url': reverse('document_upload'),
                'shortcut': 'Ctrl+U',
                'category': 'documents'
            },
            {
                'id': 'generate_report',
                'title': 'Gjenero Raport',
                'description': 'Krijo raporte për rastet dhe performance',
                'icon': 'bi-graph-up',
                'color': 'secondary',
                'url': '#',
                'modal': 'reportModal',
                'category': 'reporting'
            }
        ]
    
    def get_paralegal_actions(self):
        """Actions available to paralegals"""
        return [
            {
                'id': 'upload_document',
                'title': 'Ngarko Dokument',
                'description': 'Ngarko një dokument të ri',
                'icon': 'bi-cloud-upload',
                'color': 'primary',
                'url': reverse('document_upload'),
                'shortcut': 'Ctrl+U',
                'category': 'documents'
            },
            {
                'id': 'schedule_meeting',
                'title': 'Planifiko Takimi',
                'description': 'Krijo një takim ose event të ri',
                'icon': 'bi-calendar-plus',
                'color': 'info',
                'url': reverse('event_create'),
                'shortcut': 'Ctrl+E',
                'category': 'calendar'
            },
            {
                'id': 'time_entry',
                'title': 'Regjistro Kohë',
                'description': 'Shto entry për kohën e punuar',
                'icon': 'bi-clock',
                'color': 'success',
                'url': '#',
                'modal': 'timeEntryModal',
                'category': 'time_tracking'
            }
        ]
    
    def get_client_actions(self):
        """Actions available to clients"""
        return [
            {
                'id': 'view_cases',
                'title': 'Rastet e Mia',
                'description': 'Shiko rastet dhe ecurinë e tyre',
                'icon': 'bi-folder',
                'color': 'primary',
                'url': reverse('case_list'),
                'category': 'case_management'
            },
            {
                'id': 'upload_document',
                'title': 'Ngarko Dokument',
                'description': 'Dërgo dokumente për rastet tuaja',
                'icon': 'bi-cloud-upload',
                'color': 'success',
                'url': reverse('document_upload'),
                'category': 'documents'
            },
            {
                'id': 'view_invoices',
                'title': 'Faturat e Mia',
                'description': 'Shiko faturat dhe pagesat',
                'icon': 'bi-receipt',
                'color': 'warning',
                'url': '#',
                'modal': 'invoicesModal',
                'category': 'billing'
            }
        ]
    
    def get_common_actions(self):
        """Actions available to all users"""
        return [
            {
                'id': 'profile_settings',
                'title': 'Cilësimet e Profilit',
                'description': 'Përditëso informacionet personale',
                'icon': 'bi-person-gear',
                'color': 'secondary',
                'url': reverse('profile_update'),
                'category': 'profile'
            },
            {
                'id': 'search',
                'title': 'Kërkim i Shpejtë',
                'description': 'Kërko raste, klientë ose dokumente',
                'icon': 'bi-search',
                'color': 'dark',
                'url': '#',
                'modal': 'searchModal',
                'shortcut': 'Ctrl+K',
                'category': 'search'
            }
        ]
    
    def get_recent_suggestions(self):
        """Get suggestions based on recent activity"""
        suggestions = []
        
        if self.user.role in ['admin', 'lawyer', 'paralegal']:
            # Suggest creating events for cases without recent activity
            inactive_cases = Case.objects.filter(
                assigned_to=self.user,
                status__in=['open', 'in_court']
            ).exclude(
                events__created_at__gte=timezone.now() - timedelta(days=7)
            )[:3]
            
            for case in inactive_cases:
                suggestions.append({
                    'id': f'schedule_case_{case.id}',
                    'title': f'Planifiko për: {case.title[:30]}...',
                    'description': 'Nuk ka aktivitet për më shumë se 7 ditë',
                    'icon': 'bi-calendar-event',
                    'color': 'warning',
                    'url': f"{reverse('case_event_create', kwargs={'case_pk': case.id})}",
                    'priority': 'high'
                })
            
            # Suggest following up on overdue deadlines
            overdue_events = CaseEvent.objects.filter(
                case__assigned_to=self.user,
                is_deadline=True,
                starts_at__lt=timezone.now()
            )[:2]
            
            for event in overdue_events:
                suggestions.append({
                    'id': f'followup_deadline_{event.id}',
                    'title': f'Follow-up: {event.title[:30]}...',
                    'description': f'Deadline kaloi më {event.starts_at.strftime("%d.%m.%Y")}',
                    'icon': 'bi-exclamation-triangle',
                    'color': 'danger',
                    'url': f"{reverse('event_detail', kwargs={'pk': event.id})}",
                    'priority': 'urgent'
                })
        
        return suggestions
    
    def get_quick_stats(self):
        """Get quick stats for the action panel"""
        stats = {}
        
        if self.user.role == 'admin':
            stats = {
                'total_cases': Case.objects.count(),
                'active_cases': Case.objects.exclude(status='closed').count(),
                'total_clients': Client.objects.count(),
                'pending_deadlines': CaseEvent.objects.filter(
                    is_deadline=True,
                    starts_at__gte=timezone.now(),
                    starts_at__lte=timezone.now() + timedelta(days=7)
                ).count()
            }
        elif self.user.role in ['lawyer', 'paralegal']:
            my_cases = Case.objects.filter(assigned_to=self.user)
            stats = {
                'my_cases': my_cases.count(),
                'active_cases': my_cases.exclude(status='closed').count(),
                'my_deadlines': CaseEvent.objects.filter(
                    case__assigned_to=self.user,
                    is_deadline=True,
                    starts_at__gte=timezone.now(),
                    starts_at__lte=timezone.now() + timedelta(days=7)
                ).count(),
                'documents_uploaded': CaseDocument.objects.filter(
                    uploaded_by=self.user,
                    created_at__gte=timezone.now() - timedelta(days=30)
                ).count()
            }
        else:  # client
            try:
                client = Client.objects.get(email=self.user.email)
                my_cases = Case.objects.filter(client=client)
                stats = {
                    'my_cases': my_cases.count(),
                    'active_cases': my_cases.exclude(status='closed').count(),
                    'upcoming_events': CaseEvent.objects.filter(
                        case__client=client,
                        starts_at__gte=timezone.now(),
                        starts_at__lte=timezone.now() + timedelta(days=7)
                    ).count()
                }
            except Client.DoesNotExist:
                stats = {'my_cases': 0, 'active_cases': 0, 'upcoming_events': 0}
        
        return stats
    
    def get_keyboard_shortcuts(self):
        """Get keyboard shortcuts for quick actions"""
        shortcuts = [
            {'key': 'Ctrl+N', 'action': 'Krijo Rast të Ri', 'available_for': ['admin', 'lawyer']},
            {'key': 'Ctrl+Shift+C', 'action': 'Shto Klient', 'available_for': ['admin', 'lawyer']},
            {'key': 'Ctrl+E', 'action': 'Krijo Event', 'available_for': ['admin', 'lawyer', 'paralegal']},
            {'key': 'Ctrl+U', 'action': 'Ngarko Dokument', 'available_for': ['admin', 'lawyer', 'paralegal', 'client']},
            {'key': 'Ctrl+K', 'action': 'Kërkim i Shpejtë', 'available_for': ['admin', 'lawyer', 'paralegal', 'client']},
            {'key': 'Ctrl+/', 'action': 'Shfaq Shortcuts', 'available_for': ['admin', 'lawyer', 'paralegal', 'client']},
        ]
        
        # Filter shortcuts based on user role
        return [s for s in shortcuts if self.user.role in s['available_for']]


class NotificationWidget:
    """Notification widget për real-time alerts"""
    
    def __init__(self, user):
        self.user = user
    
    def get_notifications(self):
        """Get unread notifications for user"""
        notifications = []
        
        # Upcoming deadlines (next 3 days)
        upcoming_deadlines = self.get_upcoming_deadlines()
        for deadline in upcoming_deadlines:
            notifications.append({
                'id': f'deadline_{deadline.id}',
                'type': 'deadline',
                'title': 'Deadline i Afërt',
                'message': f'{deadline.title} - {deadline.starts_at.strftime("%d.%m.%Y")}',
                'url': reverse('event_detail', kwargs={'pk': deadline.id}),
                'priority': 'high' if deadline.starts_at.date() <= timezone.now().date() + timedelta(days=1) else 'medium',
                'created_at': deadline.created_at,
                'icon': 'bi-exclamation-triangle'
            })
        
        # Overdue items
        overdue_deadlines = self.get_overdue_deadlines()
        for deadline in overdue_deadlines:
            notifications.append({
                'id': f'overdue_{deadline.id}',
                'type': 'overdue',
                'title': 'Deadline i Kaluar',
                'message': f'{deadline.title} - kaloi më {deadline.starts_at.strftime("%d.%m.%Y")}',
                'url': reverse('event_detail', kwargs={'pk': deadline.id}),
                'priority': 'urgent',
                'created_at': deadline.created_at,
                'icon': 'bi-exclamation-circle'
            })
        
        # New documents (for relevant users)
        if self.user.role in ['admin', 'lawyer', 'paralegal']:
            recent_docs = self.get_recent_documents()
            for doc in recent_docs:
                notifications.append({
                    'id': f'document_{doc.id}',
                    'type': 'document',
                    'title': 'Dokument i Ri',
                    'message': f'{doc.title} - {doc.case.title}',
                    'url': reverse('document_detail', kwargs={'pk': doc.id}),
                    'priority': 'low',
                    'created_at': doc.created_at,
                    'icon': 'bi-file-earmark-plus'
                })
        
        # Sort by priority and date
        priority_order = {'urgent': 0, 'high': 1, 'medium': 2, 'low': 3}
        notifications.sort(key=lambda x: (priority_order[x['priority']], x['created_at']), reverse=True)
        
        return notifications[:10]  # Return top 10 notifications
    
    def get_upcoming_deadlines(self):
        """Get upcoming deadlines for user"""
        start_date = timezone.now().date()
        end_date = start_date + timedelta(days=3)
        
        if self.user.role == 'admin':
            events = CaseEvent.objects.all()
        elif self.user.role in ['lawyer', 'paralegal']:
            events = CaseEvent.objects.filter(case__assigned_to=self.user)
        else:  # client
            try:
                client = Client.objects.get(email=self.user.email)
                events = CaseEvent.objects.filter(case__client=client)
            except Client.DoesNotExist:
                events = CaseEvent.objects.none()
        
        return events.filter(
            is_deadline=True,
            starts_at__date__range=[start_date, end_date]
        ).select_related('case')
    
    def get_overdue_deadlines(self):
        """Get overdue deadlines"""
        today = timezone.now().date()
        
        if self.user.role == 'admin':
            events = CaseEvent.objects.all()
        elif self.user.role in ['lawyer', 'paralegal']:
            events = CaseEvent.objects.filter(case__assigned_to=self.user)
        else:  # client
            try:
                client = Client.objects.get(email=self.user.email)
                events = CaseEvent.objects.filter(case__client=client)
            except Client.DoesNotExist:
                events = CaseEvent.objects.none()
        
        return events.filter(
            is_deadline=True,
            starts_at__date__lt=today
        ).select_related('case')[:5]
    
    def get_recent_documents(self):
        """Get recently uploaded documents"""
        week_ago = timezone.now() - timedelta(days=7)
        
        if self.user.role == 'admin':
            docs = CaseDocument.objects.all()
        elif self.user.role in ['lawyer', 'paralegal']:
            docs = CaseDocument.objects.filter(case__assigned_to=self.user)
        else:  # client
            try:
                client = Client.objects.get(email=self.user.email)
                docs = CaseDocument.objects.filter(case__client=client)
            except Client.DoesNotExist:
                docs = CaseDocument.objects.none()
        
        return docs.filter(
            created_at__gte=week_ago
        ).select_related('case', 'uploaded_by').order_by('-created_at')[:5]
