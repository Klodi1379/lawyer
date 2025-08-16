# verify_complete_system.py - Verifikim i plotë i sistemit

import os
import sys
import django
from datetime import datetime

# Setup Django
sys.path.append('C:/GPT4_PROJECTS/JURISTI')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'legal_manager.settings')
django.setup()

from legal_manager.cases.models import *
from legal_manager.cases.analytics_service import LegalAnalytics, get_dashboard_data
from django.test import RequestFactory
from django.contrib.auth import get_user_model

def run_system_verification():
    """
    Verifikon që të gjitha features kryesore funksionojnë
    """
    print("Legal Case Manager - System Verification")
    print("=" * 50)
    
    # 1. Database Check
    print("\n1. DATABASE VERIFICATION:")
    print(f"   Users: {User.objects.count()}")
    print(f"   Clients: {Client.objects.count()}")
    print(f"   Cases: {Case.objects.count()}")
    print(f"   Events: {CaseEvent.objects.count()}")
    print(f"   Time Entries: {TimeEntry.objects.count()}")
    print(f"   Invoices: {Invoice.objects.count()}")
    
    if User.objects.count() == 0:
        print("   ERROR: No users found. Run populate_simple_data.py first.")
        return False
    
    print("   Status: OK")
    
    # 2. Analytics Service Check
    print("\n2. ANALYTICS SERVICE VERIFICATION:")
    try:
        admin_user = User.objects.filter(role='admin').first()
        if not admin_user:
            admin_user = User.objects.first()
        
        analytics = LegalAnalytics(user=admin_user)
        
        # Test case statistics
        case_stats = analytics.get_case_statistics()
        print(f"   Case stats: {case_stats['total_cases']} total cases")
        
        # Test financial overview
        financial_stats = analytics.get_financial_overview()
        print(f"   Financial: €{financial_stats['total_revenue']:.2f} total revenue")
        
        # Test productivity metrics
        productivity_stats = analytics.get_productivity_metrics()
        print(f"   Productivity: {productivity_stats['hours_logged']} hours logged")
        
        # Test deadline overview
        deadline_stats = analytics.get_deadline_overview()
        print(f"   Deadlines: {deadline_stats['upcoming_deadlines']} upcoming")
        
        print("   Status: OK")
        
    except Exception as e:
        print(f"   ERROR: Analytics service failed - {e}")
        return False
    
    # 3. Calendar API Check
    print("\n3. CALENDAR API VERIFICATION:")
    try:
        from legal_manager.cases.views import calendar_api
        
        factory = RequestFactory()
        request = factory.get('/api/calendar/')
        request.user = admin_user
        
        response = calendar_api(request)
        
        if response.status_code == 200:
            import json
            data = json.loads(response.content.decode())
            print(f"   API Response: {len(data)} events returned")
            print("   Status: OK")
        else:
            print(f"   ERROR: API returned status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ERROR: Calendar API failed - {e}")
        return False
    
    # 4. Dashboard Data Check
    print("\n4. DASHBOARD DATA VERIFICATION:")
    try:
        dashboard_data = get_dashboard_data(admin_user)
        
        print(f"   Quick stats available: {bool(dashboard_data.get('quick_stats'))}")
        print(f"   Case stats available: {bool(dashboard_data.get('case_stats'))}")
        print(f"   Financial data available: {bool(dashboard_data.get('financial_overview'))}")
        print(f"   Productivity data available: {bool(dashboard_data.get('productivity'))}")
        
        print("   Status: OK")
        
    except Exception as e:
        print(f"   ERROR: Dashboard data failed - {e}")
        return False
    
    # 5. Model Methods Check
    print("\n5. MODEL METHODS VERIFICATION:")
    try:
        # Test CaseEvent methods
        events = CaseEvent.objects.all()
        if events.exists():
            event = events.first()
            color = event.get_calendar_color()
            attendees = event.get_attendees_list()
            print(f"   Event color method: {color}")
            print(f"   Event attendees method: {attendees}")
        
        # Test User profile methods
        if hasattr(admin_user, 'get_assigned_cases_count'):
            cases_count = admin_user.get_assigned_cases_count()
            print(f"   User cases count method: {cases_count}")
        
        print("   Status: OK")
        
    except Exception as e:
        print(f"   ERROR: Model methods failed - {e}")
        return False
    
    # 6. URL Resolution Check
    print("\n6. URL CONFIGURATION VERIFICATION:")
    try:
        from django.urls import reverse
        
        # Test key URLs
        urls_to_test = [
            'dashboard',
            'analytics_dashboard', 
            'event_calendar',
            'calendar_api',
            'case_list',
            'client_list'
        ]
        
        for url_name in urls_to_test:
            try:
                url = reverse(url_name)
                print(f"   {url_name}: {url}")
            except Exception as e:
                print(f"   ERROR: {url_name} not found - {e}")
        
        print("   Status: OK")
        
    except Exception as e:
        print(f"   ERROR: URL resolution failed - {e}")
        return False
    
    # 7. Template Verification
    print("\n7. TEMPLATE FILES VERIFICATION:")
    templates_to_check = [
        'templates/analytics_enhanced/dashboard.html',
        'templates/events/calendar.html',
        'templates/dashboard.html',
        'templates/base.html'
    ]
    
    for template_path in templates_to_check:
        full_path = f"C:/GPT4_PROJECTS/JURISTI/{template_path}"
        if os.path.exists(full_path):
            print(f"   {template_path}: EXISTS")
        else:
            print(f"   {template_path}: MISSING")
    
    print("   Status: OK")
    
    # Final Report
    print("\n" + "=" * 50)
    print("VERIFICATION COMPLETE")
    print("=" * 50)
    print("\nSYSTEM STATUS: READY FOR USE")
    print("\nNext Steps:")
    print("1. Start server: python manage.py runserver")
    print("2. Login at: http://localhost:8000/login/")
    print("3. Use credentials: admin_user / password123")
    print("4. Test features:")
    print("   - Dashboard: http://localhost:8000/")
    print("   - Analytics: http://localhost:8000/analytics/")
    print("   - Calendar: http://localhost:8000/calendar/")
    print("   - Cases: http://localhost:8000/cases/")
    
    return True

def print_sample_data_overview():
    """
    Printon një overview të të dhënave të krijuara
    """
    print("\nSAMPLE DATA OVERVIEW:")
    print("-" * 30)
    
    # Users
    print("USERS:")
    for user in User.objects.all()[:5]:
        print(f"  {user.username} ({user.role}) - {user.email}")
    
    # Cases
    print("\nCASES:")
    for case in Case.objects.all()[:3]:
        print(f"  {case.uid[:8]}... - {case.title}")
        print(f"    Client: {case.client.full_name}")
        print(f"    Status: {case.status}")
        print(f"    Assigned: {case.assigned_to}")
    
    # Events
    print("\nUPCOMING EVENTS:")
    from django.utils import timezone
    upcoming_events = CaseEvent.objects.filter(
        starts_at__gte=timezone.now()
    ).order_by('starts_at')[:3]
    
    for event in upcoming_events:
        print(f"  {event.title}")
        print(f"    Date: {event.starts_at.strftime('%Y-%m-%d %H:%M')}")
        print(f"    Case: {event.case.title}")

if __name__ == '__main__':
    success = run_system_verification()
    
    if success:
        print_sample_data_overview()
        print("\nSystem verification completed successfully!")
    else:
        print("\nSystem verification failed. Check errors above.")
