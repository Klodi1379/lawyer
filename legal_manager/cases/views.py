from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import CreateView, FormView, UpdateView, DetailView, ListView, DeleteView
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth import login
from django.urls import reverse_lazy
from django.http import JsonResponse, FileResponse, Http404, HttpResponse
from django.db import models
from django.utils import timezone
from django.contrib import messages
from django.core.exceptions import PermissionDenied
import hashlib
import mimetypes
import os
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_otp.forms import OTPAuthenticationForm
from .models import (
    User, UserProfile, Client, Case, CaseDocument, 
    CaseEvent, TimeEntry, Invoice, AuditLog, UserAuditLog, EventType,
    DocumentVersion, DocumentAccess
)
from .serializers import (
    UserSerializer, UserProfileSerializer, ClientSerializer, CaseSerializer,
    CaseDocumentSerializer, CaseEventSerializer, TimeEntrySerializer, 
    InvoiceSerializer, AuditLogSerializer, UserAuditLogSerializer
)
from .forms import (
    UserRegistrationForm, UserLoginForm, UserProfileForm, 
    UserUpdateForm, CustomPasswordChangeForm, ClientForm, CaseForm,
    EventForm, EventFilterForm, QuickEventForm, DocumentUploadForm,
    DocumentUpdateForm, DocumentVersionForm, DocumentSearchForm
)

# =============================================================================
# WEB VIEWS (Traditional Django Views)
# =============================================================================

class RegistrationView(CreateView):
    form_class = UserRegistrationForm
    template_name = 'users/registration.html'
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        # Log action
        UserAuditLog.objects.create(
            user=self.object, 
            action='registration', 
            ip_address=self.request.META.get('REMOTE_ADDR')
        )
        return response

class CustomLoginView(LoginView):
    form_class = UserLoginForm
    template_name = 'users/login.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        # Log login
        UserAuditLog.objects.create(
            user=self.request.user, 
            action='login', 
            ip_address=self.request.META.get('REMOTE_ADDR')
        )
        return response

class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('login')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            UserAuditLog.objects.create(
                user=request.user, 
                action='logout', 
                ip_address=request.META.get('REMOTE_ADDR')
            )
        return super().dispatch(request, *args, **kwargs)

class ProfileView(LoginRequiredMixin, DetailView):
    model = UserProfile
    template_name = 'users/profile.html'
    context_object_name = 'profile'

    def get_object(self):
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        return profile

class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = UserProfile
    form_class = UserProfileForm
    template_name = 'users/profile_update.html'
    success_url = reverse_lazy('profile')

    def get_object(self):
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        return profile

    def form_valid(self, form):
        response = super().form_valid(form)
        UserAuditLog.objects.create(
            user=self.request.user, 
            action='profile_update', 
            ip_address=self.request.META.get('REMOTE_ADDR')
        )
        return response

class UserListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = User
    template_name = 'users/user_list.html'
    context_object_name = 'users'

    def test_func(self):
        return self.request.user.role == 'admin'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        users = User.objects.all()
        context['active_users_count'] = users.filter(is_active=True).count()
        context['lawyers_count'] = users.filter(role='lawyer').count()
        context['tfa_enabled_count'] = users.filter(is_2fa_enabled=True).count()
        return context

class UserUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = 'users/user_update.html'
    success_url = reverse_lazy('user_list')

    def test_func(self):
        return self.request.user.role == 'admin'

class CustomPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    form_class = CustomPasswordChangeForm
    template_name = 'users/password_change.html'
    success_url = reverse_lazy('profile')

class CaseListView(LoginRequiredMixin, ListView):
    model = Case
    template_name = 'cases/case_list.html'
    context_object_name = 'cases'
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        if user.role in ['admin', 'lawyer']:
            return Case.objects.all().select_related('client', 'assigned_to')
        elif user.role == 'paralegal':
            return Case.objects.filter(assigned_to=user).select_related('client', 'assigned_to')
        else:  # client
            return Case.objects.filter(client__email=user.email).select_related('client', 'assigned_to')

class CaseDetailView(LoginRequiredMixin, DetailView):
    model = Case
    template_name = 'cases/case_detail.html'
    context_object_name = 'case'

class CaseCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Case
    form_class = CaseForm
    template_name = 'cases/case_form.html'
    success_url = reverse_lazy('case_list')

    def test_func(self):
        return self.request.user.role in ['admin', 'lawyer']

    def form_valid(self, form):
        response = super().form_valid(form)
        # Log action
        AuditLog.objects.create(
            user=self.request.user,
            action='case_create',
            target_type='Case',
            target_id=str(self.object.id),
            metadata={'case_title': self.object.title}
        )
        return response

class CaseUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Case
    form_class = CaseForm
    template_name = 'cases/case_form.html'
    
    def test_func(self):
        case = self.get_object()
        return (self.request.user.role == 'admin' or 
                self.request.user == case.assigned_to)

    def get_success_url(self):
        return reverse_lazy('case_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        # Log action
        AuditLog.objects.create(
            user=self.request.user,
            action='case_update',
            target_type='Case',
            target_id=str(self.object.id),
            metadata={'case_title': self.object.title}
        )
        return response

class DashboardView(LoginRequiredMixin, ListView):
    template_name = 'dashboard.html'
    
    def get_queryset(self):
        return None
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get user-specific data based on role
        if user.role in ['admin', 'lawyer']:
            context['total_cases'] = Case.objects.count()
            context['open_cases'] = Case.objects.filter(status='open').count()
            context['recent_cases'] = Case.objects.order_by('-created_at')[:5]
        elif user.role == 'paralegal':
            context['my_cases'] = Case.objects.filter(assigned_to=user).count()
            context['open_cases'] = Case.objects.filter(assigned_to=user, status='open').count()
            context['recent_cases'] = Case.objects.filter(assigned_to=user).order_by('-created_at')[:5]
        else:  # client
            context['my_cases'] = Case.objects.filter(client__email=user.email).count()
            context['recent_cases'] = Case.objects.filter(client__email=user.email).order_by('-created_at')[:5]
        
        return context

# =============================================================================
# CLIENT VIEWS
# =============================================================================

class ClientListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Client
    template_name = 'clients/client_list.html'
    context_object_name = 'clients'
    paginate_by = 20

    def test_func(self):
        return self.request.user.role in ['admin', 'lawyer', 'paralegal']

class ClientCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Client
    form_class = ClientForm
    template_name = 'clients/client_form.html'
    success_url = reverse_lazy('client_list')

    def test_func(self):
        return self.request.user.role in ['admin', 'lawyer']

class ClientDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Client
    template_name = 'clients/client_detail.html'
    context_object_name = 'client'

    def test_func(self):
        return self.request.user.role in ['admin', 'lawyer', 'paralegal']

class ClientUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Client
    form_class = ClientForm
    template_name = 'clients/client_form.html'

    def test_func(self):
        return self.request.user.role in ['admin', 'lawyer']

    def get_success_url(self):
        return reverse_lazy('client_detail', kwargs={'pk': self.object.pk})

# =============================================================================
# DOCUMENT VIEWS (Enhanced with Upload, Download, Version Control)
# =============================================================================

class DocumentListView(LoginRequiredMixin, ListView):
    model = CaseDocument
    template_name = 'documents/document_list.html'
    context_object_name = 'documents'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        queryset = CaseDocument.objects.select_related('case', 'uploaded_by')
        
        # Apply search filters FIRST (before distinct)
        form = DocumentSearchForm(self.request.GET)
        if form.is_valid():
            search = form.cleaned_data.get('search')
            doc_type = form.cleaned_data.get('doc_type')
            status = form.cleaned_data.get('status')
            case = form.cleaned_data.get('case')
            uploaded_by = form.cleaned_data.get('uploaded_by')
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')
            confidential_only = form.cleaned_data.get('confidential_only')
            
            if search:
                queryset = queryset.filter(
                    models.Q(title__icontains=search) |
                    models.Q(description__icontains=search)
                )
            if doc_type:
                queryset = queryset.filter(doc_type=doc_type)
            if status:
                queryset = queryset.filter(status=status)
            if case:
                queryset = queryset.filter(case=case)
            if uploaded_by:
                queryset = queryset.filter(uploaded_by=uploaded_by)
            if date_from:
                queryset = queryset.filter(created_at__gte=date_from)
            if date_to:
                queryset = queryset.filter(created_at__lte=date_to)
            if confidential_only:
                queryset = queryset.filter(is_confidential=True)
        
        # Filter by user role AFTER search filters
        if user.role == 'client':
            queryset = queryset.filter(case__client__email=user.email)
        elif user.role == 'paralegal':
            queryset = queryset.filter(
                models.Q(case__assigned_to=user) | 
                models.Q(uploaded_by=user)
            )
        
        # Apply distinct() and ordering ONLY at the end
        return queryset.distinct().order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = DocumentSearchForm(self.request.GET)
        
        # Add document statistics for current page only
        docs = context['documents']  # This is page.object_list, not a queryset
        context['total_size'] = sum(doc.file_size or 0 for doc in docs)
        context['doc_type_counts'] = {}
        
        # Use the key (not label) for dictionary access in templates
        for doc_type_key, doc_type_label in CaseDocument.DOCUMENT_TYPES:
            count = len([d for d in docs if d.doc_type == doc_type_key])
            context['doc_type_counts'][doc_type_key] = count
            
        return context

class DocumentUploadView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = CaseDocument
    form_class = DocumentUploadForm
    template_name = 'documents/document_upload.html'

    def test_func(self):
        return self.request.user.role in ['admin', 'lawyer', 'paralegal']

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        case_id = self.kwargs.get('case_pk')
        if case_id:
            kwargs['case'] = get_object_or_404(Case, pk=case_id)
        return kwargs

    def form_valid(self, form):
        case_id = self.kwargs.get('case_pk')
        if case_id:
            form.instance.case = get_object_or_404(Case, pk=case_id)
        elif not form.instance.case:
            messages.error(self.request, 'Document must be associated with a case.')
            return self.form_invalid(form)
            
        form.instance.uploaded_by = self.request.user
        
        # Generate file hash for integrity checking
        if form.instance.file:
            file_content = form.instance.file.read()
            form.instance.file_hash = hashlib.sha256(file_content).hexdigest()
            form.instance.file.seek(0)  # Reset file pointer
        
        response = super().form_valid(form)
        
        # Log upload action
        DocumentAccess.objects.create(
            document=self.object,
            user=self.request.user,
            action='upload',
            ip_address=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT', '')
        )
        
        AuditLog.objects.create(
            user=self.request.user,
            action='document_upload',
            target_type='CaseDocument',
            target_id=str(self.object.id),
            metadata={
                'document_title': self.object.title,
                'case_id': self.object.case.id,
                'file_size': self.object.file_size
            }
        )
        
        messages.success(self.request, f'Document "{self.object.title}" uploaded successfully.')
        return response

    def get_success_url(self):
        if self.kwargs.get('case_pk'):
            return reverse_lazy('case_detail', kwargs={'pk': self.kwargs['case_pk']})
        else:
            return reverse_lazy('document_list')

class DocumentDetailView(LoginRequiredMixin, DetailView):
    model = CaseDocument
    template_name = 'documents/document_detail.html'
    context_object_name = 'document'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        user = self.request.user
        
        # Check permissions
        if user.role == 'client' and obj.case.client.email != user.email:
            raise PermissionDenied("You don't have permission to view this document.")
        elif user.role == 'paralegal' and obj.case.assigned_to != user and obj.uploaded_by != user:
            raise PermissionDenied("You don't have permission to view this document.")
        
        # Log view action
        DocumentAccess.objects.create(
            document=obj,
            user=user,
            action='view',
            ip_address=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT', '')
        )
        
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['versions'] = self.object.versions.all()
        context['recent_access'] = self.object.access_logs.all()[:10]
        return context

# =============================================================================
# EVENT VIEWS (Calendar and Events Management)
# =============================================================================

class IsLawyerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow lawyers and admins to edit cases.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return hasattr(request.user, 'role') and request.user.role in ['lawyer', 'admin']

    def has_object_permission(self, request, view, obj):
        # Read permissions for authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True
        # Write permissions only for assigned lawyer or admin
        return request.user == obj.assigned_to or request.user.role == 'admin'

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return User.objects.all()
        else:
            return User.objects.filter(id=user.id)

class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [IsLawyerOrReadOnly]

class CaseViewSet(viewsets.ModelViewSet):
    serializer_class = CaseSerializer
    permission_classes = [IsLawyerOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['admin', 'lawyer']:
            return Case.objects.all().select_related('client', 'assigned_to')
        elif user.role == 'paralegal':
            return Case.objects.filter(assigned_to=user).select_related('client', 'assigned_to')
        else:  # client
            return Case.objects.filter(client__email=user.email).select_related('client', 'assigned_to')

    @action(detail=True, methods=['post'])
    def add_document(self, request, pk=None):
        case = self.get_object()
        file = request.FILES.get('file')
        title = request.data.get('title')
        
        if not file or not title:
            return Response(
                {'error': 'Both file and title are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        doc = CaseDocument.objects.create(
            case=case, 
            uploaded_by=request.user, 
            file=file, 
            title=title
        )
        
        # Log action
        AuditLog.objects.create(
            user=request.user,
            action='document_upload',
            target_type='CaseDocument',
            target_id=str(doc.id),
            metadata={'case_id': case.id, 'document_title': title}
        )
        
        return Response({'id': doc.id, 'title': doc.title})

    @action(detail=True, methods=['post'])
    def add_event(self, request, pk=None):
        case = self.get_object()
        serializer = CaseEventSerializer(data=request.data)
        
        if serializer.is_valid():
            event = serializer.save(case=case, created_by=request.user)
            return Response(CaseEventSerializer(event).data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CaseDocumentViewSet(viewsets.ModelViewSet):
    queryset = CaseDocument.objects.all()
    serializer_class = CaseDocumentSerializer
    permission_classes = [IsLawyerOrReadOnly]

class CaseEventViewSet(viewsets.ModelViewSet):
    queryset = CaseEvent.objects.all()
    serializer_class = CaseEventSerializer
    permission_classes = [IsLawyerOrReadOnly]

class TimeEntryViewSet(viewsets.ModelViewSet):
    queryset = TimeEntry.objects.all()
    serializer_class = TimeEntrySerializer
    permission_classes = [IsLawyerOrReadOnly]

class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [IsLawyerOrReadOnly]

# =============================================================================
# EVENT VIEWS (Calendar and Events Management)
# =============================================================================

# Event Views
from django.db import models
from django.utils import timezone

class EventCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = CaseEvent
    form_class = EventForm
    template_name = 'events/event_form.html'

    def test_func(self):
        return self.request.user.role in ['admin', 'lawyer', 'paralegal']

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        case_id = self.kwargs.get('case_pk')
        if case_id:
            kwargs['case'] = get_object_or_404(Case, pk=case_id)
        return kwargs

    def form_valid(self, form):
        case_id = self.kwargs.get('case_pk')
        if case_id:
            form.instance.case = get_object_or_404(Case, pk=case_id)
        form.instance.created_by = self.request.user
        
        response = super().form_valid(form)
        
        AuditLog.objects.create(
            user=self.request.user,
            action='event_create',
            target_type='CaseEvent',
            target_id=str(self.object.id),
            metadata={'event_title': self.object.title, 'case_id': self.object.case.id}
        )
        
        return response

    def get_success_url(self):
        if self.kwargs.get('case_pk'):
            return reverse_lazy('case_detail', kwargs={'pk': self.kwargs['case_pk']})
        else:
            return reverse_lazy('event_calendar')

class EventListView(LoginRequiredMixin, ListView):
    model = CaseEvent
    template_name = 'events/event_list.html'
    context_object_name = 'events'
    paginate_by = 20

    def get_queryset(self):
        queryset = CaseEvent.objects.select_related('case', 'event_type', 'created_by')
        
        user = self.request.user
        if user.role == 'client':
            queryset = queryset.filter(case__client__email=user.email)
        elif user.role == 'paralegal':
            queryset = queryset.filter(
                models.Q(case__assigned_to=user) | models.Q(attendees=user)
            ).distinct()
        
        return queryset.order_by('starts_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = EventFilterForm(self.request.GET)
        return context

class EventCalendarView(LoginRequiredMixin, ListView):
    model = CaseEvent
    template_name = 'events/calendar.html'
    context_object_name = 'events'

    def get_queryset(self):
        queryset = CaseEvent.objects.select_related('case', 'event_type', 'created_by')
        
        user = self.request.user
        if user.role == 'client':
            queryset = queryset.filter(case__client__email=user.email)
        elif user.role == 'paralegal':
            queryset = queryset.filter(
                models.Q(case__assigned_to=user) | models.Q(attendees=user)
            ).distinct()
            
        return queryset

def calendar_api(request):
    """API endpoint for FullCalendar.js"""
    start = request.GET.get('start')
    end = request.GET.get('end')
    
    queryset = CaseEvent.objects.select_related('case', 'event_type', 'created_by')
    user = request.user
    
    if user.role == 'client':
        queryset = queryset.filter(case__client__email=user.email)
    elif user.role == 'paralegal':
        queryset = queryset.filter(
            models.Q(case__assigned_to=user) | models.Q(attendees=user)
        ).distinct()
    
    if start and end:
        queryset = queryset.filter(
            starts_at__gte=start,
            starts_at__lte=end
        )
    
    events_data = []
    for event in queryset:
        event_data = {
            'id': event.id,
            'title': event.title,
            'start': event.starts_at.isoformat(),
            'end': event.ends_at.isoformat() if event.ends_at else None,
            'allDay': event.is_all_day,
            'color': event.get_calendar_color(),
            'url': reverse_lazy('event_detail', kwargs={'pk': event.pk}),
            'extendedProps': {
                'case_uid': event.case.uid,
                'case_title': event.case.title,
                'priority': event.priority,
                'location': event.location,
                'attendees': event.get_attendees_list(),
                'is_deadline': event.is_deadline,
            }
        }
        events_data.append(event_data)
    
    return JsonResponse(events_data, safe=False)

class EventDetailView(LoginRequiredMixin, DetailView):
    model = CaseEvent
    template_name = 'events/event_detail.html'
    context_object_name = 'event'

class EventUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = CaseEvent
    form_class = EventForm
    template_name = 'events/event_form.html'

    def test_func(self):
        event = self.get_object()
        user = self.request.user
        return (user.role == 'admin' or 
                user == event.case.assigned_to or 
                user == event.created_by)

    def get_success_url(self):
        return reverse_lazy('event_detail', kwargs={'pk': self.object.pk})

class EventDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = CaseEvent
    template_name = 'events/event_confirm_delete.html'

    def test_func(self):
        event = self.get_object()
        user = self.request.user
        return (user.role == 'admin' or 
                user == event.case.assigned_to or 
                user == event.created_by)

    def get_success_url(self):
        return reverse_lazy('event_calendar')

def document_download(request, pk):
    """Secure document download with access logging"""
    document = get_object_or_404(CaseDocument, pk=pk)
    user = request.user
    
    # Check permissions
    if user.role == 'client' and document.case.client.email != user.email:
        raise PermissionDenied("You don't have permission to download this document.")
    elif user.role == 'paralegal' and document.case.assigned_to != user and document.uploaded_by != user:
        raise PermissionDenied("You don't have permission to download this document.")
    
    # Check if file exists
    if not document.file or not os.path.exists(document.file.path):
        messages.error(request, 'File not found.')
        return redirect('document_detail', pk=pk)
    
    # Log download action
    DocumentAccess.objects.create(
        document=document,
        user=user,
        action='download',
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )
    
    # Increment download counter
    document.download_count += 1
    document.save(update_fields=['download_count'])
    
    # Serve file
    file_path = document.file.path
    content_type, _ = mimetypes.guess_type(file_path)
    
    try:
        response = FileResponse(
            open(file_path, 'rb'),
            content_type=content_type,
            as_attachment=True,
            filename=f"{document.title}.{document.get_file_extension()}"
        )
        return response
    except Exception as e:
        messages.error(request, f'Error downloading file: {str(e)}')
        return redirect('document_detail', pk=pk)

class DocumentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = CaseDocument
    form_class = DocumentUpdateForm
    template_name = 'documents/document_update.html'
    context_object_name = 'document'

    def test_func(self):
        document = self.get_object()
        user = self.request.user
        return (user.role == 'admin' or 
                user == document.uploaded_by or 
                user == document.case.assigned_to)

    def form_valid(self, form):
        response = super().form_valid(form)
        
        # Log update action
        DocumentAccess.objects.create(
            document=self.object,
            user=self.request.user,
            action='edit',
            ip_address=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT', '')
        )
        
        AuditLog.objects.create(
            user=self.request.user,
            action='document_update',
            target_type='CaseDocument',
            target_id=str(self.object.id),
            metadata={'document_title': self.object.title}
        )
        
        messages.success(self.request, 'Document updated successfully.')
        return response

    def get_success_url(self):
        return reverse_lazy('document_detail', kwargs={'pk': self.object.pk})

class DocumentDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = CaseDocument
    template_name = 'documents/document_confirm_delete.html'

    def test_func(self):
        document = self.get_object()
        user = self.request.user
        return (user.role == 'admin' or 
                user == document.uploaded_by)

    def delete(self, request, *args, **kwargs):
        # Log delete action before deleting
        document = self.get_object()
        
        DocumentAccess.objects.create(
            document=document,
            user=request.user,
            action='delete',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        AuditLog.objects.create(
            user=request.user,
            action='document_delete',
            target_type='CaseDocument',
            target_id=str(document.id),
            metadata={'document_title': document.title}
        )
        
        messages.success(request, f'Document "{document.title}" deleted successfully.')
        return super().delete(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy('document_list')

class DocumentVersionCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = DocumentVersion
    form_class = DocumentVersionForm
    template_name = 'documents/document_version_upload.html'

    def test_func(self):
        document_pk = self.kwargs.get('document_pk')
        document = get_object_or_404(CaseDocument, pk=document_pk)
        user = self.request.user
        return (user.role in ['admin', 'lawyer'] or 
                user == document.uploaded_by or 
                user == document.case.assigned_to)

    def form_valid(self, form):
        document_pk = self.kwargs.get('document_pk')
        document = get_object_or_404(CaseDocument, pk=document_pk)
        
        # Set the document and version number
        form.instance.document = document
        form.instance.uploaded_by = self.request.user
        form.instance.version_number = document.version + 1
        
        response = super().form_valid(form)
        
        # Update main document version
        document.version = form.instance.version_number
        document.save(update_fields=['version'])
        
        # Log version upload
        AuditLog.objects.create(
            user=self.request.user,
            action='document_version_upload',
            target_type='DocumentVersion',
            target_id=str(self.object.id),
            metadata={
                'document_title': document.title,
                'version_number': form.instance.version_number
            }
        )
        
        messages.success(self.request, f'New version ({form.instance.version_number}) uploaded successfully.')
        return response

    def get_success_url(self):
        document_pk = self.kwargs.get('document_pk')
        return reverse_lazy('document_detail', kwargs={'pk': document_pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        document_pk = self.kwargs.get('document_pk')
        context['document'] = get_object_or_404(CaseDocument, pk=document_pk)
        return context

def document_version_download(request, pk):
    """Download specific version of a document"""
    version = get_object_or_404(DocumentVersion, pk=pk)
    user = request.user
    
    # Check permissions
    document = version.document
    if user.role == 'client' and document.case.client.email != user.email:
        raise PermissionDenied("You don't have permission to download this document version.")
    elif user.role == 'paralegal' and document.case.assigned_to != user and document.uploaded_by != user:
        raise PermissionDenied("You don't have permission to download this document version.")
    
    # Check if file exists
    if not version.file or not os.path.exists(version.file.path):
        messages.error(request, 'Version file not found.')
        return redirect('document_detail', pk=document.pk)
    
    # Serve file
    file_path = version.file.path
    content_type, _ = mimetypes.guess_type(file_path)
    
    try:
        response = FileResponse(
            open(file_path, 'rb'),
            content_type=content_type,
            as_attachment=True,
            filename=f"{document.title}_v{version.version_number}.{version.file.name.split('.')[-1]}"
        )
        return response
    except Exception as e:
        messages.error(request, f'Error downloading version: {str(e)}')
        return redirect('document_detail', pk=document.pk)
