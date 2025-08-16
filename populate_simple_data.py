# populate_simple_data.py - Script i thjeshtë për popullim të dhënash

import os
import sys
import django
from datetime import datetime, timedelta
from decimal import Decimal
import random

# Setup Django
sys.path.append('C:/GPT4_PROJECTS/JURISTI')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'legal_manager.settings')
django.setup()

from legal_manager.cases.models import *
from django.utils import timezone
from django.contrib.auth.hashers import make_password

def create_sample_data():
    print("Starting data population...")
    
    # Create users
    print("Creating users...")
    admin_user, created = User.objects.get_or_create(
        username='admin_user',
        defaults={
            'email': 'admin@legalfirm.com',
            'first_name': 'Admin',
            'last_name': 'User',
            'role': 'admin',
            'password': make_password('password123'),
            'is_staff': True,
            'is_superuser': True,
            'is_active': True
        }
    )
    if created:
        print(f"  Created admin user: {admin_user.username}")
    
    lawyer_anna, created = User.objects.get_or_create(
        username='lawyer_anna',
        defaults={
            'email': 'anna@legalfirm.com',
            'first_name': 'Anna',
            'last_name': 'Rossi',
            'role': 'lawyer',
            'password': make_password('password123'),
            'is_active': True
        }
    )
    if created:
        print(f"  Created lawyer: {lawyer_anna.username}")
    
    # Create clients
    print("Creating clients...")
    client1, created = Client.objects.get_or_create(
        email='abc@corp.com',
        defaults={
            'full_name': 'ABC Corporation',
            'phone': '+355 4 2123456',
            'address': 'Bulevardi Deshmoret e Kombit, Tirane',
            'organization': 'ABC Corporation'
        }
    )
    if created:
        print(f"  Created client: {client1.full_name}")
    
    client2, created = Client.objects.get_or_create(
        email='elena@example.com',
        defaults={
            'full_name': 'Elena Marku',
            'phone': '+355 69 1234567',
            'address': 'Rruga Qemal Stafa, Tirane'
        }
    )
    if created:
        print(f"  Created client: {client2.full_name}")
    
    # Create event types
    print("Creating event types...")
    event_types_data = [
        {'name': 'Court Hearing', 'color': '#dc3545', 'is_deadline': True},
        {'name': 'Client Meeting', 'color': '#28a745', 'is_deadline': False},
        {'name': 'Document Deadline', 'color': '#ffc107', 'is_deadline': True},
    ]
    
    for event_data in event_types_data:
        event_type, created = EventType.objects.get_or_create(
            name=event_data['name'],
            defaults=event_data
        )
        if created:
            print(f"  Created event type: {event_type.name}")
    
    # Create document types and statuses (skip if not exist)
    print("Checking document types and statuses...")
    try:
        doc_types = ['Contract', 'Legal Brief', 'Court Filing', 'Evidence']
        for doc_type_name in doc_types:
            doc_type, created = DocumentType.objects.get_or_create(name=doc_type_name)
            if created:
                print(f"  Created document type: {doc_type.name}")
    except:
        print("  DocumentType model not found, skipping...")
    
    try:
        doc_statuses = ['Draft', 'Final', 'Signed']
        for status_name in doc_statuses:
            status, created = DocumentStatus.objects.get_or_create(name=status_name)
            if created:
                print(f"  Created document status: {status.name}")
    except:
        print("  DocumentStatus model not found, skipping...")
    
    # Create case priorities (skip if not exist)
    print("Checking case priorities...")
    try:
        priorities = ['Low', 'Medium', 'High', 'Urgent']
        for priority_name in priorities:
            priority, created = CasePriority.objects.get_or_create(name=priority_name)
            if created:
                print(f"  Created priority: {priority.name}")
    except:
        print("  CasePriority model not found, skipping...")
    
    # Create cases
    print("Creating cases...")
    case1, created = Case.objects.get_or_create(
        title='Contract Dispute - ABC Corporation',
        defaults={
            'description': 'Dispute over breach of contract terms regarding software licensing agreement.',
            'case_type': 'commercial',
            'status': 'open',
            'client': client1,
            'assigned_to': lawyer_anna
        }
    )
    if created:
        print(f"  Created case: {case1.title}")
    
    case2, created = Case.objects.get_or_create(
        title='Family Inheritance Dispute',
        defaults={
            'description': 'Multiple heirs disputing the distribution of family estate.',
            'case_type': 'family',
            'status': 'in_court',
            'client': client2,
            'assigned_to': lawyer_anna
        }
    )
    if created:
        print(f"  Created case: {case2.title}")
    
    # Create events
    print("Creating events...")
    court_hearing_type = EventType.objects.filter(name='Court Hearing').first()
    client_meeting_type = EventType.objects.filter(name='Client Meeting').first()
    
    # Past event
    event1, created = CaseEvent.objects.get_or_create(
        title='Initial Client Meeting',
        case=case1,
        defaults={
            'description': 'Initial consultation with ABC Corporation',
            'event_type': client_meeting_type,
            'priority': 'medium',
            'starts_at': timezone.now() - timedelta(days=20),
            'ends_at': timezone.now() - timedelta(days=20) + timedelta(hours=2),
            'location': 'Office Conference Room',
            'created_by': lawyer_anna
        }
    )
    if created:
        print(f"  Created past event: {event1.title}")
    
    # Future event (today)
    event2, created = CaseEvent.objects.get_or_create(
        title='Court Hearing - Contract Dispute',
        case=case1,
        defaults={
            'description': 'Court hearing for contract dispute case',
            'event_type': court_hearing_type,
            'priority': 'high',
            'starts_at': timezone.now().replace(hour=14, minute=0, second=0, microsecond=0),
            'ends_at': timezone.now().replace(hour=16, minute=0, second=0, microsecond=0),
            'location': 'Court Room 1',
            'created_by': lawyer_anna,
            'is_deadline': True
        }
    )
    if created:
        print(f"  Created today event: {event2.title}")
    
    # Future event (tomorrow)
    event3, created = CaseEvent.objects.get_or_create(
        title='Document Filing Deadline',
        case=case2,
        defaults={
            'description': 'Deadline to file inheritance documentation',
            'event_type': EventType.objects.filter(name='Document Deadline').first(),
            'priority': 'urgent',
            'starts_at': timezone.now() + timedelta(days=1),
            'ends_at': timezone.now() + timedelta(days=1, hours=1),
            'location': 'Court Registry',
            'created_by': lawyer_anna,
            'is_deadline': True
        }
    )
    if created:
        print(f"  Created tomorrow event: {event3.title}")
    
    # Create time entries
    print("Creating time entries...")
    for i in range(10):
        date = timezone.now() - timedelta(days=i)
        minutes = random.randint(60, 480)  # 1-8 hours
        
        TimeEntry.objects.get_or_create(
            case=case1,
            user=lawyer_anna,
            created_at=date,
            defaults={
                'minutes': minutes,
                'description': f'Work on case {case1.title} - Day {i+1}'
            }
        )
    
    print("  Created time entries for case 1")
    
    # Create invoices
    print("Creating invoices...")
    total_minutes = TimeEntry.objects.filter(case=case1).aggregate(
        total=models.Sum('minutes')
    )['total'] or 0
    
    total_hours = total_minutes / 60
    hourly_rate = 150
    total_amount = Decimal(str(total_hours * hourly_rate))
    
    invoice1, created = Invoice.objects.get_or_create(
        case=case1,
        defaults={
            'issued_to': case1.client,
            'total_amount': total_amount,
            'paid': True,
            'issued_at': timezone.now() - timedelta(days=5)
        }
    )
    if created:
        print(f"  Created invoice: €{total_amount:.2f}")
    
    print("Data population completed!")
    
    # Print statistics
    print("\nFinal Statistics:")
    print(f"Users: {User.objects.count()}")
    print(f"Clients: {Client.objects.count()}")
    print(f"Cases: {Case.objects.count()}")
    print(f"Events: {CaseEvent.objects.count()}")
    print(f"Time Entries: {TimeEntry.objects.count()}")
    print(f"Invoices: {Invoice.objects.count()}")

if __name__ == '__main__':
    print("Legal Case Management Data Population")
    print("=" * 50)
    create_sample_data()
    print("\nDatabase populated successfully!")
    print("Login with: admin_user / password123")
