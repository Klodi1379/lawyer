#!/usr/bin/env python3
"""
Setup Script për Enhanced Features të Legal Case Manager
Ky script krijon migration files dhe instalimet e nevojshme për tre modulet e reja:
1. Advanced Billing System
2. Client Portal 
3. Analytics & Reporting
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
from django.db import connection
from django.contrib.auth import get_user_model

def run_command(command_list):
    """Executes a Django management command"""
    print(f"Running: {' '.join(command_list)}")
    try:
        execute_from_command_line(command_list)
        print("✅ Success!")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def create_sample_data():
    """Krijon të dhëna shembull për testime"""
    print("\n📊 Creating sample data...")
    
    # Import models
    from legal_manager.cases.models_billing import Currency, BillingRate, ExpenseCategory
    from legal_manager.cases.models_client_portal import ClientPortalAccess
    from legal_manager.cases.models import Client
    
    # Krijon valutat
    currencies = [
        {'code': 'EUR', 'name': 'Euro', 'symbol': '€', 'is_base_currency': True},
        {'code': 'USD', 'name': 'US Dollar', 'symbol': '$', 'exchange_rate': 1.1},
        {'code': 'ALL', 'name': 'Albanian Lek', 'symbol': 'L', 'exchange_rate': 110.0},
    ]
    
    for curr_data in currencies:
        currency, created = Currency.objects.get_or_create(
            code=curr_data['code'],
            defaults=curr_data
        )
        if created:
            print(f"✅ Created currency: {currency.code}")
    
    # Krijon kategori shpenzimesh
    expense_categories = [
        {'name': 'Transport', 'description': 'Shpenzime transporti', 'is_billable': True, 'default_markup_percentage': 10},
        {'name': 'Fotokopiim', 'description': 'Shpenzime fotokopiimi', 'is_billable': True, 'default_markup_percentage': 15},
        {'name': 'Taksa Gjyqi', 'description': 'Taksa dhe detyrime gjyqësore', 'is_billable': True, 'default_markup_percentage': 0},
        {'name': 'Ekspertiza', 'description': 'Shërbime ekspertimi', 'is_billable': True, 'default_markup_percentage': 5},
        {'name': 'Administrativ', 'description': 'Shpenzime administrative', 'is_billable': False},
    ]
    
    for cat_data in expense_categories:
        category, created = ExpenseCategory.objects.get_or_create(
            name=cat_data['name'],
            defaults=cat_data
        )
        if created:
            print(f"✅ Created expense category: {category.name}")
    
    # Krijon tarifa faturimi
    base_currency = Currency.objects.filter(is_base_currency=True).first()
    if base_currency:
        billing_rates = [
            {'name': 'Avokat Senior', 'rate_type': 'hourly', 'amount': 80, 'currency': base_currency},
            {'name': 'Avokat Junior', 'rate_type': 'hourly', 'amount': 50, 'currency': base_currency},
            {'name': 'Paralegal', 'rate_type': 'hourly', 'amount': 30, 'currency': base_currency},
            {'name': 'Konsultim', 'rate_type': 'hourly', 'amount': 100, 'currency': base_currency},
        ]
        
        for rate_data in billing_rates:
            rate, created = BillingRate.objects.get_or_create(
                name=rate_data['name'],
                defaults=rate_data
            )
            if created:
                print(f"✅ Created billing rate: {rate.name}")
    
    # Aktivizon Client Portal për të gjithë klientët ekzistues
    clients = Client.objects.all()
    for client in clients:
        portal_access, created = ClientPortalAccess.objects.get_or_create(
            client=client,
            defaults={
                'is_enabled': True,
                'can_view_documents': True,
                'can_download_documents': True,
                'can_view_invoices': True,
                'can_view_payments': True,
                'can_upload_documents': False,
                'can_message_lawyer': True,
                'email_notifications': True,
                'sms_notifications': False,
            }
        )
        if created:
            print(f"✅ Enabled portal access for client: {client.name}")

def update_settings():
    """Përditëson settings.py për të përfshirë aplikacionet e reja"""
    print("\n⚙️ Updating settings...")
    
    settings_file = project_root / 'legal_manager' / 'settings.py'
    
    # Lexon settings aktual
    with open(settings_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Shton installedapps të reja nëse nuk janë
    new_apps = [
        "'plotly',",
        "'django_widget_tweaks',", 
        "'channels',",
        "'channels_redis',",
    ]
    
    for app in new_apps:
        if app not in content:
            # Gjen INSTALLED_APPS dhe shton aplikacionin
            if 'INSTALLED_APPS = [' in content:
                content = content.replace(
                    'INSTALLED_APPS = [',
                    f'INSTALLED_APPS = [\n    {app}'
                )
                print(f"✅ Added {app} to INSTALLED_APPS")
    
    # Shton konfigurimin e Channels nëse nuk ekziston
    if 'ASGI_APPLICATION' not in content:
        channels_config = '''
# Channels Configuration
ASGI_APPLICATION = 'legal_manager.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('127.0.0.1', 6379)],
        },
    },
}
'''
        content += channels_config
        print("✅ Added Channels configuration")
    
    # Shkruan përsëri fajlin
    with open(settings_file, 'w', encoding='utf-8') as f:
        f.write(content)

def create_templates():
    """Krijon template strukture bazë"""
    print("\n📄 Creating template structure...")
    
    template_dirs = [
        'templates/billing',
        'templates/client_portal', 
        'templates/analytics',
        'templates/billing/emails',
        'templates/client_portal/emails',
    ]
    
    for template_dir in template_dirs:
        dir_path = project_root / template_dir
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created directory: {template_dir}")
    
    # Krijon template bazë për billing
    billing_base = project_root / 'templates/billing/base.html'
    if not billing_base.exists():
        with open(billing_base, 'w', encoding='utf-8') as f:
            f.write('''{% extends "base.html" %}
{% load static %}

{% block title %}Billing - {% endblock %}

{% block extra_css %}
<link href="{% static 'css/billing.css' %}" rel="stylesheet">
{% endblock %}

{% block content %}
<div class="billing-container">
    {% block billing_content %}{% endblock %}
</div>
{% endblock %}

{% block extra_js %}
<script src="{% static 'js/billing.js' %}"></script>
{% endblock %}''')
        print("✅ Created billing base template")

def create_static_files():
    """Krijon strukture për static files"""
    print("\n🎨 Creating static file structure...")
    
    static_dirs = [
        'static/css/billing',
        'static/css/client_portal',
        'static/css/analytics',
        'static/js/billing',
        'static/js/client_portal', 
        'static/js/analytics',
    ]
    
    for static_dir in static_dirs:
        dir_path = project_root / static_dir
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created directory: {static_dir}")

def main():
    """Main setup function"""
    print("🚀 Starting Enhanced Features Setup for Legal Case Manager")
    print("=" * 60)
    
    # 1. Update settings
    update_settings()
    
    # 2. Create migrations for new models
    print("\n📋 Creating migrations...")
    commands = [
        ['python', 'manage.py', 'makemigrations', 'cases', '--name', 'add_billing_models'],
        ['python', 'manage.py', 'makemigrations', 'cases', '--name', 'add_client_portal_models'],  
        ['python', 'manage.py', 'makemigrations', 'cases', '--name', 'add_analytics_models'],
    ]
    
    for cmd in commands:
        run_command(cmd)
    
    # 3. Run migrations
    print("\n🔄 Running migrations...")
    run_command(['python', 'manage.py', 'migrate'])
    
    # 4. Create template structure
    create_templates()
    
    # 5. Create static file structure  
    create_static_files()
    
    # 6. Create sample data
    create_sample_data()
    
    # 7. Collect static files
    print("\n📦 Collecting static files...")
    run_command(['python', 'manage.py', 'collectstatic', '--noinput'])
    
    print("\n" + "=" * 60)
    print("✅ Enhanced Features Setup Complete!")
    print("\nTë aktivizuara:")
    print("📊 Advanced Billing System")
    print("🏠 Client Portal")  
    print("📈 Analytics & Reporting")
    print("\nNext Steps:")
    print("1. Restart your Django development server")
    print("2. Navigate to /billing/ for billing features")
    print("3. Navigate to /portal/ for client portal")
    print("4. Navigate to /analytics/ for analytics dashboard")
    print("5. Check admin panel for new configuration options")

if __name__ == '__main__':
    main()