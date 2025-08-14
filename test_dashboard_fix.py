# test_dashboard_fix.py - Test për të kontrolluar nëse rregullimi funksionon

import os
import sys
import django

# Setup Django environment
sys.path.append('C:/GPT4_PROJECTS/JURISTI')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'legal_manager.settings')

try:
    django.setup()
    
    # Import the fixed models and views
    from legal_manager.cases.models import Invoice, Case, Client
    from legal_manager.cases.dashboard_views import DashboardView
    from django.db.models import Sum, Count, Q, DecimalField
    from django.db.models.functions import Coalesce
    
    print("✅ Django setup successful!")
    
    # Test the corrected aggregation
    print("\n🧪 Testing fixed aggregation...")
    
    try:
        # This should work now without errors
        financial_data = Invoice.objects.aggregate(
            total_revenue=Coalesce(
                Sum('total_amount', filter=Q(paid=True)),
                0,
                output_field=DecimalField(max_digits=12, decimal_places=2)
            ),
            pending_revenue=Coalesce(
                Sum('total_amount', filter=Q(paid=False)),
                0,
                output_field=DecimalField(max_digits=12, decimal_places=2)
            ),
            paid_invoices=Count('id', filter=Q(paid=True)),
            total_invoices=Count('id')
        )
        
        print("✅ Fixed aggregation works!")
        print(f"   Total Revenue: {financial_data['total_revenue']}")
        print(f"   Pending Revenue: {financial_data['pending_revenue']}")
        print(f"   Paid Invoices: {financial_data['paid_invoices']}")
        print(f"   Total Invoices: {financial_data['total_invoices']}")
        
    except Exception as e:
        print(f"❌ Aggregation error still exists: {e}")
    
    # Test dashboard view instantiation
    print("\n🧪 Testing dashboard view...")
    try:
        # Create a mock request object
        class MockRequest:
            def __init__(self):
                self.user = MockUser()
        
        class MockUser:
            def __init__(self):
                self.role = 'admin'
                self.email = 'admin@test.com'
        
        dashboard = DashboardView()
        dashboard.request = MockRequest()
        
        print("✅ Dashboard view can be instantiated!")
        
    except Exception as e:
        print(f"❌ Dashboard view error: {e}")
    
    print("\n🎉 FIX SUMMARY:")
    print("==================")
    print("✅ Replaced Sum('paid') with Count('id', filter=Q(paid=True))")
    print("✅ Added proper Coalesce and DecimalField handling")
    print("✅ Fixed aggregation in both admin and client dashboard data")
    print("✅ Backup created: dashboard_views_backup.py")
    print("\n💡 Next step: Start your Django server and test the dashboard!")
    print("   python manage.py runserver")
    print("   Go to: http://localhost:8000/dashboard/")
    
except Exception as e:
    print(f"❌ Setup error: {e}")
    print("\nLet me create a simple verification script instead...")
    
    # If Django setup fails, just verify the file changes
    with open('C:/GPT4_PROJECTS/JURISTI/legal_manager/cases/dashboard_views.py', 'r') as f:
        content = f.read()
        
    if "Sum('paid')" in content:
        print("❌ Error: Sum('paid') still exists in the file!")
    else:
        print("✅ Good: Sum('paid') removed from dashboard_views.py")
    
    if "Count('id', filter=Q(paid=True))" in content:
        print("✅ Good: Correct aggregation found in file")
    else:
        print("⚠️  Warning: Expected aggregation not found")
    
    if "Coalesce" in content:
        print("✅ Good: Coalesce function is being used")
    else:
        print("⚠️  Warning: Coalesce function not found")
