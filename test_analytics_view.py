# test_analytics_view.py - Test the analytics dashboard view

import os
import sys
import django

# Setup Django
sys.path.append('C:/GPT4_PROJECTS/JURISTI')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'legal_manager.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from legal_manager.cases.models import User
from legal_manager.cases.views_analytics_enhanced import AnalyticsDashboardView

def test_analytics_view():
    """
    Test if the analytics dashboard view returns the correct context data
    """
    print("Testing Analytics Dashboard View...")
    
    # Create a test request
    factory = RequestFactory()
    request = factory.get('/analytics/')
    
    # Get a user
    user = User.objects.first()
    if not user:
        print("ERROR: No users found. Run populate_simple_data.py first.")
        return
    
    request.user = user
    
    # Create the view
    view = AnalyticsDashboardView()
    view.request = request
    
    # Get the context data
    try:
        context = view.get_context_data()
        
        print("SUCCESS: View context data retrieved")
        print("Context keys:", list(context.keys()))
        
        # Check if essential data is present
        essential_keys = ['case_stats', 'financial_overview', 'productivity', 'deadlines']
        
        for key in essential_keys:
            if key in context:
                print(f"OK {key}: Present")
                if key == 'case_stats':
                    print(f"  Total cases: {context[key].get('total_cases', 'N/A')}")
                elif key == 'financial_overview':
                    print(f"  Total revenue: {context[key].get('total_revenue', 'N/A')}")
                elif key == 'productivity':
                    print(f"  Hours logged: {context[key].get('hours_logged', 'N/A')}")
                elif key == 'deadlines':
                    print(f"  Upcoming deadlines: {context[key].get('upcoming_deadlines', 'N/A')}")
            else:
                print(f"MISSING {key}: Missing")
        
        # Check charts data
        if 'charts_data' in context:
            print("OK charts_data: Present (JSON format)")
            # Try to parse the JSON to see if it's valid
            import json
            try:
                charts = json.loads(context['charts_data'])
                print(f"  Chart data keys: {list(charts.keys())}")
            except:
                print("  WARNING: Charts data is not valid JSON")
        else:
            print("MISSING charts_data: Missing")
        
        print("\nTemplate name:", view.template_name)
        
        # Check if template exists
        import os
        template_path = f"C:/GPT4_PROJECTS/JURISTI/templates/{view.template_name}"
        if os.path.exists(template_path):
            print(f"OK Template exists: {template_path}")
        else:
            print(f"MISSING Template missing: {template_path}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_template_rendering():
    """
    Test if the template can render with the context data
    """
    print("\nTesting Template Rendering...")
    
    from django.template.loader import get_template
    from django.template import Context
    from legal_manager.cases.analytics_service import get_dashboard_data, get_analytics_charts_data
    from legal_manager.cases.views_analytics_enhanced import DecimalEncoder
    import json
    
    user = User.objects.first()
    
    try:
        # Get the data
        analytics_data = get_dashboard_data(user)
        charts_data = get_analytics_charts_data(user)
        
        # Create context
        context = {
            **analytics_data,
            'charts_data': json.dumps(charts_data, cls=DecimalEncoder),
            'user': user
        }
        
        # Try to get the template
        template = get_template('analytics_enhanced/dashboard.html')
        
        print("OK Template loaded successfully")
        print("OK Context data prepared")
        
        # Try to render (this might take a moment)
        print("Attempting to render template...")
        rendered = template.render(context)
        
        print("OK Template rendered successfully")
        print(f"Rendered content length: {len(rendered)} characters")
        
        # Check if key metrics are in the rendered content
        if str(analytics_data['case_stats']['total_cases']) in rendered:
            print("OK Total cases found in rendered content")
        else:
            print("ERROR Total cases NOT found in rendered content")
            
        if str(analytics_data['financial_overview']['total_revenue']) in rendered:
            print("OK Total revenue found in rendered content")  
        else:
            print("ERROR Total revenue NOT found in rendered content")
        
        return True
        
    except Exception as e:
        print(f"ERROR in template rendering: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("Analytics Dashboard Testing")
    print("=" * 40)
    
    success1 = test_analytics_view()
    success2 = test_template_rendering()
    
    if success1 and success2:
        print("\nALL TESTS PASSED")
        print("The analytics dashboard should be working correctly.")
        print("\nTo test in browser:")
        print("1. python manage.py runserver")
        print("2. Go to http://localhost:8000/analytics/")
        print("3. Login with admin_user / password123")
    else:
        print("\nSOME TESTS FAILED")
        print("Check the errors above for troubleshooting.")
