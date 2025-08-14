"""
Signature Views - Views për menaxhimin e nënshkrimeve elektronike
Integron SignatureService me DocuSign dhe sisteme të tjera
"""

import json
import logging
from typing import Dict, List, Any

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import (
    CreateView, ListView, DetailView, UpdateView, DeleteView, FormView, TemplateView
)
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse, Http404
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from ..models.document_models import Document, DocumentSignature, DocumentAuditLog
from ..advanced_features.signature_system import (
    SignatureService, SignatureRequest, SignerInfo, SignatureField,
    SignatureProvider, SignatureStatus
)
from ..forms import SignatureRequestForm, SigningForm

User = get_user_model()
logger = logging.getLogger(__name__)

class SignatureRequestListView(LoginRequiredMixin, ListView):
    """Lista e kërkesave për nënshkrim"""
    model = SignatureRequest
    template_name = 'document_editor/signatures/request_list.html'
    context_object_name = 'signature_requests'
    paginate_by = 20

    def get_queryset(self):
        queryset = SignatureRequest.objects.select_related('document')
        
        # Filter by user permissions
        user = self.request.user
        if user.role == 'client':
            # Clients see requests for documents in their cases
            queryset = queryset.filter(document__case__client__user=user)
        elif user.role in ['lawyer', 'paralegal']:
            # Lawyers see requests for documents they own or are assigned to
            queryset = queryset.filter(
                Q(document__owned_by=user) |
                Q(document__case__assigned_to=user) |
                Q(document__editors__user=user)
            ).distinct()
        
        # Apply filters
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        provider = self.request.GET.get('provider')
        if provider:
            queryset = queryset.filter(provider=provider)
        
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter options
        context['signature_statuses'] = [
            (status.value, status.value.title()) for status in SignatureStatus
        ]
        context['signature_providers'] = [
            (provider.value, provider.value.title()) for provider in SignatureProvider
        ]
        
        # Current filters
        context['current_filters'] = {
            'status': self.request.GET.get('status', ''),
            'provider': self.request.GET.get('provider', '')
        }
        
        # Statistics
        context['stats'] = {
            'total_requests': context['signature_requests'].count() if hasattr(context['signature_requests'], 'count') else len(context['signature_requests']),
            'pending_requests': SignatureRequest.objects.filter(
                status__in=[SignatureStatus.SENT.value, SignatureStatus.DELIVERED.value]
            ).count(),
            'completed_requests': SignatureRequest.objects.filter(
                status=SignatureStatus.COMPLETED.value
            ).count(),
            'expired_requests': SignatureRequest.objects.filter(
                status=SignatureStatus.EXPIRED.value
            ).count()
        }
        
        return context

class SignatureRequestDetailView(LoginRequiredMixin, DetailView):
    """Detajet e kërkesës për nënshkrim"""
    model = SignatureRequest
    template_name = 'document_editor/signatures/request_detail.html'
    context_object_name = 'signature_request'

    def get_queryset(self):
        return SignatureRequest.objects.select_related('document')

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        
        # Check permissions
        user = self.request.user
        can_view = (
            user.role == 'admin' or
            obj.document.owned_by == user or
            obj.document.case.assigned_to == user or
            self._is_user_signer(user, obj)
        )
        
        if not can_view:
            raise Http404("Signature request not found")
        
        return obj

    def _is_user_signer(self, user, signature_request):
        """Check if user is one of the signers"""
        signers = signature_request.signers_data.get('signers', [])
        return any(signer.get('email') == user.email for signer in signers)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        signature_request = self.object
        
        # Add signers information
        signers_data = signature_request.signers_data.get('signers', [])
        context['signers'] = signers_data
        
        # Add signatures
        context['signatures'] = DocumentSignature.objects.filter(
            document=signature_request.document
        ).select_related('signer')
        
        # Check if current user can sign
        user = self.request.user
        context['can_sign'] = (
            self._is_user_signer(user, signature_request) and
            signature_request.status in [SignatureStatus.SENT.value, SignatureStatus.DELIVERED.value] and
            not context['signatures'].filter(signer=user).exists()
        )
        
        # Add signing URL if available
        if context['can_sign']:
            context['signing_url'] = reverse('document_editor:signature_sign', 
                                          kwargs={'request_id': signature_request.id})
        
        # Add progress information
        total_signers = len(signers_data)
        signed_count = context['signatures'].count()
        context['progress'] = {
            'total_signers': total_signers,
            'signed_count': signed_count,
            'percentage': int((signed_count / total_signers) * 100) if total_signers > 0 else 0,
            'remaining': total_signers - signed_count
        }
        
        return context

class SignatureRequestCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Krijimi i kërkesës për nënshkrim"""
    model = SignatureRequest
    form_class = SignatureRequestForm
    template_name = 'document_editor/signatures/request_create.html'

    def test_func(self):
        return self.request.user.role in ['admin', 'lawyer']

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get document if provided
        document_id = self.request.GET.get('document_id')
        if document_id:
            try:
                document = Document.objects.get(id=document_id)
                context['document'] = document
            except Document.DoesNotExist:
                pass
        
        # Add signature providers
        context['signature_providers'] = [
            (provider.value, provider.value.title()) for provider in SignatureProvider
        ]
        
        return context

    def form_valid(self, form):
        # Get form data
        document = form.cleaned_data['document']
        title = form.cleaned_data.get('title', f'Signature request for {document.title}')
        message = form.cleaned_data.get('message', '')
        provider = SignatureProvider(form.cleaned_data.get('provider', 'internal'))
        
        # Parse signers from form
        signers_data = json.loads(self.request.POST.get('signers_json', '[]'))
        signers = []
        
        for signer_data in signers_data:
            signer = SignerInfo(
                name=signer_data['name'],
                email=signer_data['email'],
                phone=signer_data.get('phone', ''),
                role=signer_data.get('role', 'Signer'),
                order=signer_data.get('order', 1),
                required=signer_data.get('required', True)
            )
            signers.append(signer)
        
        if not signers:
            messages.error(self.request, 'At least one signer is required')
            return self.form_invalid(form)
        
        # Parse signature fields if provided
        signature_fields = []
        fields_data = json.loads(self.request.POST.get('signature_fields_json', '[]'))
        
        for field_data in fields_data:
            field = SignatureField(
                page_number=field_data['page_number'],
                x_position=field_data['x_position'],
                y_position=field_data['y_position'],
                width=field_data.get('width', 150),
                height=field_data.get('height', 50),
                signer_email=field_data['signer_email'],
                field_type=field_data.get('field_type', 'signature')
            )
            signature_fields.append(field)
        
        try:
            # Create signature request using service
            signature_service = SignatureService(provider)
            result = signature_service.create_signature_request(
                document=document,
                signers=signers,
                signature_fields=signature_fields,
                title=title,
                message=message,
                callback_url=self.request.build_absolute_uri(
                    reverse('document_editor:signature_webhook')
                )
            )
            
            if result['success']:
                messages.success(
                    self.request, 
                    f'Signature request created successfully! {len(signers)} signers notified.'
                )
                
                # Log action
                DocumentAuditLog.objects.create(
                    document=document,
                    user=self.request.user,
                    action='signature_request_created',
                    details=f'Signature request created with {len(signers)} signers',
                    metadata={
                        'provider': provider.value,
                        'signers_count': len(signers),
                        'external_id': result.get('envelope_id', result.get('signing_token'))
                    }
                )
                
                return redirect('document_editor:signature_request_detail', 
                              pk=result['signature_request_id'])
            else:
                messages.error(self.request, f'Failed to create signature request: {result["error"]}')
                return self.form_invalid(form)
                
        except Exception as e:
            logger.error(f"Signature request creation error: {e}")
            messages.error(self.request, f'An error occurred: {str(e)}')
            return self.form_invalid(form)

class SignatureSignView(LoginRequiredMixin, FormView):
    """Nënshkrim i dokumentit"""
    form_class = SigningForm
    template_name = 'document_editor/signatures/sign.html'

    def dispatch(self, request, *args, **kwargs):
        self.signature_request = get_object_or_404(SignatureRequest, id=kwargs['request_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['signature_request'] = self.signature_request
        context['document'] = self.signature_request.document
        
        # Check if user is authorized to sign
        user_email = self.request.user.email
        signers = self.signature_request.signers_data.get('signers', [])
        
        context['authorized_signer'] = any(
            signer.get('email') == user_email for signer in signers
        )
        
        # Check if already signed
        context['already_signed'] = DocumentSignature.objects.filter(
            document=self.signature_request.document,
            signer=self.request.user
        ).exists()
        
        # Get signature fields for this user
        context['signature_fields'] = [
            field for field in self.signature_request.metadata.get('signature_fields', [])
            if field.get('signer') == user_email
        ]
        
        return context

    def form_valid(self, form):
        if not self.get_context_data()['authorized_signer']:
            messages.error(self.request, 'You are not authorized to sign this document')
            return redirect('document_editor:signature_request_detail', pk=self.signature_request.id)
        
        if self.get_context_data()['already_signed']:
            messages.warning(self.request, 'You have already signed this document')
            return redirect('document_editor:signature_request_detail', pk=self.signature_request.id)
        
        signature_data = form.cleaned_data['signature_data']
        
        try:
            # Sign document using signature service
            signature_service = SignatureService()
            result = signature_service.sign_document(
                signature_request_id=self.signature_request.id,
                signer_email=self.request.user.email,
                signature_data=signature_data,
                signing_token=self.signature_request.external_id,
                ip_address=self.request.META.get('REMOTE_ADDR', ''),
                user_agent=self.request.META.get('HTTP_USER_AGENT', '')
            )
            
            if result['success']:
                messages.success(self.request, 'Document signed successfully!')
                
                # Send notification to document owner
                # TODO: Implement notification system
                
                return redirect('document_editor:signature_request_detail', pk=self.signature_request.id)
            else:
                messages.error(self.request, f'Signing failed: {result["error"]}')
                return self.form_invalid(form)
                
        except Exception as e:
            logger.error(f"Document signing error: {e}")
            messages.error(self.request, f'An error occurred while signing: {str(e)}')
            return self.form_invalid(form)

class SignatureListView(LoginRequiredMixin, ListView):
    """Lista e nënshkrimeve"""
    model = DocumentSignature
    template_name = 'document_editor/signatures/signature_list.html'
    context_object_name = 'signatures'
    paginate_by = 20

    def get_queryset(self):
        queryset = DocumentSignature.objects.select_related('document', 'signer')
        
        # Filter by user permissions
        user = self.request.user
        if user.role == 'client':
            queryset = queryset.filter(document__case__client__user=user)
        elif user.role in ['lawyer', 'paralegal']:
            queryset = queryset.filter(
                Q(document__owned_by=user) |
                Q(document__case__assigned_to=user) |
                Q(signer=user)
            ).distinct()
        
        return queryset.order_by('-signed_at')

class SignatureDetailView(LoginRequiredMixin, DetailView):
    """Detajet e nënshkrimit"""
    model = DocumentSignature
    template_name = 'document_editor/signatures/signature_detail.html'
    context_object_name = 'signature'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        signature = self.object
        
        # Verify signature
        signature_service = SignatureService()
        verification_result = signature_service.verify_signature(signature.id)
        context['verification_result'] = verification_result
        
        # Add certificate information if available
        context['certificate_info'] = signature.certificate_info
        
        return context

@login_required
@require_POST
def signature_verify(request, signature_id):
    """Verify signature"""
    try:
        signature = get_object_or_404(DocumentSignature, id=signature_id)
        
        # Check permissions
        user = request.user
        can_verify = (
            user.role == 'admin' or
            signature.document.owned_by == user or
            signature.document.case.assigned_to == user
        )
        
        if not can_verify:
            return JsonResponse({'success': False, 'error': 'Permission denied'})
        
        # Verify using signature service
        signature_service = SignatureService()
        result = signature_service.verify_signature(signature_id)
        
        # Log verification
        DocumentAuditLog.objects.create(
            document=signature.document,
            user=request.user,
            action='signature_verified',
            details=f'Signature verification result: {"Valid" if result.get("is_valid") else "Invalid"}',
            metadata=result
        )
        
        return JsonResponse(result)
        
    except Exception as e:
        logger.error(f"Signature verify error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def signature_request_cancel(request, request_id):
    """Cancel signature request"""
    try:
        signature_request = get_object_or_404(SignatureRequest, id=request_id)
        
        # Check permissions
        if not (signature_request.document.owned_by == request.user or request.user.role == 'admin'):
            return JsonResponse({'success': False, 'error': 'Permission denied'})
        
        # Update status
        signature_request.status = SignatureStatus.CANCELLED.value
        signature_request.save()
        
        # Log action
        DocumentAuditLog.objects.create(
            document=signature_request.document,
            user=request.user,
            action='signature_request_cancelled',
            details='Signature request cancelled'
        )
        
        messages.success(request, 'Signature request cancelled successfully')
        
        return JsonResponse({
            'success': True,
            'redirect_url': reverse('document_editor:signature_request_detail', kwargs={'pk': request_id})
        })
        
    except Exception as e:
        logger.error(f"Signature request cancel error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
def signature_webhook(request):
    """Webhook për signature provider callbacks"""
    try:
        if request.method != 'POST':
            return JsonResponse({'error': 'Only POST method allowed'}, status=405)
        
        # Parse webhook data based on provider
        # This is a generic handler - specific implementations needed for each provider
        
        data = json.loads(request.body)
        event_type = data.get('event', '')
        envelope_id = data.get('envelope_id', data.get('external_id', ''))
        
        if not envelope_id:
            return JsonResponse({'error': 'Missing envelope/external ID'}, status=400)
        
        try:
            signature_request = SignatureRequest.objects.get(external_id=envelope_id)
        except SignatureRequest.DoesNotExist:
            return JsonResponse({'error': 'Signature request not found'}, status=404)
        
        # Update status based on event
        status_mapping = {
            'envelope_completed': SignatureStatus.COMPLETED.value,
            'envelope_declined': SignatureStatus.DECLINED.value,
            'envelope_voided': SignatureStatus.CANCELLED.value,
            'envelope_delivered': SignatureStatus.DELIVERED.value,
        }
        
        new_status = status_mapping.get(event_type)
        if new_status:
            signature_request.status = new_status
            if new_status == SignatureStatus.COMPLETED.value:
                signature_request.completed_at = timezone.now()
            signature_request.save()
            
            # Log webhook event
            DocumentAuditLog.objects.create(
                document=signature_request.document,
                action='signature_webhook',
                details=f'Webhook event: {event_type}',
                metadata=data
            )
        
        return JsonResponse({'status': 'received'})
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Signature webhook error: {e}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def signature_analytics(request):
    """Signature analytics dashboard"""
    if request.user.role not in ['admin', 'lawyer']:
        raise PermissionDenied("Access denied")
    
    from datetime import datetime, timedelta
    
    # Get date range
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)  # Last 30 days
    
    # Signature statistics
    signature_requests = SignatureRequest.objects.filter(
        created_at__gte=start_date,
        created_at__lte=end_date
    )
    
    stats = {
        'total_requests': signature_requests.count(),
        'completed_requests': signature_requests.filter(status=SignatureStatus.COMPLETED.value).count(),
        'pending_requests': signature_requests.filter(
            status__in=[SignatureStatus.SENT.value, SignatureStatus.DELIVERED.value]
        ).count(),
        'declined_requests': signature_requests.filter(status=SignatureStatus.DECLINED.value).count(),
        'expired_requests': signature_requests.filter(status=SignatureStatus.EXPIRED.value).count(),
    }
    
    # Completion rate
    if stats['total_requests'] > 0:
        stats['completion_rate'] = round((stats['completed_requests'] / stats['total_requests']) * 100, 1)
    else:
        stats['completion_rate'] = 0
    
    # Provider statistics
    provider_stats = signature_requests.values('provider').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Average signing time
    completed_requests = signature_requests.filter(
        status=SignatureStatus.COMPLETED.value,
        completed_at__isnull=False
    )
    
    if completed_requests.exists():
        total_hours = sum([
            (r.completed_at - r.created_at).total_seconds() / 3600
            for r in completed_requests if r.completed_at
        ])
        avg_signing_hours = total_hours / completed_requests.count()
    else:
        avg_signing_hours = 0
    
    context = {
        'stats': stats,
        'provider_stats': provider_stats,
        'avg_signing_hours': round(avg_signing_hours, 1),
        'date_range': {
            'start': start_date.strftime('%Y-%m-%d'),
            'end': end_date.strftime('%Y-%m-%d')
        }
    }
    
    return render(request, 'document_editor/signatures/analytics.html', context)

@login_required
def signature_certificate_download(request, signature_id):
    """Download signature certificate"""
    try:
        signature = get_object_or_404(DocumentSignature, id=signature_id)
        
        # Check permissions
        user = request.user
        can_download = (
            user.role == 'admin' or
            signature.document.owned_by == user or
            signature.signer == user
        )
        
        if not can_download:
            raise PermissionDenied("Permission denied")
        
        # Generate certificate (placeholder implementation)
        from django.template.loader import render_to_string
        
        certificate_content = render_to_string('document_editor/signatures/certificate.html', {
            'signature': signature,
            'document': signature.document,
            'generated_at': timezone.now()
        })
        
        response = HttpResponse(certificate_content, content_type='text/html')
        response['Content-Disposition'] = f'attachment; filename="signature_certificate_{signature.id}.html"'
        
        # Log download
        DocumentAuditLog.objects.create(
            document=signature.document,
            user=request.user,
            action='certificate_download',
            details=f'Certificate downloaded for signature {signature.id}'
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Certificate download error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})
