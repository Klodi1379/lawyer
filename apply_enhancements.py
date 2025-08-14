#!/usr/bin/env python3
"""
Script për të aplikuar përmirësimet në sidebar dhe navbar
"""

import os
import sys
import django
from pathlib import Path

# Setup Django environment
project_root = Path(__file__).parent
sys.path.append(str(project_root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'legal_manager.settings')

django.setup()

from django.core.management import execute_from_command_line

def apply_enhancements():
    """
    Aplikon të gjitha përmirësimet për sidebar dhe navbar
    """
    print("🚀 Aplikimi i Përmirësimeve për Sidebar dhe Navbar")
    print("=" * 60)
    
    # 1. Collect static files për CSS të ri
    print("\n📦 Collecting static files...")
    try:
        execute_from_command_line(['manage.py', 'collectstatic', '--noinput'])
        print("✅ Static files collected successfully!")
    except Exception as e:
        print(f"❌ Error collecting static files: {e}")
    
    # 2. Check nëse fajlat e rinj ekzistojnë
    print("\n📋 Checking enhanced files...")
    
    required_files = [
        'templates/partials/sidebar_enhanced.html',
        'templates/partials/navbar_enhanced.html', 
        'static/css/enhanced-features.css',
        'legal_manager/cases/views_api_stats.py'
    ]
    
    all_files_exist = True
    for file_path in required_files:
        full_path = project_root / file_path
        if full_path.exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ Missing: {file_path}")
            all_files_exist = False
    
    if not all_files_exist:
        print("\n⚠️ Some files are missing. Please make sure all files are created.")
        return False
    
    # 3. Test që base.html është updated
    base_html_path = project_root / 'templates/base.html'
    if base_html_path.exists():
        with open(base_html_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if 'sidebar_enhanced.html' in content and 'navbar_enhanced.html' in content:
            print("✅ base.html updated to use enhanced templates")
        else:
            print("❌ base.html not properly updated")
            return False
    
    # 4. Test URLs
    try:
        from legal_manager.cases.urls import urlpatterns
        url_names = [pattern.name for pattern in urlpatterns if hasattr(pattern, 'name')]
        
        required_urls = [
            'enhanced_stats_api',
            'navbar_stats_api', 
            'search_api',
            'notifications_api'
        ]
        
        urls_ok = True
        for url_name in required_urls:
            if url_name in url_names:
                print(f"✅ API endpoint: {url_name}")
            else:
                print(f"❌ Missing API endpoint: {url_name}")
                urls_ok = False
        
        if not urls_ok:
            return False
            
    except Exception as e:
        print(f"❌ Error checking URLs: {e}")
        return False
    
    # 5. Create sample data for testing
    print("\n📊 Creating sample data for enhanced features...")
    create_sample_data()
    
    print("\n" + "=" * 60)
    print("🎉 Përmirësimet u aplikuan me sukses!")
    print("\nVeçoritë e reja:")
    print("📱 Enhanced Navbar me search, notifications, quick actions")
    print("🗂️ Enhanced Sidebar me billing, analytics, client portal") 
    print("📊 API endpoints për statistika në kohë reale")
    print("🎨 CSS të përmirësuar me animacione dhe dark mode")
    print("🔍 Global search functionality")
    print("🔔 Real-time notifications")
    
    print("\nNext Steps:")
    print("1. Restart Django development server")
    print("2. Navigate to dashboard të shihni ndryshimet")
    print("3. Test search functionality në navbar")
    print("4. Test sidebar navigation dhe stats")
    print("5. Try dark mode toggle")
    
    return True

def create_sample_data():
    """
    Krijon të dhëna shembull për testing
    """
    try:
        from legal_manager.cases.models import User, Case, Client, CaseDocument
        from legal_manager.cases.models_billing import Currency, BillingRate, ExpenseCategory
        
        # Krijon valuta
        eur, created = Currency.objects.get_or_create(
            code='EUR',
            defaults={
                'name': 'Euro',
                'symbol': '€',
                'is_base_currency': True,
                'exchange_rate': 1.0
            }
        )
        if created:
            print("✅ Created EUR currency")
        
        usd, created = Currency.objects.get_or_create(
            code='USD', 
            defaults={
                'name': 'US Dollar',
                'symbol': '$',
                'exchange_rate': 1.1
            }
        )
        if created:
            print("✅ Created USD currency")
        
        # Krijon tarifa
        rate, created = BillingRate.objects.get_or_create(
            name='Standard Hourly Rate',
            defaults={
                'rate_type': 'hourly',
                'amount': 75.00,
                'currency': eur
            }
        )
        if created:
            print("✅ Created billing rate")
        
        # Krijon kategori shpenzimesh
        categories = [
            ('Transport', 'Shpenzime transporti'),
            ('Court Fees', 'Taksa gjyqi'),
            ('Administrative', 'Shpenzime administrative')
        ]
        
        for name, desc in categories:
            cat, created = ExpenseCategory.objects.get_or_create(
                name=name,
                defaults={'description': desc, 'is_billable': True}
            )
            if created:
                print(f"✅ Created expense category: {name}")
        
        print("✅ Sample data created successfully")
        
    except Exception as e:
        print(f"⚠️ Error creating sample data: {e}")

def main():
    """
    Main function
    """
    success = apply_enhancements()
    
    if success:
        print("\n🎊 Përfundimi i suksesshëm!")
        print("Sistemi juaj tani ka navbar dhe sidebar të përmirësuar!")
    else:
        print("\n❌ Ka probleme. Ju lutem kontrolloni gabimet më lart.")
        return 1
    
    return 0

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)