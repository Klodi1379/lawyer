#!/usr/bin/env python
"""Script to create sample data for testing"""
import os
import sys
import django

# Set the settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'legal_manager.settings')

# Add the project directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'legal_manager'))

# Setup Django
django.setup()

from cases.models import User, Client, Case

def create_sample_data():
    print("Creating sample data for Legal Case Manager...")
    
    # Create sample clients
    clients_data = [
        {
            'full_name': 'Maria Gjoni',
            'email': 'maria.gjoni@email.com',
            'phone': '+355 69 123 4567',
            'address': 'Rruga e Durrësit 123, Tiranë',
            'organization': ''
        },
        {
            'full_name': 'Agron Berisha',
            'email': 'agron.berisha@company.al',
            'phone': '+355 68 987 6543',
            'address': 'Bulevardi Zog I, 45, Tiranë',
            'organization': 'Berisha Construction Sh.p.k.'
        },
        {
            'full_name': 'Elena Krasniqi',
            'email': 'elena.krasniqi@gmail.com',
            'phone': '+355 67 555 0123',
            'address': 'Rruga Mine Peza 67, Tiranë',
            'organization': ''
        },
        {
            'full_name': 'Driton Ahmeti',
            'email': 'driton@techfirm.al',
            'phone': '+355 69 876 5432',
            'address': 'Rruga e Kavajës 89, Tiranë',
            'organization': 'TechFirm Albania'
        },
        {
            'full_name': 'Valbona Selimi',
            'email': 'valbona.selimi@outlook.com',
            'phone': '+355 68 234 5678',
            'address': 'Lagjja 21 Dhjetori, Pallati 15, Ap. 23, Tiranë',
            'organization': ''
        }
    ]
    
    # Create clients
    created_clients = []
    for client_data in clients_data:
        client, created = Client.objects.get_or_create(
            email=client_data['email'],
            defaults=client_data
        )
        if created:
            print(f"[+] Created client: {client.full_name}")
        else:
            print(f"[-] Client already exists: {client.full_name}")
        created_clients.append(client)
    
    # Create a lawyer user if it doesn't exist
    lawyer_user, created = User.objects.get_or_create(
        username='lawyer1',
        defaults={
            'email': 'lawyer@example.com',
            'first_name': 'Arben',
            'last_name': 'Hoxha',
            'role': 'lawyer'
        }
    )
    if created:
        lawyer_user.set_password('lawyer123')
        lawyer_user.save()
        print(f"[+] Created lawyer user: {lawyer_user.username}")
    else:
        print(f"[-] Lawyer user already exists: {lawyer_user.username}")
    
    # Create a paralegal user
    paralegal_user, created = User.objects.get_or_create(
        username='paralegal1',
        defaults={
            'email': 'paralegal@example.com',
            'first_name': 'Anjeza',
            'last_name': 'Basha',
            'role': 'paralegal'
        }
    )
    if created:
        paralegal_user.set_password('paralegal123')
        paralegal_user.save()
        print(f"[+] Created paralegal user: {paralegal_user.username}")
    else:
        print(f"[-] Paralegal user already exists: {paralegal_user.username}")
    
    print(f"\n[SUCCESS] Sample data creation completed!")
    print(f"[INFO] Total clients: {Client.objects.count()}")
    print(f"[INFO] Total users: {User.objects.count()}")
    
    print(f"\n[NEXT STEPS] You can now:")
    print(f"1. Login as admin: admin / admin123")
    print(f"2. Login as lawyer: lawyer1 / lawyer123") 
    print(f"3. Login as paralegal: paralegal1 / paralegal123")
    print(f"4. Create new cases with the sample clients")

if __name__ == '__main__':
    create_sample_data()
