# dashboard_widgets/calendar_widget.py - Interactive Calendar Widget
from django.utils import timezone
from datetime import datetime, timedelta
import json

from ..models import CaseEvent, Case


class CalendarWidget:
    """Interactive calendar widget për dashboard"""
    
    def __init__(self, user):
        self.user = user
    
    def get_events_data(self, start_date=None, end_date=None):
        """Get calendar events for the specified date range"""
        
        if not start_date:
            start_date = timezone.now().date()
        if not end_date:
            end_date = start_date + timedelta(days=30)
        
        # Filter events based on user role
        if self.user.role == 'admin':
            events = CaseEvent.objects.all()
        elif self.user.role in ['lawyer', 'paralegal']:
            events = CaseEvent.objects.filter(case__assigned_to=self.user)
        else:  # client
            try:
                from ..models import Client
                client = Client.objects.get(email=self.user.email)
                events = CaseEvent.objects.filter(case__client=client)
            except Client.DoesNotExist:
                events = CaseEvent.objects.none()
        
        # Filter by date range
        events = events.filter(
            starts_at__date__range=[start_date, end_date]
        ).select_related('case', 'created_by').order_by('starts_at')
        
        # Format events for FullCalendar
        calendar_events = []
        for event in events:
            calendar_events.append({
                'id': event.id,
                'title': event.title,
                'start': event.starts_at.isoformat(),
                'end': event.ends_at.isoformat() if event.ends_at else None,
                'allDay': event.is_all_day,
                'color': self.get_event_color(event),
                'className': self.get_event_class(event),
                'extendedProps': {
                    'caseTitle': event.case.title,
                    'caseId': event.case.id,
                    'isDeadline': event.is_deadline,
                    'description': event.description[:100] + '...' if len(event.description) > 100 else event.description,
                    'createdBy': event.created_by.get_full_name() if event.created_by else 'Unknown'
                }
            })
        
        return calendar_events
    
    def get_event_color(self, event):
        """Determine event color based on type and urgency"""
        if event.is_deadline:
            # Red for deadlines
            days_until = (event.starts_at.date() - timezone.now().date()).days
            if days_until <= 1:
                return '#dc3545'  # Urgent red
            elif days_until <= 7:
                return '#fd7e14'  # Warning orange
            else:
                return '#ffc107'  # Warning yellow
        else:
            # Different colors for different event types
            return '#0d6efd'  # Primary blue for regular events
    
    def get_event_class(self, event):
        """Get CSS class for event styling"""
        classes = ['fc-event']
        
        if event.is_deadline:
            classes.append('deadline-event')
        
        if event.is_all_day:
            classes.append('all-day-event')
        
        return ' '.join(classes)
    
    def get_upcoming_events(self, days=7):
        """Get upcoming events for the next N days"""
        start_date = timezone.now().date()
        end_date = start_date + timedelta(days=days)
        
        events = self.get_events_data(start_date, end_date)
        
        # Sort by date and return first 10
        return sorted(events, key=lambda x: x['start'])[:10]
    
    def get_overdue_deadlines(self):
        """Get overdue deadlines"""
        today = timezone.now().date()
        
        # Filter events based on user role
        if self.user.role == 'admin':
            events = CaseEvent.objects.all()
        elif self.user.role in ['lawyer', 'paralegal']:
            events = CaseEvent.objects.filter(case__assigned_to=self.user)
        else:  # client
            try:
                from ..models import Client
                client = Client.objects.get(email=self.user.email)
                events = CaseEvent.objects.filter(case__client=client)
            except Client.DoesNotExist:
                events = CaseEvent.objects.none()
        
        overdue = events.filter(
            is_deadline=True,
            starts_at__date__lt=today
        ).select_related('case', 'created_by').order_by('starts_at')
        
        return [{
            'id': event.id,
            'title': event.title,
            'case_title': event.case.title,
            'case_id': event.case.id,
            'deadline_date': event.starts_at.date(),
            'days_overdue': (today - event.starts_at.date()).days,
            'priority': 'high' if (today - event.starts_at.date()).days > 7 else 'medium'
        } for event in overdue]
    
    def get_calendar_summary(self):
        """Get calendar summary data for dashboard"""
        today = timezone.now().date()
        week_end = today + timedelta(days=7)
        month_end = today + timedelta(days=30)
        
        # Filter events based on user role
        if self.user.role == 'admin':
            events = CaseEvent.objects.all()
        elif self.user.role in ['lawyer', 'paralegal']:
            events = CaseEvent.objects.filter(case__assigned_to=self.user)
        else:  # client
            try:
                from ..models import Client
                client = Client.objects.get(email=self.user.email)
                events = CaseEvent.objects.filter(case__client=client)
            except Client.DoesNotExist:
                events = CaseEvent.objects.none()
        
        # Count events
        today_events = events.filter(starts_at__date=today).count()
        week_events = events.filter(starts_at__date__range=[today, week_end]).count()
        month_events = events.filter(starts_at__date__range=[today, month_end]).count()
        
        # Count deadlines
        week_deadlines = events.filter(
            is_deadline=True,
            starts_at__date__range=[today, week_end]
        ).count()
        
        overdue_count = len(self.get_overdue_deadlines())
        
        return {
            'today_events': today_events,
            'week_events': week_events,
            'month_events': month_events,
            'week_deadlines': week_deadlines,
            'overdue_deadlines': overdue_count,
            'upcoming_events': self.get_upcoming_events(3),  # Next 3 days
            'overdue_list': self.get_overdue_deadlines()[:5]  # Top 5 overdue
        }


