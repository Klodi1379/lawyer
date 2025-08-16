# populate_realistic_data.py - Script për popullim të dhënash realiste

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
    """
    Krijon të dhëna realiste për sistemin juridik
    """
    print("Creating data population...")
    
    # 1. Krijoni përdorues të ndryshëm
    create_users()
    
    # 2. Krijoni klientë
    create_clients()
    
    # 3. Krijoni monedha dhe kategori
    create_currencies_and_categories()
    
    # 4. Krijoni raste
    create_cases()
    
    # 5. Krijoni dokumente
    create_documents()
    
    # 6. Krijoni evente
    create_events()
    
    # 7. Krijoni time entries
    create_time_entries()
    
    # 8. Krijoni fatura
    create_invoices()
    
    print("Data population completed!")

def create_users():
    """Krijon përdorues të ndryshëm me role të ndryshme"""
    print("Creating users...")
    
    users_data = [
        {
            'username': 'admin_user',
            'email': 'admin@legalfirm.com',
            'first_name': 'Admin',
            'last_name': 'User',
            'role': 'admin',
            'is_staff': True,
            'is_superuser': True
        },
        {
            'username': 'lawyer_anna',
            'email': 'anna@legalfirm.com',
            'first_name': 'Anna',
            'last_name': 'Rossi',
            'role': 'lawyer'
        },
        {
            'username': 'lawyer_ben',
            'email': 'ben@legalfirm.com',
            'first_name': 'Ben',
            'last_name': 'Smith',
            'role': 'lawyer'
        },
        {
            'username': 'paralegal_sara',
            'email': 'sara@legalfirm.com',
            'first_name': 'Sara',
            'last_name': 'Johnson',
            'role': 'paralegal'
        },
        {
            'username': 'client_mario',
            'email': 'mario@example.com',
            'first_name': 'Mario',
            'last_name': 'Bianchi',
            'role': 'client'
        }
    ]
    
    for user_data in users_data:
        user, created = User.objects.get_or_create(
            username=user_data['username'],
            defaults={
                **user_data,
                'password': make_password('password123'),
                'is_active': True
            }
        )
        if created:
            print(f"  Created user: {user.username} ({user.role})")
            
            # Krijoni profile për secilin përdorues
            UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'bio': f'Professional {user.role} at our law firm',
                    'phone': f'+355 69 {random.randint(100000, 999999)}',
                    'address': f'Address for {user.get_full_name()}'
                }
            )

def create_clients():
    """Krijon klientë të ndryshëm"""
    print("Creating clients...")
    
    clients_data = [
        {
            'full_name': 'ABC Corporation',
            'email': 'contact@abc-corp.com',
            'phone': '+355 4 2123456',
            'address': 'Bulevardi Dëshmorët e Kombit, Tiranë',
            'organization': 'ABC Corporation'
        },
        {
            'full_name': 'Tech Solutions Ltd',
            'email': 'info@techsolutions.al',
            'phone': '+355 4 2234567',
            'address': 'Rruga e Kavajës, Tiranë',
            'organization': 'Tech Solutions Ltd'
        },
        {
            'full_name': 'Elena Marku',
            'email': 'elena.marku@gmail.com',
            'phone': '+355 69 1234567',
            'address': 'Rruga Qemal Stafa, Tiranë',
            'organization': ''
        },
        {
            'full_name': 'Import Export Co.',
            'email': 'office@importexport.al',
            'phone': '+355 4 2345678',
            'address': 'Rruga Mine Peza, Durrës',
            'organization': 'Import Export Co.'
        },
        {
            'full_name': 'Real Estate Group',
            'email': 'contact@realestate.al',
            'phone': '+355 4 2456789',
            'address': 'Bulevardi Bajram Curri, Tiranë',
            'organization': 'Real Estate Group'
        },
        {
            'full_name': 'Agron Doci',
            'email': 'agron.doci@yahoo.com',
            'phone': '+355 69 2345678',
            'address': 'Rruga Fan Noli, Vlorë',
            'organization': ''
        }
    ]
    
    for client_data in clients_data:
        client, created = Client.objects.get_or_create(
            email=client_data['email'],
            defaults=client_data
        )
        if created:
            print(f"  ✓ Created client: {client.full_name}")

