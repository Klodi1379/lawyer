#!/usr/bin/env python
"""Script to create an admin user"""
import os
import sys
import django

# Set the settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'legal_manager.settings')

# Add the project directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'legal_manager'))

# Setup Django
django.setup()

from cases.models import User

def create_admin():
    username = 'admin'
    email = 'admin@example.com'
    password = 'admin123'
    
    if not User.objects.filter(username=username).exists():
        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            role='admin'
        )
        print(f"Admin user created successfully!")
        print(f"Username: {username}")
        print(f"Password: {password}")
        print(f"Email: {email}")
    else:
        print("Admin user already exists!")

if __name__ == '__main__':
    create_admin()
