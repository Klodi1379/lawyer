import os
from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'legal_manager.settings')

app = Celery('legal_manager')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Periodic tasks configuration
from celery.schedules import crontab

app.conf.beat_schedule = {
    'check-upcoming-deadlines': {
        'task': 'cases.tasks.check_upcoming_deadlines',
        'schedule': crontab(hour=9, minute=0),  # Run daily at 9 AM
    },
    'cleanup-old-audit-logs': {
        'task': 'cases.tasks.cleanup_old_audit_logs',
        'schedule': crontab(hour=2, minute=0, day_of_week=1),  # Run weekly on Monday at 2 AM
    },
}

app.conf.timezone = 'Europe/Tirane'

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
