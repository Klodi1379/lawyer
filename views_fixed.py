# views_fixed.py - Views të rregulluara për gabimin e slice
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, JsonResponse, Http404
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q, Count, Prefetch
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
import mimetypes
import os

from .models_improved import (
    User, Client, Case, Document, DocumentCategory, DocumentType,
    DocumentStatus, DocumentCaseRelation, DocumentAccess, DocumentAuditLog
)
from .serializers_improved import (
    UserSerializer, ClientSerializer, CaseSerializer, DocumentSerializer,
    DocumentCategorySerializer, DocumentTypeSerializer, DocumentStatusSerializer,
    DocumentCaseRelationSerializer, DocumentAccessSerializer, DocumentBulkSerializer,
    DocumentFromTemplateSerializer
)

# ==========================================
# CUSTOM PERMISSIONS (UNCHANGED)
# ==========================================

class IsLawyerOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return hasattr(request.user, 'role') and request.user.role in ['lawyer', 'admin']

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        if hasattr(obj, 'assigned_to'):
            return request.user == obj.assigned_to or request.user.role == 'admin'
        
        if hasattr(obj, 'created_by'):
            return request.user == obj.created_by or request.user.role == 'admin'
        
        return request.user.role == 'admin'

class DocumentPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user
        
        if user.role == 'admin':
            return True
        
        if obj.created_by == user:
            return True
        
        if request.method in permissions.SAFE_METHODS:
            if obj.access_level == 'public':
                return True
            
            if obj.access_level == 'internal' and user.role in ['lawyer', 'paralegal']:
                return True
        
        access = obj.access_controls.filter(user=user).first()
        if access:
            if request.method in permissions.SAFE_METHODS:
                return access.can_view
            elif request.method in ['PUT', 'PATCH']:
                return access.can_edit
            elif request.method == 'DELETE':
                return access.can_delete
        
        role_access = obj.access_controls.filter(role=user.role).first()
        if role_access:
            if request.method in permissions.SAFE_METHODS:
                return role_access.can_view
            elif request.method in ['PUT', 'PATCH']:
                return role_access.can_edit
            elif request.method == 'DELETE':
                return role_access.can_delete
        
        return False

# ==========================================
# VIEWSETS (FIXED)
# ==========================================

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.role == 'admin':
            return User.objects.all()
        return User.objects.filter(id=self.request.user.id)

class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [IsLawyerOrReadOnly]
    
    def get_queryset(self):
        queryset = Client.objects.prefetch_related('cases')
        
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search) |
                Q(email__icontains=search) |
                Q(organization__icontains=search)
            )
        
        return queryset

class CaseViewSet(viewsets.ModelViewSet):
    queryset = Case.objects.all()
    serializer_class = CaseSerializer
    permission_classes = [IsLawyerOrReadOnly]
    
    def get_queryset(self):
        queryset = Case.objects.select_related('client', 'assigned_to').prefetch_related(
            Prefetch('documentcaserelation_set__document')
        )
        
        # Filtro për klientët
        if self.request.user.role == 'client':
            queryset = queryset.filter(client__user=self.request.user)
        
        # Filtrime të tjera
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        case_type_filter = self.request.query_params.get('case_type', None)
        if case_type_filter:
            queryset = queryset.filter(case_type=case_type_filter)
        
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(uid__icontains=search) |
                Q(description__icontains=search)
            )
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def add_document(self, request, pk=None):
        case = self.get_object()
        document_id = request.data.get('document_id')
        relationship_type = request.data.get('relationship_type', 'primary')
        
        try:
            document = Document.objects.get(id=document_id)
        except Document.DoesNotExist:
            return Response({'error': 'Document not found'}, status=status.HTTP_404_NOT_FOUND)
        
        relation, created = DocumentCaseRelation.objects.get_or_create(
            document=document,
            case=case,
            relationship_type=relationship_type,
            defaults={'added_by': request.user}
        )
        
        if created:
            DocumentAuditLog.objects.create(
                document=document,
                user=request.user,
                action='linked_to_case',
                metadata={'case_id': case.id, 'case_title': case.title}
            )
            
            return Response({'message': 'Document added to case successfully'})
        else:
            return Response({'message': 'Document already linked to this case'})

class DocumentCategoryViewSet(viewsets.ModelViewSet):
    queryset = DocumentCategory.objects.annotate(types_count=Count('types'))
    serializer_class = DocumentCategorySerializer
    permission_classes = [IsLawyerOrReadOnly]

class DocumentTypeViewSet(viewsets.ModelViewSet):
    queryset = DocumentType.objects.select_related('category')
    serializer_class = DocumentTypeSerializer
    permission_classes = [IsLawyerOrReadOnly]
    
    def get_queryset(self):
        queryset = DocumentType.objects.select_related('category')
        
        category = self.request.query_params.get('category', None)
        if category:
            queryset = queryset.filter(category_id=category)
        
        is_template = self.request.query_params.get('is_template', None)
        if is_template is not None:
            queryset = queryset.filter(is_template=is_template.lower() == 'true')
        
        return queryset

