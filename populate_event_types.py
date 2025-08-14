#!/usr/bin/env python
"""
Script to populate EventType data for the Legal Case Manager
"""
import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'legal_manager.settings')
django.setup()

from legal_manager.cases.models import EventType

def create_event_types():
    """Create default event types if they don't exist"""
    
    event_types = [
        {'name': 'Seancë Gjyqësore', 'color': '#dc3545', 'is_deadline': False},
        {'name': 'Takim me Klient', 'color': '#28a745', 'is_deadline': False},
        {'name': 'Afat Dorëzimi', 'color': '#ffc107', 'is_deadline': True},
        {'name': 'Konsultim Ligjor', 'color': '#17a2b8', 'is_deadline': False},
        {'name': 'Deadline Gjyqësor', 'color': '#dc3545', 'is_deadline': True},
        {'name': 'Mbledhje Ekipi', 'color': '#6f42c1', 'is_deadline': False},
        {'name': 'Shqyrtim Dokumentesh', 'color': '#fd7e14', 'is_deadline': False},
        {'name': 'Takimi me Prokurorin', 'color': '#20c997', 'is_deadline': False},
        {'name': 'Përgatitur Padi', 'color': '#6c757d', 'is_deadline': False},
        {'name': 'Investigim', 'color': '#343a40', 'is_deadline': False},
    ]
    
    created_count = 0
    for event_type_data in event_types:
        event_type, created = EventType.objects.get_or_create(
            name=event_type_data['name'],
            defaults={
                'color': event_type_data['color'],
                'is_deadline': event_type_data['is_deadline']
            }
        )
        if created:
            created_count += 1
            print(f"[+] Created EventType: {event_type.name}")
        else:
            print(f"[=] EventType already exists: {event_type.name}")
    
    print(f"\nSummary: Created {created_count} new EventTypes")
    print(f"Total EventTypes: {EventType.objects.count()}")

if __name__ == '__main__':
    create_event_types()
