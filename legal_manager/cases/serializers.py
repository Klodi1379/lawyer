from rest_framework import serializers
from .models import (
    User, UserProfile, Client, Case, CaseDocument, 
    CaseEvent, TimeEntry, Invoice, AuditLog, UserAuditLog
)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'is_2fa_enabled', 'date_joined']
        read_only_fields = ['id', 'date_joined']

class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = UserProfile
        fields = ['user', 'bio', 'profile_picture', 'phone', 'address', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = '__all__'

class CaseDocumentSerializer(serializers.ModelSerializer):
    uploaded_by = UserSerializer(read_only=True)
    
    class Meta:
        model = CaseDocument
        fields = '__all__'

class CaseEventSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = CaseEvent
        fields = '__all__'

class TimeEntrySerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = TimeEntry
        fields = '__all__'

class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = '__all__'

class CaseSerializer(serializers.ModelSerializer):
    documents = CaseDocumentSerializer(many=True, read_only=True)
    events = CaseEventSerializer(many=True, read_only=True)
    time_entries = TimeEntrySerializer(many=True, read_only=True)
    invoices = InvoiceSerializer(many=True, read_only=True)
    client = ClientSerializer(read_only=True)
    assigned_to = UserSerializer(read_only=True)
    
    class Meta:
        model = Case
        fields = [
            'id', 'uid', 'title', 'description', 'client', 'assigned_to', 
            'case_type', 'status', 'documents', 'events', 'time_entries', 
            'invoices', 'created_at', 'updated_at'
        ]

class AuditLogSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = AuditLog
        fields = '__all__'

class UserAuditLogSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = UserAuditLog
        fields = '__all__'