def create_currencies_and_categories():
    """Krijon monedha dhe kategori për sistemin"""
    print("💰 Creating currencies and categories...")
    
    # Monedha
    currencies = [
        {'code': 'EUR', 'name': 'Euro', 'symbol': '€'},
        {'code': 'USD', 'name': 'US Dollar', 'symbol': '$'},
        {'code': 'ALL', 'name': 'Albanian Lek', 'symbol': 'L'}
    ]
    
    for curr_data in currencies:
        if hasattr(django.apps.apps.get_model('cases', 'Currency'), 'objects'):
            Currency = django.apps.apps.get_model('cases', 'Currency')
            currency, created = Currency.objects.get_or_create(
                code=curr_data['code'],
                defaults=curr_data
            )
            if created:
                print(f"  ✓ Created currency: {currency.code}")
    
    # Event Types
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
    
    # Document Types
    doc_types = [
        'Contract',
        'Legal Brief',
        'Court Filing',
        'Evidence',
        'Correspondence',
        'Settlement Agreement',
        'Power of Attorney'
    ]
    
    for doc_type_name in doc_types:
        doc_type, created = DocumentType.objects.get_or_create(
            name=doc_type_name
        )
        if created:
            print(f"  ✓ Created document type: {doc_type.name}")
    
    # Document Status
    doc_statuses = [
        'Draft',
        'Under Review',
        'Final',
        'Signed',
        'Filed'
    ]
    
    for status_name in doc_statuses:
        status, created = DocumentStatus.objects.get_or_create(
            name=status_name
        )
        if created:
            print(f"  ✓ Created document status: {status.name}")
    
    # Case Priorities
    priorities = [
        'Low',
        'Medium',
        'High',
        'Urgent'
    ]
    
    for priority_name in priorities:
        priority, created = CasePriority.objects.get_or_create(
            name=priority_name
        )
        if created:
            print(f"  ✓ Created case priority: {priority.name}")

def create_cases():
    """Krijon raste juridike të ndryshme"""
    print("⚖️ Creating legal cases...")
    
    lawyers = User.objects.filter(role='lawyer')
    clients = Client.objects.all()
    priorities = CasePriority.objects.all()
    
    cases_data = [
        {
            'title': 'Contract Dispute - ABC Corporation',
            'description': 'Dispute over breach of contract terms regarding software licensing agreement. Client claims vendor failed to deliver according to specifications.',
            'case_type': 'commercial',
            'status': 'open',
            'estimated_cost': Decimal('15000.00')
        },
        {
            'title': 'Employment Termination Case',
            'description': 'Wrongful termination lawsuit filed by former employee. Claims include discrimination and violation of employment contract.',
            'case_type': 'civil',
            'status': 'in_court',
            'estimated_cost': Decimal('8500.00')
        },
        {
            'title': 'Real Estate Transaction',
            'description': 'Assistance with commercial property acquisition including due diligence, contract negotiation, and closing procedures.',
            'case_type': 'commercial',
            'status': 'open',
            'estimated_cost': Decimal('12000.00')
        },
        {
            'title': 'Family Inheritance Dispute',
            'description': 'Multiple heirs disputing the distribution of family estate. Involves property valuation and will interpretation.',
            'case_type': 'family',
            'status': 'open',
            'estimated_cost': Decimal('6500.00')
        },
        {
            'title': 'Criminal Defense - Fraud Allegations',
            'description': 'Defense against white-collar crime charges including fraud and embezzlement. Complex financial evidence review required.',
            'case_type': 'criminal',
            'status': 'in_court',
            'estimated_cost': Decimal('25000.00')
        },
        {
            'title': 'Intellectual Property Protection',
            'description': 'Patent application and trademark registration for technology startup. Includes prior art research and application filing.',
            'case_type': 'commercial',
            'status': 'closed',
            'estimated_cost': Decimal('7500.00')
        },
        {
            'title': 'Divorce Proceedings',
            'description': 'Contested divorce with child custody and asset division issues. Requires mediation and court proceedings.',
            'case_type': 'family',
            'status': 'appeal',
            'estimated_cost': Decimal('9500.00')
        },
        {
            'title': 'Corporate Compliance Review',
            'description': 'Comprehensive review of corporate governance and regulatory compliance for mid-size company.',
            'case_type': 'commercial',
            'status': 'closed',
            'estimated_cost': Decimal('18000.00')
        }
    ]
    
    for i, case_data in enumerate(cases_data):
        case, created = Case.objects.get_or_create(
            title=case_data['title'],
            defaults={
                **case_data,
                'client': random.choice(clients),
                'assigned_to': random.choice(lawyers) if lawyers else None,
                'priority': random.choice(priorities) if priorities else None,
                'created_at': timezone.now() - timedelta(days=random.randint(1, 180))
            }
        )
        if created:
            print(f"  ✓ Created case: {case.title}")
            
            # Krijoni timeline për rastin
            CaseTimeline.objects.create(
                case=case,
                event_description=f"Case '{case.title}' was created and assigned to {case.assigned_to}",
                user=case.assigned_to
            )

