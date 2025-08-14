# serializers_improved.py - Serializers për strukturën e re
from rest_framework import serializers
from .models_improved import (
    User, Client, Case, Document, DocumentCategory, DocumentType, 
    DocumentStatus, DocumentCaseRelation, DocumentAccess
)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'first_name', 'last_name']
        read_only_fields = ['id']

class ClientSerializer(serializers.ModelSerializer):
    cases_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Client
        fields = '__all__'
    
    def get_cases_count(self, obj):
        return obj.cases.count()

class DocumentCategorySerializer(serializers.ModelSerializer):
    types_count = serializers.SerializerMethodField()
    
    class Meta:
        model = DocumentCategory
        fields = '__all__'
    
    def get_types_count(self, obj):
        return obj.types.count()

class DocumentTypeSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = DocumentType
        fields = '__all__'

class DocumentStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentStatus
        fields = '__all__'

class DocumentAccessSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    granted_by_username = serializers.CharField(source='granted_by.username', read_only=True)
    
    class Meta:
        model = DocumentAccess
        fields = '__all__'

class DocumentCaseRelationSerializer(serializers.ModelSerializer):
    case_title = serializers.CharField(source='case.title', read_only=True)
    case_uid = serializers.CharField(source='case.uid', read_only=True)
    added_by_username = serializers.CharField(source='added_by.username', read_only=True)
    
    class Meta:
        model = DocumentCaseRelation
        fields = '__all__'

class DocumentSerializer(serializers.ModelSerializer):
    # Related data
    document_type_name = serializers.CharField(source='document_type.name', read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_color = serializers.CharField(source='status.color', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    uploaded_by_username = serializers.CharField(source='uploaded_by.username', read_only=True)
    
    # Cases related to this document
    related_cases = DocumentCaseRelationSerializer(source='documentcaserelation_set', many=True, read_only=True)
    
    # Access controls
    access_controls = DocumentAccessSerializer(many=True, read_only=True)
    
    # File info
    file_url = serializers.SerializerMethodField()
    file_size_formatted = serializers.SerializerMethodField()
    
    # Computed fields
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    can_download = serializers.SerializerMethodField()
    
    class Meta:
        model = Document
        fields = [
            'id', 'uid', 'title', 'description', 'file', 'file_url', 
            'file_size', 'file_size_formatted', 'file_type',
            'document_type', 'document_type_name', 'status', 'status_name', 'status_color',
            'version', 'parent_document', 'is_template', 'template_variables',
            'metadata', 'tags', 'created_by', 'created_by_username',
            'uploaded_by', 'uploaded_by_username', 'is_confidential', 'access_level',
            'created_at', 'updated_at', 'last_accessed',
            'related_cases', 'access_controls',
            'can_edit', 'can_delete', 'can_download'
        ]
        read_only_fields = ['id', 'uid', 'file_size', 'file_type', 'created_at', 'updated_at']
    
    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None
    
    def get_file_size_formatted(self, obj):
        if not obj.file_size:
            return "Unknown"
        
        # Convert bytes to human readable format
        for unit in ['B', 'KB', 'MB', 'GB']:
            if obj.file_size < 1024.0:
                return f"{obj.file_size:.1f} {unit}"
            obj.file_size /= 1024.0
        return f"{obj.file_size:.1f} TB"
    
    def get_can_edit(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        
        user = request.user
        # Admin mund të editojë gjithçka
        if user.role == 'admin':
            return True
        
        # Krijuesi mund të editojë dokumentin e vet
        if obj.created_by == user:
            return True
        
        # Kontrollo access controls specifike
        access = obj.access_controls.filter(user=user).first()
        if access:
            return access.can_edit
        
        # Kontrollo access controls bazuar në role
        role_access = obj.access_controls.filter(role=user.role).first()
        if role_access:
            return role_access.can_edit
        
        return False
    
    def get_can_delete(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        
        user = request.user
        # Vetëm admin ose krijuesi mund të fshijë
        return user.role == 'admin' or obj.created_by == user
    
    def get_can_download(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        
        user = request.user
        # Admin mund të shkarkojë gjithçka
        if user.role == 'admin':
            return True
        
        # Kontrollo access level
        if obj.access_level == 'public':
            return True
        
        if obj.access_level == 'internal' and user.role in ['lawyer', 'paralegal']:
            return True
        
        # Kontrollo access controls specifike
        access = obj.access_controls.filter(user=user).first()
        if access:
            return access.can_download
        
        # Kontrollo access controls bazuar në role
        role_access = obj.access_controls.filter(role=user.role).first()
        if role_access:
            return role_access.can_download
        
        return False

class CaseSerializer(serializers.ModelSerializer):
    # Related data
    client_name = serializers.CharField(source='client.full_name', read_only=True)
    assigned_to_username = serializers.CharField(source='assigned_to.username', read_only=True)
    
    # Documents related to this case
    documents = serializers.SerializerMethodField()
    documents_count = serializers.SerializerMethodField()
    
    # Events count
    events_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Case
        fields = [
            'id', 'uid', 'title', 'description', 'client', 'client_name',
            'assigned_to', 'assigned_to_username', 'case_type', 'status',
            'created_at', 'updated_at', 'documents', 'documents_count', 'events_count'
        ]
        read_only_fields = ['id', 'uid', 'created_at', 'updated_at']
    
    def get_documents(self, obj):
        # Merr dokumentet e lidhura me këtë rast
        relations = DocumentCaseRelation.objects.filter(case=obj).select_related('document')
        documents_data = []
        
        for relation in relations:
            doc = relation.document
            documents_data.append({
                'id': doc.id,
                'uid': doc.uid,
                'title': doc.title,
                'document_type': doc.document_type.name,
                'status': doc.status.name,
                'relationship_type': relation.relationship_type,
                'created_at': doc.created_at,
            })
        
        return documents_data
    
    def get_documents_count(self, obj):
        return DocumentCaseRelation.objects.filter(case=obj).count()
    
    def get_events_count(self, obj):
        return obj.events.count()

# Serializer për bulk operations
class DocumentBulkSerializer(serializers.Serializer):
    document_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=100
    )
    action = serializers.ChoiceField(choices=[
        ('delete', 'Delete'),
        ('change_status', 'Change Status'),
        ('add_to_case', 'Add to Case'),
        ('remove_from_case', 'Remove from Case'),
        ('change_access_level', 'Change Access Level'),
    ])
    
    # Optional parameters based on action
    new_status = serializers.IntegerField(required=False)
    case_id = serializers.IntegerField(required=False)
    relationship_type = serializers.CharField(required=False)
    access_level = serializers.CharField(required=False)

# Serializer për template-based document creation
class DocumentFromTemplateSerializer(serializers.Serializer):
    template_id = serializers.IntegerField()
    title = serializers.CharField(max_length=255)
    case_id = serializers.IntegerField(required=False)
    template_variables = serializers.JSONField(required=False)
    
    def validate_template_id(self, value):
        try:
            template = Document.objects.get(id=value, is_template=True)
            return value
        except Document.DoesNotExist:
            raise serializers.ValidationError("Template not found or not a template")
    
    def validate_case_id(self, value):
        if value:
            try:
                Case.objects.get(id=value)
                return value
            except Case.DoesNotExist:
                raise serializers.ValidationError("Case not found")
        return value
