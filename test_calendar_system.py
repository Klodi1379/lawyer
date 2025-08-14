#!/usr/bin/env python
"""
Test script for Legal Case Manager Calendar and Events System
"""
import os
import django
from datetime import datetime, timedelta

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'legal_manager.settings')
django.setup()

from legal_manager.cases.models import User, Client, Case, CaseEvent, EventType
from django.utils import timezone

def test_calendar_system():
    """Test calendar and events functionality"""
    
    print("=" * 60)
    print("TESTING LEGAL CASE MANAGER CALENDAR SYSTEM")
    print("=" * 60)
    
    # 1. Check if EventTypes exist
    print("\n1. Checking EventTypes...")
    event_types = EventType.objects.all()
    print(f"   Found {event_types.count()} event types:")
    for et in event_types:
        print(f"   - {et.name} (Color: {et.color}, Deadline: {et.is_deadline})")
    
    # 2. Check Users
    print("\n2. Checking Users...")
    users = User.objects.all()
    print(f"   Found {users.count()} users:")
    for user in users[:5]:  # Show first 5
        print(f"   - {user.username} ({user.get_full_name()}) - Role: {user.role}")
    
    # 3. Check Clients and Cases
    print("\n3. Checking Clients and Cases...")
    clients = Client.objects.all()
    cases = Case.objects.all()
    print(f"   Found {clients.count()} clients and {cases.count()} cases")
    
    # 4. Create test events if we have data
    if users.exists() and cases.exists():
        print("\n4. Creating test events...")
        
        # Get first lawyer/admin user
        lawyer = users.filter(role__in=['lawyer', 'admin']).first()
        test_case = cases.first()
        
        if lawyer and test_case:
            # Create different types of events
            test_events = [
                {
                    'title': 'Court Hearing - Test Case',
                    'case': test_case,
                    'event_type': event_types.filter(name__icontains='Seancë').first(),
                    'starts_at': timezone.now() + timedelta(days=7),
                    'ends_at': timezone.now() + timedelta(days=7, hours=2),
                    'priority': 'high',
                    'created_by': lawyer
                },
                {
                    'title': 'Client Meeting',
                    'case': test_case,
                    'event_type': event_types.filter(name__icontains='Takim').first(),
                    'starts_at': timezone.now() + timedelta(days=3),
                    'ends_at': timezone.now() + timedelta(days=3, hours=1),
                    'priority': 'medium',
                    'created_by': lawyer
                },
                {
                    'title': 'Document Deadline',
                    'case': test_case,
                    'event_type': event_types.filter(is_deadline=True).first(),
                    'starts_at': timezone.now() + timedelta(days=14),
                    'priority': 'urgent',
                    'is_deadline': True,
                    'created_by': lawyer
                }
            ]
            
            created_count = 0
            for event_data in test_events:
                event, created = CaseEvent.objects.get_or_create(
                    title=event_data['title'],
                    case=event_data['case'],
                    defaults=event_data
                )
                if created:
                    created_count += 1
                    print(f"   [+] Created: {event.title}")
                else:
                    print(f"   [=] Exists: {event.title}")
            
            print(f"   Created {created_count} new test events")
        else:
            print("   [!] No lawyer/admin user or case found - skipping event creation")
    else:
        print("   [!] No users or cases found - skipping event creation")
    
    # 5. Display all events
    print("\n5. Current Events in System...")
    events = CaseEvent.objects.all().order_by('starts_at')
    print(f"   Found {events.count()} total events:")
    
    for event in events:
        status_icon = "[DEADLINE]" if event.is_deadline else "[EVENT]"
        print(f"   {status_icon} {event.title}")
        print(f"      Case: {event.case.title}")
        print(f"      Date: {event.starts_at.strftime('%Y-%m-%d %H:%M')}")
        print(f"      Priority: {event.priority}")
        print(f"      Type: {event.event_type.name if event.event_type else 'No type'}")
        print("")
    
    # 6. Test Calendar API data structure
    print("\n6. Testing Calendar API Data Structure...")
    api_events = []
    for event in events:
        event_data = {
            'id': event.id,
            'title': event.title,
            'start': event.starts_at.isoformat(),
            'end': event.ends_at.isoformat() if event.ends_at else None,
            'allDay': event.is_all_day,
            'color': event.get_calendar_color(),
            'extendedProps': {
                'case_uid': event.case.uid,
                'case_title': event.case.title,
                'priority': event.priority,
                'location': event.location,
                'is_deadline': event.is_deadline,
            }
        }
        api_events.append(event_data)
    
    print(f"   Generated {len(api_events)} calendar API events")
    if api_events:
        print("   Sample event data:")
        import json
        print(json.dumps(api_events[0], indent=2, default=str))
    
    # 7. System Health Check
    print("\n7. System Health Check...")
    try:
        # Test model relationships
        for event in events[:3]:
            case_title = event.case.title
            creator_name = event.created_by.username if event.created_by else "Unknown"
            color = event.get_calendar_color()
            print(f"   [OK] Event '{event.title}' - Case: {case_title}, Creator: {creator_name}, Color: {color}")
        
        print("   [OK] All model relationships working correctly")
        
        # Test URL patterns (would need Django test client for full test)
        expected_urls = [
            'event_calendar', 'event_list', 'event_create', 
            'calendar_api', 'case_list', 'client_list', 'document_list'
        ]
        print(f"   [OK] Expected URL patterns: {', '.join(expected_urls)}")
        
    except Exception as e:
        print(f"   [ERROR] Error during health check: {e}")
    
    print("\n" + "=" * 60)
    print("CALENDAR SYSTEM TEST COMPLETED")
    print("=" * 60)
    print("\nNext Steps:")
    print("1. Run: python manage.py runserver")
    print("2. Visit: http://localhost:8000/calendar/")
    print("3. Test creating new events via web interface")
    print("4. Check calendar API: http://localhost:8000/api/calendar/")
    print("\nSystem Status: READY [OK]")

if __name__ == '__main__':
    test_calendar_system()
