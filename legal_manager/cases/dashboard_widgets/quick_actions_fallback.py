# dashboard_widgets/quick_actions_fallback.py - Simple fallback implementation
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, timedelta


class QuickActionsWidgetFallback:
    """Simple fallback implementation for quick actions"""
    
    def __init__(self, user):
        self.user = user
    
    def get_actions(self):
        """Get basic quick actions that work for all users"""
        actions = []
        
        try:
            # Basic actions available to all users
            if self.user.role in ['admin', 'lawyer']:
                actions.extend([
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
                        'category': 'client_management'
                    }
                ])
            
            # Actions for all roles
            actions.extend([
                {
                    'id': 'schedule_meeting',
                    'title': 'Planifiko Event',
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
                }
            ])
        except Exception as e:
            # If there are URL resolution errors, return empty list
            print(f"Error generating quick actions: {e}")
            actions = []
        
        return actions
    
    def get_recent_suggestions(self):
        """Get simple suggestions based on user activity"""
        suggestions = []
        
        try:
            if self.user.role in ['admin', 'lawyer']:
                suggestions.append({
                    'title': 'Krijo rastin e parë',
                    'description': 'Fillo duke krijuar rastin e parë për të testuar sistemin',
                    'icon': 'bi-folder-plus',
                    'color': 'primary',
                    'priority': 'high',
                    'url': reverse('case_create')
                })
            
            suggestions.append({
                'title': 'Shqyrto kalendarin',
                'description': 'Kontrollo calendar-in për event-et e ardhshme',
                'icon': 'bi-calendar-check',
                'color': 'info',
                'priority': 'medium',
                'url': reverse('event_calendar')
            })
        except Exception as e:
            print(f"Error generating suggestions: {e}")
        
        return suggestions
    
    def get_quick_stats(self):
        """Get basic stats"""
        from ..models import Case, Client, CaseEvent
        
        try:
            stats = {
                'total_cases': Case.objects.count(),
                'active_cases': Case.objects.filter(status__in=['open', 'in_court']).count(),
                'total_clients': Client.objects.count(),
                'pending_deadlines': CaseEvent.objects.filter(
                    is_deadline=True,
                    starts_at__gte=timezone.now()
                ).count()
            }
            
            # Filter by user if not admin
            if self.user.role != 'admin':
                stats.update({
                    'my_cases': Case.objects.filter(assigned_to=self.user).count(),
                    'my_deadlines': CaseEvent.objects.filter(
                        case__assigned_to=self.user,
                        is_deadline=True,
                        starts_at__gte=timezone.now()
                    ).count()
                })
        except Exception as e:
            print(f"Error getting stats: {e}")
            stats = {
                'total_cases': 0,
                'active_cases': 0,
                'total_clients': 0,
                'pending_deadlines': 0
            }
        
        return stats
    
    def get_keyboard_shortcuts(self):
        """Get keyboard shortcuts"""
        return [
            {'action': 'Create new case', 'key': 'Ctrl+N'},
            {'action': 'Create new event', 'key': 'Ctrl+E'},
            {'action': 'Upload document', 'key': 'Ctrl+U'},
            {'action': 'Global search', 'key': 'Ctrl+K'},
            {'action': 'Show shortcuts', 'key': 'Ctrl+/'}
        ]


class NotificationWidgetFallback:
    """Simple fallback for notifications"""
    
    def __init__(self, user):
        self.user = user
    
    def get_notifications(self):
        """Get basic notifications"""
        notifications = []
        
        try:
            from ..models import CaseEvent
            
            # Get upcoming deadlines as notifications
            upcoming_deadlines = CaseEvent.objects.filter(
                is_deadline=True,
                starts_at__gte=timezone.now(),
                starts_at__lte=timezone.now() + timedelta(days=7)
            )
            
            if self.user.role != 'admin':
                upcoming_deadlines = upcoming_deadlines.filter(case__assigned_to=self.user)
            
            for deadline in upcoming_deadlines[:5]:  # Limit to 5
                notifications.append({
                    'title': f'Deadline: {deadline.title}',
                    'message': f'Due {deadline.starts_at.strftime("%B %d, %Y")}',
                    'icon': 'bi-exclamation-triangle',
                    'priority': 'urgent',
                    'created_at': deadline.created_at,
                    'url': f'/events/{deadline.pk}/'
                })
        except Exception as e:
            print(f"Error getting notifications: {e}")
        
        return notifications
