# calendar_fix.py - Fix për problemet e kalendarit

import os
import sys
import django

# Setup Django
sys.path.append('C:/GPT4_PROJECTS/JURISTI')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'legal_manager.settings')
django.setup()

from legal_manager.cases.models import CaseEvent, EventType
from django.utils import timezone
from datetime import timedelta

def fix_calendar_issues():
    """
    Fiksimi i problemeve të kalendarit
    """
    print("🔧 Fixing calendar issues...")
    
    # 1. Sigurohu që ka EventType
    event_types = [
        {'name': 'Court Hearing', 'color': '#dc3545', 'is_deadline': True},
        {'name': 'Client Meeting', 'color': '#28a745', 'is_deadline': False},
        {'name': 'Document Deadline', 'color': '#ffc107', 'is_deadline': True},
        {'name': 'Internal Meeting', 'color': '#007bff', 'is_deadline': False},
        {'name': 'Filing Deadline', 'color': '#fd7e14', 'is_deadline': True}
    ]
    
    for event_data in event_types:
        event_type, created = EventType.objects.get_or_create(
            name=event_data['name'],
            defaults=event_data
        )
        if created:
            print(f"  ✓ Created event type: {event_type.name}")
    
    # 2. Sigurohu që events kanë metodat e duhura
    events = CaseEvent.objects.all()
    print(f"  📋 Found {events.count()} events")
    
    # 3. Testo metodat
    for event in events[:3]:  # Testo vetëm 3 të parat
        try:
            color = event.get_calendar_color()
            attendees = event.get_attendees_list()
            print(f"  ✓ Event '{event.title}' - Color: {color}, Attendees: {attendees}")
        except Exception as e:
            print(f"  ❌ Error with event '{event.title}': {e}")
    
    # 4. Krijoni disa evente për test nëse s'ka
    if events.count() == 0:
        print("  📅 Creating test events...")
        from legal_manager.cases.models import Case, User
        
        cases = Case.objects.all()
        users = User.objects.filter(role__in=['lawyer', 'admin'])
        
        if cases.exists() and users.exists():
            case = cases.first()
            user = users.first()
            event_type = EventType.objects.first()
            
            # Event për sot
            today_event = CaseEvent.objects.create(
                case=case,
                title="Test Meeting Today",
                description="Test event for today",
                event_type=event_type,
                starts_at=timezone.now().replace(hour=14, minute=0, second=0, microsecond=0),
                ends_at=timezone.now().replace(hour=15, minute=0, second=0, microsecond=0),
                created_by=user,
                priority='medium'
            )
            print(f"  ✓ Created today event: {today_event.title}")
            
            # Event për nesër
            tomorrow_event = CaseEvent.objects.create(
                case=case,
                title="Court Hearing Tomorrow",
                description="Important court hearing",
                event_type=event_type,
                starts_at=timezone.now() + timedelta(days=1),
                ends_at=timezone.now() + timedelta(days=1, hours=2),
                created_by=user,
                priority='high',
                is_deadline=True
            )
            print(f"  ✓ Created tomorrow event: {tomorrow_event.title}")
    
    print("✅ Calendar fixes completed!")

def test_calendar_api():
    """
    Teston API-n e kalendarit
    """
    print("🧪 Testing calendar API...")
    
    from django.test import RequestFactory
    from legal_manager.cases.views import calendar_api
    from legal_manager.cases.models import User
    
    factory = RequestFactory()
    
    # Krijo request
    request = factory.get('/api/calendar/')
    
    # Gjej një user
    user = User.objects.first()
    if user:
        request.user = user
        
        try:
            response = calendar_api(request)
            print(f"  ✓ API Response Status: {response.status_code}")
            
            import json
            data = json.loads(response.content.decode())
            print(f"  ✓ Events returned: {len(data)}")
            
            if data:
                print("  📋 Sample event data:")
                for key, value in data[0].items():
                    print(f"    {key}: {value}")
        except Exception as e:
            print(f"  ❌ API Error: {e}")
    else:
        print("  ❌ No users found for testing")

if __name__ == '__main__':
    fix_calendar_issues()
    test_calendar_api()
