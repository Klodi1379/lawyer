from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from ...models import Client, Case, CaseDocument, CaseEvent
from django.utils import timezone
from datetime import timedelta
import random

User = get_user_model()

class Command(BaseCommand):
    help = 'Create sample data for development and testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=10,
            help='Number of users to create'
        )
        parser.add_argument(
            '--clients',
            type=int,
            default=20,
            help='Number of clients to create'
        )
        parser.add_argument(
            '--cases',
            type=int,
            default=30,
            help='Number of cases to create'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before creating new data'
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing data...')
            User.objects.filter(is_superuser=False).delete()
            Client.objects.all().delete()
            Case.objects.all().delete()

        # Create users
        self.stdout.write(f"Creating {options['users']} users...")
        users = self.create_users(options['users'])
        
        # Create clients
        self.stdout.write(f"Creating {options['clients']} clients...")
        clients = self.create_clients(options['clients'])
        
        # Create cases
        self.stdout.write(f"Creating {options['cases']} cases...")
        cases = self.create_cases(options['cases'], users, clients)
        
        # Create events for some cases
        self.stdout.write("Creating events...")
        self.create_events(cases[:10], users)

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {len(users)} users, '
                f'{len(clients)} clients, and {len(cases)} cases'
            )
        )

    def create_users(self, count):
        users = []
        roles = ['lawyer', 'paralegal', 'admin']
        
        for i in range(count):
            username = f'user{i+1}'
            email = f'user{i+1}@example.com'
            role = random.choice(roles)
            
            user = User.objects.create_user(
                username=username,
                email=email,
                password='testpass123',
                first_name=f'User{i+1}',
                last_name='Test',
                role=role
            )
            users.append(user)
            
        return users

    def create_clients(self, count):
        clients = []
        companies = [
            'ABC Corporation', 'XYZ Ltd', 'Tech Solutions', 'Global Industries',
            'Green Energy Co', 'Digital Media', 'Healthcare Plus', 'Finance Pro',
            'Construction Group', 'Education Services'
        ]
        
        for i in range(count):
            organization = random.choice(companies) if random.choice([True, False]) else ''
            
            client = Client.objects.create(
                full_name=f'Client {i+1}',
                email=f'client{i+1}@example.com',
                phone=f'+35569{random.randint(1000000, 9999999)}',
                address=f'Rruga {i+1}, Tirana, Albania',
                organization=organization
            )
            clients.append(client)
            
        return clients

    def create_cases(self, count, users, clients):
        cases = []
        case_types = ['civil', 'criminal', 'family', 'commercial']
        statuses = ['open', 'in_court', 'appeal', 'closed']
        
        case_titles = [
            'Contract Dispute Resolution',
            'Property Ownership Claim',
            'Employment Termination Case',
            'Insurance Claim Settlement',
            'Intellectual Property Violation',
            'Business Partnership Dissolution',
            'Personal Injury Compensation',
            'Divorce and Custody Proceedings',
            'Real Estate Transaction Issue',
            'Corporate Compliance Review'
        ]
        
        lawyers = [u for u in users if u.role in ['lawyer', 'admin']]
        
        for i in range(count):
            title = random.choice(case_titles)
            case_type = random.choice(case_types)
            status = random.choice(statuses)
            client = random.choice(clients)
            assigned_to = random.choice(lawyers) if random.choice([True, False]) else None
            
            # Create more recent cases
            days_ago = random.randint(1, 365)
            created_at = timezone.now() - timedelta(days=days_ago)
            
            case = Case.objects.create(
                title=f'{title} #{i+1}',
                description=f'Description for case {i+1}. This is a {case_type} case involving {client.full_name}.',
                client=client,
                assigned_to=assigned_to,
                case_type=case_type,
                status=status
            )
            
            # Update created_at manually
            case.created_at = created_at
            case.save()
            
            cases.append(case)
            
        return cases

    def create_events(self, cases, users):
        event_types = [
            'Court Hearing',
            'Client Meeting', 
            'Document Deadline',
            'Filing Deadline',
            'Mediation Session',
            'Settlement Conference',
            'Deposition',
            'Case Review'
        ]
        
        for case in cases:
            # Create 1-3 events per case
            num_events = random.randint(1, 3)
            
            for i in range(num_events):
                title = random.choice(event_types)
                is_deadline = random.choice([True, False])
                
                # Create future events
                days_ahead = random.randint(1, 90)
                starts_at = timezone.now() + timedelta(days=days_ahead)
                
                CaseEvent.objects.create(
                    case=case,
                    title=f'{title} for {case.title}',
                    notes=f'Scheduled {title.lower()} for case {case.uid}',
                    starts_at=starts_at,
                    created_by=case.assigned_to or random.choice(users),
                    is_deadline=is_deadline
                )

    def create_superuser_if_needed(self):
        """Create superuser if it doesn't exist."""
        if not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser(
                username='admin',
                email='admin@example.com',
                password='admin123',
                role='admin'
            )
            self.stdout.write(
                self.style.SUCCESS('Created superuser: admin/admin123')
            )