def create_documents():
    """Krijon dokumente për rastet"""
    print("📄 Creating documents...")
    
    cases = Case.objects.all()
    users = User.objects.filter(role__in=['lawyer', 'paralegal'])
    doc_types = DocumentType.objects.all()
    doc_statuses = DocumentStatus.objects.all()
    
    documents_per_case = 2  # Mesatarisht 2 dokumente për rast
    
    for case in cases:
        for i in range(random.randint(1, documents_per_case + 1)):
            doc_type = random.choice(doc_types) if doc_types else None
            status = random.choice(doc_statuses) if doc_statuses else None
            uploader = random.choice(users) if users else None
            
            # Krijoni dokument pa file real (do të përdorim placeholder)
            document = CaseDocument.objects.create(
                case=case,
                title=f"{doc_type.name if doc_type else 'Document'} - {case.title[:30]}",
                doc_type=doc_type,
                status=status,
                uploaded_by=uploader,
                version=random.randint(1, 3),
                created_at=timezone.now() - timedelta(days=random.randint(1, 60))
            )
            
            # Krijoni një file placeholder (mund ta zëvendësosh me file real)
            document.file.name = f"documents/sample_{document.id}_{doc_type.name.lower().replace(' ', '_') if doc_type else 'document'}.pdf"
            document.save()
            
            print(f"  ✓ Created document: {document.title}")

def create_events():
    """Krijon evente dhe takime për rastet"""
    print("📅 Creating events...")
    
    cases = Case.objects.all()
    users = User.objects.filter(role__in=['lawyer', 'paralegal'])
    event_types = EventType.objects.all()
    
    # Krijoni evente të së kaluarës, sot dhe të ardhmes
    for case in cases:
        # Events të së kaluarës
        for i in range(random.randint(1, 3)):
            event_type = random.choice(event_types) if event_types else None
            creator = random.choice(users) if users else None
            
            past_date = timezone.now() - timedelta(days=random.randint(1, 90))
            
            event = CaseEvent.objects.create(
                case=case,
                title=f"{event_type.name if event_type else 'Event'} - {case.title[:30]}",
                description=f"Past event for case {case.uid}. This was an important milestone in the case progress.",
                event_type=event_type,
                priority=random.choice(['low', 'medium', 'high', 'urgent']),
                starts_at=past_date,
                ends_at=past_date + timedelta(hours=random.randint(1, 4)),
                location=random.choice(['Court Room 1', 'Office Conference Room', 'Client Office', 'Online Meeting']),
                created_by=creator,
                is_deadline=event_type.is_deadline if event_type else random.choice([True, False])
            )
            
            # Shto disa attendees
            if random.choice([True, False]):
                attendees = random.sample(list(users), min(len(users), random.randint(1, 3)))
                event.attendees.set(attendees)
            
            print(f"  ✓ Created past event: {event.title}")
        
        # Events të ardhshëm
        for i in range(random.randint(1, 4)):
            event_type = random.choice(event_types) if event_types else None
            creator = random.choice(users) if users else None
            
            future_date = timezone.now() + timedelta(days=random.randint(1, 60))
            
            event = CaseEvent.objects.create(
                case=case,
                title=f"{event_type.name if event_type else 'Upcoming Event'} - {case.title[:30]}",
                description=f"Upcoming event for case {case.uid}. Preparation and documentation required.",
                event_type=event_type,
                priority=random.choice(['low', 'medium', 'high', 'urgent']),
                starts_at=future_date,
                ends_at=future_date + timedelta(hours=random.randint(1, 4)),
                location=random.choice(['Court Room 2', 'Main Conference Room', 'Client Location', 'Video Conference']),
                reminder_minutes=random.choice([30, 60, 120, 1440]),  # 30min, 1h, 2h, 1day
                created_by=creator,
                is_deadline=event_type.is_deadline if event_type else random.choice([True, False])
            )
            
            # Shto attendees
            if random.choice([True, False]):
                attendees = random.sample(list(users), min(len(users), random.randint(1, 2)))
                event.attendees.set(attendees)
            
            print(f"  ✓ Created future event: {event.title}")

