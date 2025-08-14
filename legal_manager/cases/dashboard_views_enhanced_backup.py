# Enhanced Dashboard Views - Integration me widgets e reja
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta
import json

from .dashboard_views import DashboardView as BaseDashboardView
from .dashboard_widgets.analytics import get_all_widgets_data, get_widget_data
from .dashboard_widgets.calendar_widget import CalendarWidget, MiniCalendarWidget
from .dashboard_widgets.quick_actions import QuickActionsWidget, NotificationWidget


class EnhancedDashboardView(BaseDashboardView):
    """Enhanced dashboard me widgets të reja"""
    template_name = 'dashboard/enhanced_index.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get widget date range from request
        date_range = self.get_date_range_from_request()
        
        # Add analytics widgets data
        try:
            context['analytics_data'] = get_all_widgets_data(user, date_range)
        except Exception as e:
            context['analytics_data'] = {'error': str(e)}
        
        # Add calendar widget data
        calendar_widget = CalendarWidget(user)
        context['calendar_data'] = calendar_widget.get_calendar_summary()
        context['upcoming_events'] = calendar_widget.get_upcoming_events(7)
        
        # Add mini calendar
        mini_calendar = MiniCalendarWidget(user)
        context['mini_calendar'] = mini_calendar.get_month_data()
        
        # Add quick actions
        quick_actions = QuickActionsWidget(user)
        context['quick_actions'] = quick_actions.get_actions()
        context['quick_suggestions'] = quick_actions.get_recent_suggestions()
        context['quick_stats'] = quick_actions.get_quick_stats()
        context['keyboard_shortcuts'] = quick_actions.get_keyboard_shortcuts()
        
        # Add notifications
        notification_widget = NotificationWidget(user)
        context['notifications'] = notification_widget.get_notifications()
        
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
        # This will be implemented when we add user preferences
        return {
            'hidden_widgets': [],
            'widget_order': [
                'case_performance',
                'financial_performance', 
                'productivity',
                'document_analytics',
                'client_satisfaction'
            ],
            'dashboard_layout': 'default'  # default, compact, detailed
        }


@login_required
def dashboard_widget_api(request, widget_name):
    """API endpoint për individual widget data"""
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
        
        # Get widget data
        data = get_widget_data(widget_name, request.user, date_range)
        
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
    """API endpoint për calendar widget"""
    try:
        start_date_str = request.GET.get('start')
        end_date_str = request.GET.get('end')
        
        calendar_widget = CalendarWidget(request.user)
        
        if start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            events = calendar_widget.get_events_data(start_date, end_date)
        else:
            events = calendar_widget.get_events_data()
        
        return JsonResponse(events, safe=False)
        
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)


@login_required
def quick_actions_api(request):
    """API endpoint për quick actions"""
    try:
        quick_actions = QuickActionsWidget(request.user)
        
        data = {
            'actions': quick_actions.get_actions(),
            'suggestions': quick_actions.get_recent_suggestions(),
            'stats': quick_actions.get_quick_stats(),
            'shortcuts': quick_actions.get_keyboard_shortcuts()
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)


@login_required
def notifications_api(request):
    """API endpoint për notifications"""
    try:
        notification_widget = NotificationWidget(request.user)
        notifications = notification_widget.get_notifications()
        
        return JsonResponse({
            'notifications': notifications,
            'count': len(notifications),
            'unread_count': len([n for n in notifications if n.get('priority') in ['urgent', 'high']])
        })
        
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)


@login_required 
def mini_calendar_api(request):
    """API endpoint për mini calendar"""
    try:
        year = int(request.GET.get('year', timezone.now().year))
        month = int(request.GET.get('month', timezone.now().month))
        
        current_date = datetime(year, month, 1).date()
        mini_calendar = MiniCalendarWidget(request.user, current_date)
        
        data = mini_calendar.get_month_data()
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)


@login_required
def dashboard_export_api(request):
    """API endpoint për dashboard data export"""
    try:
        export_format = request.GET.get('format', 'json')  # json, csv, pdf
        
        if export_format not in ['json', 'csv', 'pdf']:
            return JsonResponse({
                'error': 'Invalid export format'
            }, status=400)
        
        # Get all dashboard data
        user = request.user
        
        # Get date range
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
        
        # Collect all data
        export_data = {
            'user': {
                'username': user.username,
                'role': user.role,
                'full_name': user.get_full_name()
            },
            'export_date': timezone.now().isoformat(),
            'date_range': {
                'start': date_range[0].isoformat() if date_range else None,
                'end': date_range[1].isoformat() if date_range else None
            },
            'analytics': get_all_widgets_data(user, date_range),
            'calendar_summary': CalendarWidget(user).get_calendar_summary(),
            'quick_stats': QuickActionsWidget(user).get_quick_stats()
        }
        
        if export_format == 'json':
            response = JsonResponse(export_data)
            response['Content-Disposition'] = f'attachment; filename="dashboard_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json"'
            return response
        
        # For CSV and PDF exports, we would implement those formats here
        # For now, return JSON with a note
        return JsonResponse({
            'error': f'{export_format.upper()} export not yet implemented',
            'data': export_data
        })
        
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)


@login_required
def dashboard_refresh_api(request):
    """API endpoint to refresh dashboard data"""
    try:
        # This endpoint can be called to refresh specific widgets
        widget_names = request.GET.getlist('widgets')  # List of widget names to refresh
        
        if not widget_names:
            # Refresh all widgets
            widget_names = ['case_performance', 'financial_performance', 'productivity', 'document_analytics', 'client_satisfaction']
        
        refreshed_data = {}
        
        for widget_name in widget_names:
            try:
                refreshed_data[widget_name] = get_widget_data(widget_name, request.user)
            except Exception as e:
                refreshed_data[widget_name] = {'error': str(e)}
        
        return JsonResponse({
            'success': True,
            'refreshed_widgets': widget_names,
            'data': refreshed_data,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