class DocumentStatusViewSet(viewsets.ModelViewSet):
    queryset = DocumentStatus.objects.all()
    serializer_class = DocumentStatusSerializer
    permission_classes = [IsLawyerOrReadOnly]

# ==========================================
# DOCUMENT VIEWSET - FIXED VERSION
# ==========================================

class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [DocumentPermission]
    parser_classes = (MultiPartParser, FormParser)
    
    def get_queryset(self):
        # Start me base queryset
        queryset = Document.objects.select_related(
            'document_type', 'status', 'created_by', 'uploaded_by'
        ).prefetch_related(
            'documentcaserelation_set__case',
            'access_controls'
        )
        
        # Apliko filtrimet bazë para distinct()
        document_type = self.request.query_params.get('document_type', None)
        if document_type:
            queryset = queryset.filter(document_type_id=document_type)
        
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status_id=status_filter)
        
        is_template = self.request.query_params.get('is_template', None)
        if is_template is not None:
            queryset = queryset.filter(is_template=is_template.lower() == 'true')
        
        access_level = self.request.query_params.get('access_level', None)
        if access_level:
            queryset = queryset.filter(access_level=access_level)
        
        case_id = self.request.query_params.get('case', None)
        if case_id:
            queryset = queryset.filter(documentcaserelation__case_id=case_id)
        
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(tags__icontains=search)
            )
        
        # Kontrollo access bazuar në user role (me Q objects kompleks)
        user = self.request.user
        access_filter = Q()
        
        if user.role == 'admin':
            # Admin sheh gjithçka
            pass  # No additional filtering
        elif user.role == 'client':
            # Klientët shohin vetëm dokumentet e rasteve të tyre ose public documents
            access_filter = (
                Q(documentcaserelation__case__client__user=user) |
                Q(access_level='public')
            )
        elif user.role in ['lawyer', 'paralegal']:
            # Lawyer/paralegal shohin dokumentet e tyre dhe ato internal/public
            access_filter = (
                Q(created_by=user) |
                Q(access_level__in=['public', 'internal']) |
                Q(documentcaserelation__case__assigned_to=user)
            )
        
        if access_filter:
            queryset = queryset.filter(access_filter)
        
        # Apliko distinct() VETËM në fund, pas të gjitha filtrimeve
        return queryset.distinct()
    
    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            uploaded_by=self.request.user
        )
        
        document = serializer.instance
        DocumentAuditLog.objects.create(
            document=document,
            user=self.request.user,
            action='created',
            ip_address=self.get_client_ip(),
            user_agent=self.request.META.get('HTTP_USER_AGENT', '')
        )
    
    def perform_update(self, serializer):
        serializer.save()
        
        document = serializer.instance
        DocumentAuditLog.objects.create(
            document=document,
            user=self.request.user,
            action='updated',
            ip_address=self.get_client_ip(),
            user_agent=self.request.META.get('HTTP_USER_AGENT', '')
        )
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Update last_accessed
        instance.last_accessed = timezone.now()
        instance.save(update_fields=['last_accessed'])
        
        # Log view
        DocumentAuditLog.objects.create(
            document=instance,
            user=request.user,
            action='viewed',
            ip_address=self.get_client_ip(),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        document = self.get_object()
        
        if not self.can_download_document(document, request.user):
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        DocumentAuditLog.objects.create(
            document=document,
            user=request.user,
            action='downloaded',
            ip_address=self.get_client_ip(),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        if document.file:
            response = HttpResponse(
                document.file.read(),
                content_type=mimetypes.guess_type(document.file.path)[0] or 'application/octet-stream'
            )
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(document.file.name)}"'
            return response
        else:
            return Response({'error': 'File not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['post'])
    def bulk_action(self, request):
        serializer = DocumentBulkSerializer(data=request.data)
        
        if serializer.is_valid():
            document_ids = serializer.validated_data['document_ids']
            action_type = serializer.validated_data['action']
            
            # Krijo queryset të ri për bulk actions (pa distinct())
            documents_queryset = Document.objects.filter(id__in=document_ids)
            
            # Kontrollo permissions për çdo dokument
            allowed_documents = []
            for doc in documents_queryset:
                if self.check_object_permissions(request, doc):
                    allowed_documents.append(doc)
            
            if not allowed_documents:
                return Response({'error': 'No documents accessible'}, status=status.HTTP_403_FORBIDDEN)
            
            result = self.execute_bulk_action(action_type, allowed_documents, serializer.validated_data, request.user)
            
            return Response(result)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def create_from_template(self, request):
        serializer = DocumentFromTemplateSerializer(data=request.data)
        
        if serializer.is_valid():
            template_id = serializer.validated_data['template_id']
            title = serializer.validated_data['title']
            case_id = serializer.validated_data.get('case_id')
            template_vars = serializer.validated_data.get('template_variables', {})
            
            template = Document.objects.get(id=template_id, is_template=True)
            
            new_document = Document.objects.create(
                title=title,
                description=f"Created from template: {template.title}",
                document_type=template.document_type,
                status=DocumentStatus.objects.filter(name='Draft').first() or template.status,
                is_template=False,
                template_variables=template_vars,
                metadata={'created_from_template': template.id},
                created_by=request.user,
                uploaded_by=request.user,
                access_level=template.access_level
            )
            
            if case_id:
                case = Case.objects.get(id=case_id)
                DocumentCaseRelation.objects.create(
                    document=new_document,
                    case=case,
                    relationship_type='template_used',
                    added_by=request.user
                )
            
            DocumentAuditLog.objects.create(
                document=new_document,
                user=request.user,
                action='created',
                metadata={'template_id': template.id}
            )
            
            serializer = DocumentSerializer(new_document, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def grant_access(self, request, pk=None):
        document = self.get_object()
        
        if request.user.role != 'admin' and document.created_by != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        user_id = request.data.get('user_id')
        role = request.data.get('role')
        permissions_data = request.data.get('permissions', {})
        
        if user_id:
            user = get_object_or_404(User, id=user_id)
            access, created = DocumentAccess.objects.update_or_create(
                document=document,
                user=user,
                defaults={
                    'can_view': permissions_data.get('can_view', True),
                    'can_download': permissions_data.get('can_download', True),
                    'can_edit': permissions_data.get('can_edit', False),
                    'can_delete': permissions_data.get('can_delete', False),
                    'can_share': permissions_data.get('can_share', False),
                    'granted_by': request.user
                }
            )
            
            action = 'access_granted' if created else 'access_updated'
            DocumentAuditLog.objects.create(
                document=document,
                user=request.user,
                action=action,
                metadata={'target_user': user.username, 'permissions': permissions_data}
            )
            
            return Response({'message': f'Access {action} successfully'})
        
        elif role:
            access, created = DocumentAccess.objects.update_or_create(
                document=document,
                role=role,
                defaults={
                    'can_view': permissions_data.get('can_view', True),
                    'can_download': permissions_data.get('can_download', True),
                    'can_edit': permissions_data.get('can_edit', False),
                    'can_delete': permissions_data.get('can_delete', False),
                    'can_share': permissions_data.get('can_share', False),
                    'granted_by': request.user
                }
            )
            
            action = 'role_access_granted' if created else 'role_access_updated'
            DocumentAuditLog.objects.create(
                document=document,
                user=request.user,
                action=action,
                metadata={'target_role': role, 'permissions': permissions_data}
            )
            
            return Response({'message': f'Role access {action} successfully'})
        
        return Response({'error': 'user_id or role required'}, status=status.HTTP_400_BAD_REQUEST)
    
    # ==========================================
    # HELPER METHODS
    # ==========================================
    
    def get_client_ip(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip
    
    def can_download_document(self, document, user):
        if user.role == 'admin':
            return True
        
        if document.created_by == user:
            return True
        
        if document.access_level == 'public':
            return True
        
        if document.access_level == 'internal' and user.role in ['lawyer', 'paralegal']:
            return True
        
        access = document.access_controls.filter(user=user).first()
        if access:
            return access.can_download
        
        role_access = document.access_controls.filter(role=user.role).first()
        if role_access:
            return role_access.can_download
        
        return False
    
    def execute_bulk_action(self, action_type, documents, data, user):
        results = {'success': 0, 'failed': 0, 'errors': []}
        
        with transaction.atomic():
            for document in documents:
                try:
                    if action_type == 'delete':
                        DocumentAuditLog.objects.create(
                            document=document,
                            user=user,
                            action='deleted'
                        )
                        document.delete()
                        results['success'] += 1
                    
                    elif action_type == 'change_status':
                        new_status_id = data.get('new_status')
                        if new_status_id:
                            status_obj = DocumentStatus.objects.get(id=new_status_id)
                            document.status = status_obj
                            document.save()
                            
                            DocumentAuditLog.objects.create(
                                document=document,
                                user=user,
                                action='status_changed',
                                metadata={'new_status': status_obj.name}
                            )
                            results['success'] += 1
                    
                    elif action_type == 'change_access_level':
                        new_level = data.get('access_level')
                        if new_level:
                            document.access_level = new_level
                            document.save()
                            
                            DocumentAuditLog.objects.create(
                                document=document,
                                user=user,
                                action='access_level_changed',
                                metadata={'new_access_level': new_level}
                            )
                            results['success'] += 1
                    
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append(f"Document {document.id}: {str(e)}")
        
        return results
