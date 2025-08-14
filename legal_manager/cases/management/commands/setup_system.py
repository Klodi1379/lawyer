from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.core.management import call_command
import os

User = get_user_model()

class Command(BaseCommand):
    help = 'Initialize the Legal Case Management System'

    def add_arguments(self, parser):
        parser.add_argument(
            '--with-sample-data',
            action='store_true',
            help='Create sample data after setup'
        )
        parser.add_argument(
            '--superuser-username',
            type=str,
            default='admin',
            help='Superuser username (default: admin)'
        )
        parser.add_argument(
            '--superuser-email',
            type=str,
            default='admin@legalsystem.com',
            help='Superuser email'
        )
        parser.add_argument(
            '--superuser-password',
            type=str,
            default='admin123',
            help='Superuser password (default: admin123)'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🏛️  Initializing Legal Case Management System...')
        )

        # Check if database is ready
        self.stdout.write('📋 Checking database connection...')
        try:
            call_command('check', '--database', 'default')
            self.stdout.write(self.style.SUCCESS('✅ Database connection OK'))
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Database connection failed: {e}')
            )
            return

        # Run migrations
        self.stdout.write('🔄 Running database migrations...')
        call_command('migrate', verbosity=0)
        self.stdout.write(self.style.SUCCESS('✅ Migrations completed'))

        # Collect static files (for production)
        if not options.get('verbosity', 1):
            self.stdout.write('📦 Collecting static files...')
            call_command('collectstatic', interactive=False, verbosity=0)
            self.stdout.write(self.style.SUCCESS('✅ Static files collected'))

        # Create superuser if it doesn't exist
        superuser_username = options['superuser_username']
        superuser_email = options['superuser_email']
        superuser_password = options['superuser_password']

        if not User.objects.filter(username=superuser_username).exists():
            self.stdout.write('👤 Creating superuser account...')
            User.objects.create_superuser(
                username=superuser_username,
                email=superuser_email,
                password=superuser_password,
                role='admin'
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Superuser created: {superuser_username} / {superuser_password}'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'⚠️  Superuser {superuser_username} already exists')
            )

        # Create sample data if requested
        if options['with_sample_data']:
            self.stdout.write('🎭 Creating sample data...')
            call_command('seed_data', users=5, clients=10, cases=15)
            self.stdout.write(self.style.SUCCESS('✅ Sample data created'))

        # Display summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(
            self.style.SUCCESS('🎉 Legal Case Management System initialized successfully!')
        )
        self.stdout.write('\n📊 System Summary:')
        self.stdout.write(f'   Users: {User.objects.count()}')
        
        # Import models here to avoid circular imports
        from ...models import Client, Case
        self.stdout.write(f'   Clients: {Client.objects.count()}')
        self.stdout.write(f'   Cases: {Case.objects.count()}')

        self.stdout.write('\n🔐 Admin Access:')
        self.stdout.write(f'   Username: {superuser_username}')
        self.stdout.write(f'   Password: {superuser_password}')
        self.stdout.write(f'   Admin URL: http://localhost:8000/admin/')

        self.stdout.write('\n🌐 Application URLs:')
        self.stdout.write('   Web Interface: http://localhost:8000/')
        self.stdout.write('   API Documentation: http://localhost:8000/api/')

        self.stdout.write('\n⚠️  Important Notes:')
        self.stdout.write('   - Change the superuser password in production')
        self.stdout.write('   - Configure your .env file with production settings')
        self.stdout.write('   - Set up your LLM API key for AI features')
        
        if options['with_sample_data']:
            self.stdout.write('   - Sample data created for testing (remove in production)')

        self.stdout.write('\n🚀 Ready to start! Run: python manage.py runserver')
        self.stdout.write('='*60)
