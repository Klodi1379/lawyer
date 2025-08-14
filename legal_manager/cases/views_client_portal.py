"""
Views për Client Portal
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, Http404, FileResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, ListView, DetailView
from django.utils import timezone
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Avg
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from datetime import timedelta
import mimetypes
import os

from .models import Case, Client, CaseDocument
from .models_billing import AdvancedInvoice, Payment
from .models_client_portal import (
    ClientPortalAccess, ClientDocumentShare, ClientMessage, 
    ClientNotification, ClientDashboardWidget, ClientPaymentTracking,
    ClientFeedback
)
from .serializers_client_portal import (
    ClientPortalAccessSerializer, ClientDocumentShareSerializer,
    ClientMessageSerializer, ClientNotificationSerializer,
    ClientDashboardStatsSerializer, ClientFeedbackSerializer
)

# =============================================================================
# CLIENT PORTAL MIXINS
# =============================================================================

class ClientAccessMixin:
    """
    Mixin për të kontrolluar aksesimin e klientëve në portal
    """
    def test_func(self):
        if hasattr(self.request.user, 'client_profile'):
            client = self.request.user.client_profile
            try:
                portal_access = client.portal_access
                return portal_access.is_enabled
            except ClientPortalAccess.DoesNotExist:
                return False
        return False

class ClientOnlyMixin(UserPassesTestMixin):
    """
    Mixin që lejon vetëm klientët të aksesojnë
    """
    def test_func(self):
        return (
            self.request.user.is_authenticated and 
            hasattr(self.request.user, 'client_profile') and
            self.request.user.client_profile.portal_access.is_enabled
        )

# =============================================================================
# WEB VIEWS për Client Portal
# =============================================================================

class ClientDashboardView(ClientOnlyMixin, TemplateView):
    """
    Dashboard kryesor i klientit
    """
    template_name = 'client_portal/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        client = self.request.user.client_profile
        
        # Rastet aktive
        active_cases = Case.objects.filter(
            client=client,
            status__in=['open', 'pending']
        ).order_by('-created_at')
        
        # Dokumentet e fundit
        recent_documents = ClientDocumentShare.objects.filter(
            client=client,
            is_active=True
        ).select_related('document', 'case').order_by('-shared_at')[:5]
        
        # Faturat e fundit
        recent_invoices = AdvancedInvoice.objects.filter(
            client=client
        ).order_by('-issue_date')[:5]
        
        # Njoftimet e palexuara
        unread_notifications = ClientNotification.objects.filter(
            client=client,
            status='unread'
        ).count()
        
        # Mesazhet e pa-lexuara
        unread_messages = ClientMessage.objects.filter(
            client=client,
            is_read=False,
            message_type='lawyer_to_client'
        ).count()
        
        # Statistika financiare
        financial_stats = self._get_financial_stats(client)
        
        context.update({
            'client': client,
            'active_cases': active_cases,
            'recent_documents': recent_documents,
            'recent_invoices': recent_invoices,
            'unread_notifications': unread_notifications,
            'unread_messages': unread_messages,
            'financial_stats': financial_stats,
        })
        
        return context
    
    def _get_financial_stats(self, client):
        """Llogarit statistikat financiare për klientin"""
        current_year = timezone.now().year
        
        # Faturat e këtij viti
        year_invoices = AdvancedInvoice.objects.filter(
            client=client,
            issue_date__year=current_year
        )
        
        total_invoiced = year_invoices.aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        # Pagesat e këtij viti
        total_paid = Payment.objects.filter(
            invoice__client=client,
            payment_date__year=current_year,
            status='completed'
        ).aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        # Balanca e mbetur
        outstanding = AdvancedInvoice.objects.filter(
            client=client,
            status__in=['sent', 'overdue']
        ).aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        outstanding_payments = Payment.objects.filter(
            invoice__client=client,
            invoice__status__in=['sent', 'overdue'],
            status='completed'
        ).aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        outstanding_balance = outstanding - outstanding_payments
        
        return {
            'total_invoiced': total_invoiced,
            'total_paid': total_paid,
            'outstanding_balance': outstanding_balance,
            'invoice_count': year_invoices.count(),
        }

class ClientCasesView(ClientOnlyMixin, ListView):
    """
    Lista e rasteve të klientit
    """
    template_name = 'client_portal/cases.html'
    context_object_name = 'cases'
    paginate_by = 10
    
    def get_queryset(self):
        client = self.request.user.client_profile
        return Case.objects.filter(client=client).order_by('-created_at')

class ClientCaseDetailView(ClientOnlyMixin, DetailView):
    """
    Detajet e rastit për klient
    """
    template_name = 'client_portal/case_detail.html'
    context_object_name = 'case'
    
    def get_queryset(self):
        client = self.request.user.client_profile
        return Case.objects.filter(client=client)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        case = self.object
        client = self.request.user.client_profile
        
        # Dokumentet e ndarë për këtë rast
        shared_documents = ClientDocumentShare.objects.filter(
            client=client,
            case=case,
            is_active=True
        ).select_related('document').order_by('-shared_at')
        
        # Ngjarjet e ardhshme
        upcoming_events = case.events.filter(
            starts_at__gte=timezone.now()
        ).order_by('starts_at')[:5]
        
        # Mesazhet për këtë rast
        recent_messages = ClientMessage.objects.filter(
            client=client,
            case=case
        ).order_by('-sent_at')[:10]
        
        context.update({
            'shared_documents': shared_documents,
            'upcoming_events': upcoming_events,
            'recent_messages': recent_messages,
        })
        
        return context

class ClientDocumentsView(ClientOnlyMixin, ListView):
    """
    Dokumentet e klientit
    """
    template_name = 'client_portal/documents.html'
    context_object_name = 'document_shares'
    paginate_by = 20
    
    def get_queryset(self):
        client = self.request.user.client_profile
        return ClientDocumentShare.objects.filter(
            client=client,
            is_active=True
        ).select_related('document', 'case', 'shared_by').order_by('-shared_at')

@login_required
def client_document_download(request, share_id):
    """
    Shkarkon dokumentin e ndarë me klient
    """
    if not hasattr(request.user, 'client_profile'):
        raise Http404("Access denied")
    
    client = request.user.client_profile
    
    try:
        document_share = ClientDocumentShare.objects.get(
            id=share_id,
            client=client,
            is_active=True
        )
    except ClientDocumentShare.DoesNotExist:
        raise Http404("Document not found")
    
    # Kontrollon nëse është i aksesueshëm
    if not document_share.is_accessible():
        messages.error(request, "Dokumenti nuk është më i aksesueshëm")
        return redirect('client_portal:documents')
    
    # Kontrollon llojin e aksesit
    if document_share.share_type == 'view_only':
        messages.error(request, "Ju nuk keni të drejtë të shkarkoni këtë dokument")
        return redirect('client_portal:documents')
    
    # Regjistron aksesimin
    document_share.record_access()
    
    # Kthen fajlin
    document = document_share.document
    if document.file:
        response = FileResponse(
            document.file.open('rb'),
            as_attachment=True,
            filename=document.filename
        )
        return response
    
    raise Http404("File not found")

class ClientInvoicesView(ClientOnlyMixin, ListView):
    """
    Faturat e klientit
    """
    template_name = 'client_portal/invoices.html'
    context_object_name = 'invoices'
    paginate_by = 20
    
    def get_queryset(self):
        client = self.request.user.client_profile
        return AdvancedInvoice.objects.filter(
            client=client
        ).select_related('case', 'currency').order_by('-issue_date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        client = self.request.user.client_profile
        
        # Statistika të faturave
        invoice_stats = AdvancedInvoice.objects.filter(client=client).aggregate(
            total_amount=Sum('total_amount'),
            paid_count=Count('id', filter=Q(status='paid')),
            pending_count=Count('id', filter=Q(status__in=['sent', 'draft'])),
            overdue_count=Count('id', filter=Q(
                status='sent',
                due_date__lt=timezone.now().date()
            ))
        )
        
        context['invoice_stats'] = invoice_stats
        return context

class ClientPaymentsView(ClientOnlyMixin, ListView):
    """
    Pagesat e klientit
    """
    template_name = 'client_portal/payments.html'
    context_object_name = 'payments'
    paginate_by = 20
    
    def get_queryset(self):
        client = self.request.user.client_profile
        return Payment.objects.filter(
            invoice__client=client
        ).select_related('invoice', 'currency').order_by('-payment_date')

class ClientMessagesView(ClientOnlyMixin, ListView):
    """
    Mesazhet e klientit
    """
    template_name = 'client_portal/messages.html'
    context_object_name = 'messages'
    paginate_by = 20
    
    def get_queryset(self):
        client = self.request.user.client_profile
        return ClientMessage.objects.filter(
            client=client
        ).select_related('case', 'sender').order_by('-sent_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Shënon mesazhet si të lexuara
        ClientMessage.objects.filter(
            client=self.request.user.client_profile,
            is_read=False,
            message_type='lawyer_to_client'
        ).update(is_read=True, read_at=timezone.now())
        
        return context

# =============================================================================
# API VIEWS për Client Portal
# =============================================================================

class ClientPortalViewSet(viewsets.ViewSet):
    """
    API ViewSet për Client Portal
    """
    permission_classes = [IsAuthenticated]
    
    def _get_client_or_404(self, request):
        """Helper për të marrë klientin ose error 404"""
        if not hasattr(request.user, 'client_profile'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Access denied: Client access required")
        return request.user.client_profile
    
    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        """
        Statistika për dashboard-in e klientit
        """
        client = self._get_client_or_404(request)
        
        # Llogarit statistikat
        stats = {
            'active_cases': Case.objects.filter(
                client=client,
                status__in=['open', 'pending']
            ).count(),
            
            'total_cases': Case.objects.filter(client=client).count(),
            
            'shared_documents': ClientDocumentShare.objects.filter(
                client=client,
                is_active=True
            ).count(),
            
            'unread_notifications': ClientNotification.objects.filter(
                client=client,
                status='unread'
            ).count(),
            
            'unread_messages': ClientMessage.objects.filter(
                client=client,
                is_read=False,
                message_type='lawyer_to_client'
            ).count(),
            
            'pending_invoices': AdvancedInvoice.objects.filter(
                client=client,
                status__in=['sent', 'draft']
            ).count(),
        }
        
        # Financial stats
        current_year = timezone.now().year
        financial_stats = {
            'total_invoiced_this_year': AdvancedInvoice.objects.filter(
                client=client,
                issue_date__year=current_year
            ).aggregate(total=Sum('total_amount'))['total'] or 0,
            
            'total_paid_this_year': Payment.objects.filter(
                invoice__client=client,
                payment_date__year=current_year,
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or 0,
        }
        
        serializer = ClientDashboardStatsSerializer({
            **stats,
            **financial_stats
        })
        
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def notifications(self, request):
        """
        Lista e njoftimeve të klientit
        """
        client = self._get_client_or_404(request)
        
        notifications = ClientNotification.objects.filter(
            client=client
        ).order_by('-created_at')
        
        # Paginimi
        paginator = Paginator(notifications, 20)
        page_number = request.query_params.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        serializer = ClientNotificationSerializer(page_obj, many=True)
        
        return Response({
            'results': serializer.data,
            'count': paginator.count,
            'num_pages': paginator.num_pages,
            'current_page': page_obj.number,
        })
    
    @action(detail=False, methods=['post'])
    def mark_notification_read(self, request):
        """
        Shënon njoftimin si të lexuar
        """
        client = self._get_client_or_404(request)
        notification_id = request.data.get('notification_id')
        
        try:
            notification = ClientNotification.objects.get(
                id=notification_id,
                client=client
            )
            notification.mark_as_read()
            
            return Response({'success': True})
            
        except ClientNotification.DoesNotExist:
            return Response(
                {'error': 'Njoftimi nuk u gjet'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    def send_message(self, request):
        """
        Dërgon mesazh të ri për avokatin
        """
        client = self._get_client_or_404(request)
        
        case_id = request.data.get('case_id')
        subject = request.data.get('subject')
        content = request.data.get('content')
        is_urgent = request.data.get('is_urgent', False)
        
        try:
            case = Case.objects.get(id=case_id, client=client)
            
            message = ClientMessage.objects.create(
                case=case,
                client=client,
                sender=request.user,
                message_type='client_to_lawyer',
                subject=subject,
                content=content,
                is_urgent=is_urgent
            )
            
            # Krijon njoftim për avokatin
            if case.assigned_lawyer:
                ClientNotification.objects.create(
                    client=client,
                    case=case,
                    notification_type='message_received',
                    title='Mesazh i ri nga klienti',
                    message=f'{client.name} ka dërguar një mesazh të ri: {subject}'
                )
            
            serializer = ClientMessageSerializer(message)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Case.DoesNotExist:
            return Response(
                {'error': 'Rasti nuk u gjet'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    def submit_feedback(self, request):
        """
        Dërgon feedback për shërbimet
        """
        client = self._get_client_or_404(request)
        
        data = request.data.copy()
        data['client'] = client.id
        
        serializer = ClientFeedbackSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def client_case_timeline(request, case_id):
    """
    Timeline e aktiviteteve për një rast
    """
    if not hasattr(request.user, 'client_profile'):
        return Response(
            {'error': 'Access denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    client = request.user.client_profile
    
    try:
        case = Case.objects.get(id=case_id, client=client)
    except Case.DoesNotExist:
        return Response(
            {'error': 'Rasti nuk u gjet'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Merr aktivitetet e ndryshme
    activities = []
    
    # Ngjarjet
    events = case.events.all().order_by('-starts_at')
    for event in events:
        activities.append({
            'type': 'event',
            'date': event.starts_at.date(),
            'title': event.title,
            'description': event.description,
            'icon': 'calendar'
        })
    
    # Dokumentet e ndarë
    documents = ClientDocumentShare.objects.filter(
        case=case,
        client=client,
        is_active=True
    ).order_by('-shared_at')
    
    for doc in documents:
        activities.append({
            'type': 'document',
            'date': doc.shared_at.date(),
            'title': f'Dokument i ndarë: {doc.document.filename}',
            'description': doc.share_message,
            'icon': 'file'
        })
    
    # Mesazhet
    messages = ClientMessage.objects.filter(
        case=case,
        client=client
    ).order_by('-sent_at')
    
    for msg in messages:
        activities.append({
            'type': 'message',
            'date': msg.sent_at.date(),
            'title': f'Mesazh: {msg.subject}',
            'description': msg.content[:100] + '...' if len(msg.content) > 100 else msg.content,
            'icon': 'message',
            'sender': msg.sender.get_full_name()
        })
    
    # Rendit sipas datës
    activities.sort(key=lambda x: x['date'], reverse=True)
    
    return Response({
        'case': {
            'id': case.id,
            'title': case.title,
            'status': case.status
        },
        'activities': activities
    })