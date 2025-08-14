# Enhanced Dashboard Views - Integration me widgets e reja (me fallback support)
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta
import json

from .dashboard_views import DashboardView as BaseDashboardView

# Try to import main widgets, fallback to simple implementation if needed
try:
    from .dashboard_widgets.analytics import get_all_widgets_data, get_widget_data
    from .dashboard_widgets.calendar_widget import CalendarWidget, MiniCalendarWidget
    from .dashboard_widgets.quick_actions import QuickActionsWidget, NotificationWidget
except ImportError as e:
    print(f"Warning: Main widgets not available, using fallback: {e}")
    get_all_widgets_data = None
    get_widget_data = None
    CalendarWidget = None
    MiniCalendarWidget = None
    QuickActionsWidget = None
    NotificationWidget = None

# Import fallback widgets
from .dashboard_widgets.quick_actions_fallback import QuickActionsWidgetFallback, NotificationWidgetFallback


class EnhancedDashboardView(BaseDashboardView):
    """Enhanced dashboard me widgets të reja dhe fallback support"""
    template_name = 'dashboard/enhanced_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get widget date range from request
        date_range = self.get_date_range_from_request()
        
        # Add analytics widgets data with fallback
        try:
            if get_all_widgets_data:
                context['analytics_data'] = get_all_widgets_data(user, date_range)
            else:
                context['analytics_data'] = None
        except Exception as e:
            print(f"Error getting analytics data: {e}")
            context['analytics_data'] = {'error': str(e)}
        
        # Add calendar widget data with fallback
        try:
            if CalendarWidget and MiniCalendarWidget:
                calendar_widget = CalendarWidget(user)
                context['calendar_data'] = calendar_widget.get_calendar_summary()
                context['upcoming_events'] = calendar_widget.get_upcoming_events(7)
                
                mini_calendar = MiniCalendarWidget(user)
                context['mini_calendar'] = mini_calendar.get_month_data()
            else:
                context['calendar_data'] = None
                context['upcoming_events'] = []
                context['mini_calendar'] = None
        except Exception as e:
            print(f"Error getting calendar data: {e}")
            context['calendar_data'] = None
            context['upcoming_events'] = []
            context['mini_calendar'] = None
        
        # Add quick actions with fallback
        try:
            if QuickActionsWidget:
                quick_actions = QuickActionsWidget(user)
            else:
                quick_actions = QuickActionsWidgetFallback(user)
            
            context['quick_actions'] = quick_actions.get_actions()
            context['quick_suggestions'] = quick_actions.get_recent_suggestions()
            context['quick_stats'] = quick_actions.get_quick_stats()
            context['keyboard_shortcuts'] = quick_actions.get_keyboard_shortcuts()
        except Exception as e:
            print(f"Error getting quick actions: {e}")
            # Use simple fallback
            fallback_widget = QuickActionsWidgetFallback(user)
            context['quick_actions'] = fallback_widget.get_actions()
            context['quick_suggestions'] = fallback_widget.get_recent_suggestions()
            context['quick_stats'] = fallback_widget.get_quick_stats()
            context['keyboard_shortcuts'] = fallback_widget.get_keyboard_shortcuts()
        
        # Add notifications with fallback
        try:
            if NotificationWidget:
                notification_widget = NotificationWidget(user)
            else:
                notification_widget = NotificationWidgetFallback(user)
            
            context['notifications'] = notification_widget.get_notifications()
        except Exception as e:
            print(f"Error getting notifications: {e}")
            # Use simple fallback
            fallback_notification = NotificationWidgetFallback(user)
            context['notifications'] = fallback_notification.get_notifications()
        
        # Add widget preferences (if user has saved any)
        context['widget_preferences'] = self.get_user_widget_preferences()
        
        return context
    
    def get_date_range_from_request(self):
        """Get date range from request parameters"""
        start_date_str = self.request.GET.get('start_date')
        end_date_str = self.request.GET.get('end_date')
        
        if start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                return (start_date, end_date)
            except ValueError:
                pass
        
        # Default to last 30 days
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        return (start_date, end_date)
    
    def get_user_widget_preferences(self):
        """Get user's widget preferences (placeholder for future feature)"""
        return {
            'hidden_widgets': [],
            'widget_order': [
                'case_performance',
                'financial_performance', 
                'productivity',
                'document_analytics',
                'client_satisfaction'
            ],
            'dashboard_layout': 'default'
        }


@login_required
def dashboard_widget_api(request, widget_name):
    """API endpoint për individual widget data me fallback"""
    try:
        # Get date range from request
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        
        date_range = None
        if start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                date_range = (start_date, end_date)
            except ValueError:
                pass
        
        # Get widget data with fallback
        if get_widget_data:
            data = get_widget_data(widget_name, request.user, date_range)
        else:
            data = {'error': 'Widget system not available'}
        
        return JsonResponse({
            'success': True,
            'data': data,
            'widget': widget_name,
            'timestamp': timezone.now().isoformat()
        })
        
    except ValueError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)


@login_required
def calendar_widget_api(request):
    """API endpoint për calendar widget me fallback"""
    try:
        start_date_str = request.GET.get('start')
        end_date_str = request.GET.get('end')
        
        if CalendarWidget:
            calendar_widget = CalendarWidget(request.user)
            
            if start_date_str and end_date_str:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                events = calendar_widget.get_events_data(start_date, end_date)
            else:
                events = calendar_widget.get_events_data()
        else:
            # Simple fallback - return empty events
            events = []
        
        return JsonResponse(events, safe=False)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def quick_actions_api(request):
    """API endpoint për quick actions"""
    try:
        # Use fallback implementation always for reliability
        widget = QuickActionsWidgetFallback(request.user)
        actions = widget.get_actions()
        
        return JsonResponse({
            'success': True,
            'actions': actions
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def notifications_api(request):
    """API endpoint për notifications"""
    try:
        # Use fallback implementation for reliability
        widget = NotificationWidgetFallback(request.user)
        notifications = widget.get_notifications()
        
        return JsonResponse({
            'success': True,
            'notifications': notifications
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def mini_calendar_api(request):
    """API endpoint për mini calendar"""
    try:
        year = int(request.GET.get('year', timezone.now().year))
        month = int(request.GET.get('month', timezone.now().month))
        
        # Simple calendar data generation (fallback)
        calendar_data = {
            'year': year,
            'month': month,
            'month_name': datetime(year, month, 1).strftime('%B %Y'),
            'weeks': [],
            'total_events': 0
        }
        
        return JsonResponse(calendar_data)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def dashboard_export_api(request):
    """API endpoint për export dashboard data"""
    try:
        format_type = request.GET.get('format', 'json').lower()
        
        if format_type not in ['json', 'csv', 'pdf']:
            return JsonResponse({
                'success': False,
                'error': 'Invalid format'
            }, status=400)
        
        # Generate basic export data
        export_data = {
            'user': request.user.username,
            'exported_at': timezone.now().isoformat(),
            'format': format_type,
            'message': f'Dashboard export in {format_type} format would be generated here'
        }
        
        return JsonResponse({
            'success': True,
            'data': export_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def dashboard_refresh_api(request):
    """API endpoint për refresh dashboard"""
    try:
        # Simple refresh response
        return JsonResponse({
            'success': True,
            'data': {
                'refreshed_at': timezone.now().isoformat(),
                'message': 'Dashboard refreshed successfully'
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
