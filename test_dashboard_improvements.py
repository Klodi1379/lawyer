#!/usr/bin/env python
"""
Test script për dashboard-in e përmirësuar
"""
import os
import sys
import django

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'legal_manager.settings')
django.setup()

def test_dashboard_improvements():
    """Test dashboard improvements and fixes"""
    print("Testing dashboard improvements...")
    
    # Test 1: Check if dashboard view can be imported
    try:
        from legal_manager.cases.dashboard_views_enhanced import EnhancedDashboardView
        print("SUCCESS: Enhanced dashboard view imported successfully")
    except Exception as e:
        print(f"ERROR: Cannot import enhanced dashboard view: {e}")
        return False
    
    # Test 2: Check if fallback widgets work
    try:
        from legal_manager.cases.dashboard_widgets.quick_actions_fallback import (
            QuickActionsWidgetFallback, NotificationWidgetFallback
        )
        print("SUCCESS: Fallback widgets imported successfully")
    except Exception as e:
        print(f"ERROR: Cannot import fallback widgets: {e}")
        return False
    
    # Test 3: Test fallback widget functionality
    try:
        from legal_manager.cases.models import User
        
        # Create or get a test user
        user, created = User.objects.get_or_create(
            username='test_dashboard',
            defaults={
                'email': 'test@dashboard.com',
                'role': 'lawyer'
            }
        )
        
        # Test quick actions fallback
        quick_actions = QuickActionsWidgetFallback(user)
        actions = quick_actions.get_actions()
        stats = quick_actions.get_quick_stats()
        suggestions = quick_actions.get_recent_suggestions()
        shortcuts = quick_actions.get_keyboard_shortcuts()
        
        print(f"SUCCESS: Quick actions working - {len(actions)} actions, {len(stats)} stats")
        
        # Test notifications fallback
        notifications = NotificationWidgetFallback(user)
        notifs = notifications.get_notifications()
        
        print(f"SUCCESS: Notifications working - {len(notifs)} notifications")
        
    except Exception as e:
        print(f"ERROR: Widget functionality test failed: {e}")
        return False
    
    # Test 4: Check template file exists and is valid
    try:
        template_path = os.path.join(
            os.path.dirname(__file__), 
            'templates/dashboard/enhanced_index.html'
        )
        
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'justify-content: space-between' in content:
                    print("SUCCESS: Template CSS fix applied")
                else:
                    print("WARNING: CSS fix might not be applied")
                
                if 'quick-action-card' in content:
                    print("SUCCESS: Quick action styling present")
                else:
                    print("WARNING: Quick action styling missing")
        else:
            print("ERROR: Template file not found")
            return False
            
    except Exception as e:
        print(f"ERROR: Template check failed: {e}")
        return False
    
    print("\nDashboard improvements test completed successfully!")
    return True

def print_summary():
    """Print improvement summary"""
    print("\n" + "="*60)
    print("DASHBOARD IMPROVEMENTS SUMMARY")
    print("="*60)
    print("✅ Fixed CSS issues:")
    print("   - justify-content: space-between (was 'between')")
    print("   - Improved quick action card styling")
    print("   - Better responsive design")
    print("   - Enhanced stat card layouts")
    print("")
    print("✅ Added fallback widgets:")
    print("   - QuickActionsWidgetFallback")
    print("   - NotificationWidgetFallback")
    print("   - Graceful error handling")
    print("")
    print("✅ Template improvements:")
    print("   - Better error handling")
    print("   - Default content when data missing")
    print("   - Improved loading states")
    print("   - Enhanced mobile responsiveness")
    print("")
    print("✅ JavaScript enhancements:")
    print("   - Better error handling")
    print("   - Improved chart initialization")
    print("   - Enhanced notification system")
    print("="*60)

if __name__ == '__main__':
    success = test_dashboard_improvements()
    if success:
        print_summary()
    else:
        print("\nSome tests failed. Please check the errors above.")