def create_time_entries():
    """Krijon time entries për raste dhe përdorues"""
    print("⏱️ Creating time entries...")
    
    cases = Case.objects.all()
    users = User.objects.filter(role__in=['lawyer', 'paralegal'])
    
    # Krijoni time entries për 60 ditët e fundit
    for case in cases:
        for day in range(60):
            date = timezone.now() - timedelta(days=day)
            
            # Ka mundësi që të mos ketë punë çdo ditë
            if random.random() > 0.7:  # 30% chance of work each day
                continue
            
            # Zgjedh një përdorues që punoi në këtë rast
            if case.assigned_to:
                worker = case.assigned_to
            else:
                worker = random.choice(users) if users else None
            
            if not worker:
                continue
            
            # Krijoni 1-3 time entries për këtë ditë
            for _ in range(random.randint(1, 3)):
                minutes = random.randint(30, 480)  # 30 minuta deri në 8 orë
                
                activities = [
                    "Research and case analysis",
                    "Document preparation and review",
                    "Client consultation and communication",
                    "Court preparation and filing",
                    "Legal writing and correspondence",
                    "Evidence gathering and analysis",
                    "Contract review and negotiation",
                    "Meeting with opposing counsel",
                    "Case strategy development",
                    "Administrative tasks"
                ]
                
                TimeEntry.objects.create(
                    case=case,
                    user=worker,
                    minutes=minutes,
                    description=random.choice(activities),
                    created_at=date
                )
    
    print(f"  ✓ Created time entries for all cases")

def create_invoices():
    """Krijon fatura për rastet"""
    print("💰 Creating invoices...")
    
    cases = Case.objects.all()
    
    for case in cases:
        # Krijoni 1-2 fatura për rast
        for i in range(random.randint(1, 2)):
            # Llogarit totalin bazuar në time entries
            time_entries = TimeEntry.objects.filter(case=case)
            total_minutes = sum([entry.minutes for entry in time_entries])
            total_hours = total_minutes / 60
            
            # Tarifë 150 EUR për orë (mesatarisht)
            hourly_rate = random.randint(120, 200)
            total_amount = Decimal(str(total_hours * hourly_rate))
            
            # Disa fatura janë të paguara
            is_paid = random.choice([True, False, False])  # 33% chance të jetë e paguar
            
            invoice_date = timezone.now() - timedelta(days=random.randint(1, 90))
            
            invoice = Invoice.objects.create(
                case=case,
                issued_to=case.client,
                total_amount=total_amount,
                paid=is_paid,
                issued_at=invoice_date
            )
            
            print(f"  ✓ Created invoice: €{total_amount:.2f} for {case.title[:30]}...")

def cleanup_existing_data():
    """Pastron të dhënat e mëparshme (opsionale)"""
    print("🧹 Cleaning up existing data...")
    
    # Uncomment nëse do të pastrosh të dhënat e mëparshme
    # TimeEntry.objects.all().delete()
    # Invoice.objects.all().delete()
    # CaseEvent.objects.all().delete()
    # CaseDocument.objects.all().delete()
    # Case.objects.all().delete()
    # Client.objects.all().delete()
    # User.objects.filter(is_superuser=False).delete()

if __name__ == '__main__':
    print("Legal Case Management Data Population")
    print("=" * 50)
    
    # cleanup_existing_data()  # Uncomment nëse do të pastrosh të dhënat
    create_sample_data()
    
    print("\nFinal Statistics:")
    print(f"Users: {User.objects.count()}")
    print(f"Clients: {Client.objects.count()}")
    print(f"Cases: {Case.objects.count()}")
    print(f"Documents: {CaseDocument.objects.count()}")
    print(f"Events: {CaseEvent.objects.count()}")
    print(f"Time Entries: {TimeEntry.objects.count()}")
    print(f"Invoices: {Invoice.objects.count()}")
    
    print("\nDatabase populated successfully!")
    print("You can now:")
    print("- Log in as admin_user/password123")
    print("- View analytics dashboard")
    print("- Check calendar events")
    print("- Explore case management features")
