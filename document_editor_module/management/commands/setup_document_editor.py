"""
Management command për setup inicial të Document Editor Module
Krijn data të nevojshme: document types, statuses, default templates
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction

from ...models.document_models import DocumentType, DocumentStatus, DocumentTemplate
from ...advanced_features.workflow_system import WorkflowTemplate

User = get_user_model()

class Command(BaseCommand):
    help = 'Setup Document Editor Module with initial data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-templates',
            action='store_true',
            help='Skip creating default templates'
        )
        parser.add_argument(
            '--admin-user',
            type=str,
            help='Username of admin user to assign as template creator'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Setting up Document Editor Module...'))
        
        try:
            with transaction.atomic():
                # Create document types
                self.create_document_types()
                
                # Create document statuses
                self.create_document_statuses()
                
                # Create default templates if not skipped
                if not options['skip_templates']:
                    admin_user = self.get_admin_user(options.get('admin_user'))
                    if admin_user:
                        self.create_default_templates(admin_user)
                        self.create_workflow_templates(admin_user)
                
                self.stdout.write(
                    self.style.SUCCESS('Document Editor Module setup completed successfully!')
                )
                
        except Exception as e:
            raise CommandError(f'Setup failed: {str(e)}')

    def create_document_types(self):
        """Create default document types"""
        self.stdout.write('Creating document types...')
        
        document_types = [
            {
                'name': 'Padi Civile',
                'description': 'Padi për çështje civile',
                'requires_signature': True,
                'is_legal_document': True
            },
            {
                'name': 'Ankesë',
                'description': 'Ankesë kundër vendimeve',
                'requires_signature': True,
                'is_legal_document': True
            },
            {
                'name': 'Kontratë',
                'description': 'Kontrata dhe marrëveshje',
                'requires_signature': True,
                'is_legal_document': True
            },
            {
                'name': 'Kërkesë',
                'description': 'Kërkesa të ndryshme',
                'requires_signature': False,
                'is_legal_document': True
            },
            {
                'name': 'Vendim',
                'description': 'Vendime gjyqësore',
                'requires_signature': False,
                'is_legal_document': True
            },
            {
                'name': 'Raport',
                'description': 'Raporte dhe analizë',
                'requires_signature': False,
                'is_legal_document': False
            },
            {
                'name': 'Memorandum',
                'description': 'Memorandume dhe shënime',
                'requires_signature': False,
                'is_legal_document': False
            }
        ]
        
        created_count = 0
        for doc_type_data in document_types:
            doc_type, created = DocumentType.objects.get_or_create(
                name=doc_type_data['name'],
                defaults=doc_type_data
            )
            if created:
                created_count += 1
                self.stdout.write(f'  Created: {doc_type.name}')
        
        self.stdout.write(f'Created {created_count} document types')

    def create_document_statuses(self):
        """Create default document statuses"""
        self.stdout.write('Creating document statuses...')
        
        statuses = [
            {'name': 'Draft', 'description': 'Dokument në hartim', 'color': '#6c757d', 'order': 1},
            {'name': 'Review', 'description': 'Në rishikim', 'color': '#ffc107', 'order': 2},
            {'name': 'Approved', 'description': 'I miratuar', 'color': '#28a745', 'order': 3},
            {'name': 'Signed', 'description': 'I nënshkruar', 'color': '#17a2b8', 'order': 4, 'is_final': True},
            {'name': 'Rejected', 'description': 'I refuzuar', 'color': '#dc3545', 'order': 5, 'is_final': True},
            {'name': 'Archived', 'description': 'I arkivuar', 'color': '#868e96', 'order': 6, 'is_final': True}
        ]
        
        created_count = 0
        for status_data in statuses:
            status, created = DocumentStatus.objects.get_or_create(
                name=status_data['name'],
                defaults=status_data
            )
            if created:
                created_count += 1
                self.stdout.write(f'  Created: {status.name}')
        
        self.stdout.write(f'Created {created_count} document statuses')

    def get_admin_user(self, username=None):
        """Get admin user for template creation"""
        if username:
            try:
                user = User.objects.get(username=username)
                if user.is_staff or getattr(user, 'role', '') == 'admin':
                    return user
                else:
                    self.stdout.write(
                        self.style.WARNING(f'User {username} is not admin. Skipping template creation.')
                    )
                    return None
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(f'User {username} not found. Skipping template creation.')
                )
                return None
        else:
            # Try to find any admin user
            admin_users = User.objects.filter(is_staff=True)
            if admin_users.exists():
                return admin_users.first()
            
            # Try users with admin role
            if hasattr(User, 'role'):
                admin_role_users = User.objects.filter(role='admin')
                if admin_role_users.exists():
                    return admin_role_users.first()
        
        self.stdout.write(
            self.style.WARNING('No admin user found. Skipping template creation.')
        )
        return None

    def create_default_templates(self, admin_user):
        """Create default document templates"""
        self.stdout.write('Creating default templates...')
        
        templates = [
            {
                'name': 'Padi Civile - Bazë',
                'category': 'Padi Civile',
                'content': '''PADI CIVILE

GJYKATA E RRETHIT GJYQËSOR {{ court_name }}

PADITËS: {{ plaintiff_name }}
me banim në {{ plaintiff_address }}

KUNDËR

TË PADITURIT: {{ defendant_name }}
me banim në {{ defendant_address }}

OBJEKT: {{ case_object }}
VLERA: {{ case_value }} {{ currency }}

NDERUAR GJYKATË,

Paraqes këtë padi civile për sa vijon:

FAKTE:
{{ case_facts }}

BAZA LIGJORE:
Bazuar në {{ legal_basis }}, kërkoj:

KËRKESA:
{{ case_request }}

PROVA:
{{ evidence_list }}

Për sa më sipër, lutem respektivisht që gjykata:
{{ court_request }}

Me respekt,
{{ lawyer_name }}
Avokat
{{ date | legal_date }}''',
                'variables': {
                    'court_name': 'text',
                    'plaintiff_name': 'text', 
                    'plaintiff_address': 'text',
                    'defendant_name': 'text',
                    'defendant_address': 'text',
                    'case_object': 'text',
                    'case_value': 'number',
                    'currency': 'choice',
                    'case_facts': 'text',
                    'legal_basis': 'text',
                    'case_request': 'text',
                    'evidence_list': 'text',
                    'court_request': 'text',
                    'lawyer_name': 'text',
                    'date': 'date'
                }
            },
            {
                'name': 'Kontratë Shërbimi - Standard',
                'category': 'Kontratë',
                'content': '''KONTRATË SHËRBIMI

Palët:
1. {{ provider_name }}, me seli në {{ provider_address }} (Ofruesi)
2. {{ client_name }}, me seli në {{ client_address }} (Klienti)

vendosën të lidhin këtë kontratë:

NENI 1 - OBJEKTI
{{ service_description }}

NENI 2 - AFATET
Kontrata hyn në fuqi më {{ start_date | legal_date }} dhe përfundon më {{ end_date | legal_date }}.

NENI 3 - ÇMIMI
Çmimi i shërbimit është {{ price }} {{ currency }}.
Pagesa do të kryhet {{ payment_terms }}.

NENI 4 - OBLIGIMET E PALËVE
Ofruesi angazhohet:
{{ provider_obligations }}

Klienti angazhohet:
{{ client_obligations }}

NENI 5 - NDRYSHIMI DHE ZGJIDHJA
{{ modification_clause }}

NENI 6 - DISPOZITA TË PËRGJITHSHME
{{ general_provisions }}

Kjo kontratë u lidh në {{ contract_place }} më {{ contract_date | legal_date }}.

PALËT:
Ofruesi: ________________    Klienti: ________________
{{ provider_name }}         {{ client_name }}''',
                'variables': {
                    'provider_name': 'text',
                    'provider_address': 'text',
                    'client_name': 'text', 
                    'client_address': 'text',
                    'service_description': 'text',
                    'start_date': 'date',
                    'end_date': 'date',
                    'price': 'number',
                    'currency': 'choice',
                    'payment_terms': 'text',
                    'provider_obligations': 'text',
                    'client_obligations': 'text',
                    'modification_clause': 'text',
                    'general_provisions': 'text',
                    'contract_place': 'text',
                    'contract_date': 'date'
                }
            }
        ]
        
        created_count = 0
        for template_data in templates:
            template, created = DocumentTemplate.objects.get_or_create(
                name=template_data['name'],
                defaults={
                    **template_data,
                    'created_by': admin_user
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f'  Created: {template.name}')
        
        self.stdout.write(f'Created {created_count} templates')

    def create_workflow_templates(self, admin_user):
        """Create default workflow templates"""
        self.stdout.write('Creating workflow templates...')
        
        # Get document types
        try:
            padi_type = DocumentType.objects.get(name='Padi Civile')
            kontrate_type = DocumentType.objects.get(name='Kontratë')
        except DocumentType.DoesNotExist:
            self.stdout.write('Document types not found. Skipping workflow templates.')
            return
        
        workflows = [
            {
                'name': 'Workflow Standard për Padi',
                'description': 'Workflow standard për procesimin e padive civile',
                'document_types': [padi_type],
                'steps_config': [
                    {
                        'name': 'Hartim i Draft',
                        'type': 'review',
                        'description': 'Hartimi inicial i padisë',
                        'deadline_hours': 48,
                        'assigned_roles': ['lawyer'],
                        'allowed_actions': ['complete', 'request_changes']
                    },
                    {
                        'name': 'Rishikim Ligjor',
                        'type': 'review',
                        'description': 'Rishikim i aspekteve ligjore',
                        'deadline_hours': 24,
                        'assigned_roles': ['lawyer'],
                        'allowed_actions': ['approve', 'reject', 'request_changes']
                    },
                    {
                        'name': 'Miratim Final',
                        'type': 'approval',
                        'description': 'Miratimi final para dorëzimit',
                        'deadline_hours': 12,
                        'assigned_roles': ['admin'],
                        'allowed_actions': ['approve', 'reject']
                    }
                ]
            },
            {
                'name': 'Workflow për Kontrata',
                'description': 'Workflow për hartim dhe miratim kontratash',
                'document_types': [kontrate_type],
                'steps_config': [
                    {
                        'name': 'Hartim Kontrate',
                        'type': 'review',
                        'description': 'Hartimi i kontratës bazuar në kërkesat',
                        'deadline_hours': 72,
                        'assigned_roles': ['lawyer'],
                        'allowed_actions': ['complete']
                    },
                    {
                        'name': 'Kontroll Klauzolash',
                        'type': 'review',
                        'description': 'Kontrolli i klauzlave dhe termave',
                        'deadline_hours': 24,
                        'assigned_roles': ['lawyer'],
                        'allowed_actions': ['approve', 'request_changes']
                    },
                    {
                        'name': 'Nënshkrim',
                        'type': 'signature',
                        'description': 'Nënshkrimi elektronik i kontratës',
                        'deadline_hours': 168,  # 1 javë
                        'assigned_roles': ['client'],
                        'allowed_actions': ['approve', 'reject']
                    }
                ]
            }
        ]
        
        created_count = 0
        for workflow_data in workflows:
            document_types = workflow_data.pop('document_types')
            
            workflow, created = WorkflowTemplate.objects.get_or_create(
                name=workflow_data['name'],
                defaults={
                    **workflow_data,
                    'created_by': admin_user
                }
            )
            
            if created:
                workflow.document_types.set(document_types)
                created_count += 1
                self.stdout.write(f'  Created: {workflow.name}')
        
        self.stdout.write(f'Created {created_count} workflow templates')