class MiniCalendarWidget:
    """Mini calendar widget për sidebar navigation"""
    
    def __init__(self, user, current_date=None):
        self.user = user
        self.current_date = current_date or timezone.now().date()
    
    def get_month_data(self):
        """Get calendar data for current month"""
        # Get first day of month
        first_day = self.current_date.replace(day=1)
        
        # Get last day of month
        if first_day.month == 12:
            next_month = first_day.replace(year=first_day.year + 1, month=1)
        else:
            next_month = first_day.replace(month=first_day.month + 1)
        last_day = next_month - timedelta(days=1)
        
        # Get events for the month
        calendar_widget = CalendarWidget(self.user)
        events = calendar_widget.get_events_data(first_day, last_day)
        
        # Group events by date
        events_by_date = {}
        for event in events:
            date_key = event['start'][:10]  # Extract date part
            if date_key not in events_by_date:
                events_by_date[date_key] = []
            events_by_date[date_key].append(event)
        
        # Generate calendar grid
        calendar_weeks = []
        current_date = first_day
        
        # Start from Monday of the week containing first day
        days_from_monday = current_date.weekday()
        current_date = current_date - timedelta(days=days_from_monday)
        
        while current_date <= last_day + timedelta(days=6):
            week = []
            for _ in range(7):  # 7 days in a week
                date_str = current_date.strftime('%Y-%m-%d')
                day_events = events_by_date.get(date_str, [])
                
                week.append({
                    'date': current_date,
                    'date_str': date_str,
                    'day': current_date.day,
                    'is_current_month': current_date.month == self.current_date.month,
                    'is_today': current_date == timezone.now().date(),
                    'event_count': len(day_events),
                    'has_deadline': any(event['extendedProps']['isDeadline'] for event in day_events),
                    'events': day_events[:3]  # Show max 3 events
                })
                current_date += timedelta(days=1)
            
            calendar_weeks.append(week)
            
            # Break if we've passed the last day and completed the week
            if current_date > last_day and current_date.weekday() == 0:
                break
        
        return {
            'month_name': first_day.strftime('%B %Y'),
            'weeks': calendar_weeks,
            'prev_month': (first_day - timedelta(days=1)).strftime('%Y-%m'),
            'next_month': next_month.strftime('%Y-%m'),
            'total_events': len(events)
        }
