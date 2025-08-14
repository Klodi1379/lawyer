"""
Workflow Views - Views për menaxhimin e workflow-ve të dokumenteve
Integron WorkflowEngine me approval processes dhe notifications
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
from django.http import JsonResponse, HttpResponse
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.db import transaction
from django.utils import timezone

from ..models.document_models import Document, DocumentAuditLog
from ..advanced_features.workflow_system import (
    WorkflowEngine, WorkflowTemplate, DocumentWorkflow, WorkflowStep,
    WorkflowStepStatus, ActionType, WorkflowAction
)
from ..forms import WorkflowTemplateForm, WorkflowActionForm

logger = logging.getLogger(__name__)

class WorkflowDashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard për workflow management"""
    template_name = 'document_editor/workflows/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Pending tasks for current user
        pending_steps = WorkflowStep.objects.filter(
            assigned_users=user,
            status__in=[WorkflowStepStatus.PENDING.value, WorkflowStepStatus.IN_PROGRESS.value]
        ).select_related('workflow__document').order_by('deadline')
        
        context['pending_tasks'] = pending_steps[:10]
        
        # Overdue tasks
        overdue_steps = pending_steps.filter(
            deadline__lt=timezone.now()
        )
        context['overdue_tasks'] = overdue_steps
        
        # Recent completed workflows
        if user.role in ['admin', 'lawyer']:
            recent_completed = DocumentWorkflow.objects.filter(
                status=WorkflowStepStatus.COMPLETED.value,
                completed_at__gte=timezone.now() - timezone.timedelta(days=7)
            ).select_related('document').order_by('-completed_at')[:10]
        else:
            recent_completed = []
        
        context['recent_completed'] = recent_completed
        
        # Statistics
        context['stats'] = {
            'pending_count': pending_steps.count(),
            'overdue_count': overdue_steps.count(),
            'completed_today': DocumentWorkflow.objects.filter(
                status=WorkflowStepStatus.COMPLETED.value,
                completed_at__date=timezone.now().date()
            ).count(),
            'total_workflows': DocumentWorkflow.objects.count() if user.role in ['admin', 'lawyer'] else 0
        }
        
        return context

class WorkflowListView(LoginRequiredMixin, ListView):
    """Lista e workflow-ve"""
    model = DocumentWorkflow
    template_name = 'document_editor/workflows/list.html'
    context_object_name = 'workflows'
    paginate_by = 20

    def get_queryset(self):
        queryset = DocumentWorkflow.objects.select_related(
            'document', 'template'
        ).prefetch_related('steps__assigned_users')
        
        # Filter by user permissions
        user = self.request.user
        if user.role == 'client':
            queryset = queryset.filter(document__case__client__user=user)
        elif user.role in ['lawyer', 'paralegal']:
            queryset = queryset.filter(
                Q(document__owned_by=user) |
                Q(document__case__assigned_to=user) |
                Q(steps__assigned_users=user)
            ).distinct()
        
        # Apply filters
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        document_type = self.request.GET.get('document_type')
        if document_type:
            queryset = queryset.filter(document__document_type_id=document_type)
        
        return queryset.order_by('-started_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter options
        context['workflow_statuses'] = [
            (status.value, status.value.title()) for status in WorkflowStepStatus
        ]
        context['document_types'] = DocumentType.objects.all()
        
        # Current filters
        context['current_filters'] = {
            'status': self.request.GET.get('status', ''),
            'document_type': self.request.GET.get('document_type', '')
        }
        
        return context

class WorkflowDetailView(LoginRequiredMixin, DetailView):
    """Detajet e workflow"""
    model = DocumentWorkflow
    template_name = 'document_editor/workflows/detail.html'
    context_object_name = 'workflow'

    def get_queryset(self):
        return DocumentWorkflow.objects.select_related(
            'document', 'template'
        ).prefetch_related(
            'steps__assigned_users',
            'steps__actions__user'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        workflow = self.object
        
        # Add workflow steps with details
        steps = workflow.steps.all().order_by('step_number')
        context['workflow_steps'] = steps
        
        # Add current step details
        if workflow.current_step > 0:
            try:
                current_step = steps.get(step_number=workflow.current_step)
                context['current_step'] = current_step
                context['can_act'] = current_step.assigned_users.filter(id=self.request.user.id).exists()
            except WorkflowStep.DoesNotExist:
                context['current_step'] = None
                context['can_act'] = False
        else:
            context['current_step'] = None
            context['can_act'] = False
        
        # Add action form if user can act
        if context.get('can_act'):
            context['action_form'] = WorkflowActionForm()
        
        # Add timeline
        all_actions = WorkflowAction.objects.filter(
            step__workflow=workflow
        ).select_related('user', 'step').order_by('-created_at')
        context['workflow_timeline'] = all_actions[:20]
        
        # Add permissions
        context['can_manage'] = (
            self.request.user.role == 'admin' or
            workflow.document.owned_by == self.request.user
        )
        
        return context

class WorkflowTemplateListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Lista e workflow template-ve"""
    model = WorkflowTemplate
    template_name = 'document_editor/workflows/templates/list.html'
    context_object_name = 'templates'
    paginate_by = 20

    def test_func(self):
        return self.request.user.role in ['admin', 'lawyer']

    def get_queryset(self):
        return WorkflowTemplate.objects.prefetch_related('document_types').order_by('-updated_at')

class WorkflowTemplateDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Detajet e workflow template"""
    model = WorkflowTemplate
    template_name = 'document_editor/workflows/templates/detail.html'
    context_object_name = 'template'

    def test_func(self):
        return self.request.user.role in ['admin', 'lawyer']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        template = self.object
        
        # Parse steps configuration
        context['steps_config'] = template.steps_config
        
        # Add usage statistics
        context['usage_stats'] = {
            'workflows_created': DocumentWorkflow.objects.filter(template=template).count(),
            'success_rate': self._calculate_success_rate(template),
            'avg_completion_time': self._calculate_avg_completion_time(template)
        }
        
        return context

    def _calculate_success_rate(self, template):
        """Calculate workflow success rate"""
        total_workflows = DocumentWorkflow.objects.filter(template=template).count()
        if total_workflows == 0:
            return 0
        
        completed_workflows = DocumentWorkflow.objects.filter(
            template=template,
            status=WorkflowStepStatus.COMPLETED.value
        ).count()
        
        return round((completed_workflows / total_workflows) * 100, 1)

    def _calculate_avg_completion_time(self, template):
        """Calculate average completion time"""
        completed_workflows = DocumentWorkflow.objects.filter(
            template=template,
            status=WorkflowStepStatus.COMPLETED.value,
            completed_at__isnull=False
        )
        
        if not completed_workflows.exists():
            return None
        
        total_hours = 0
        count = 0
        
        for workflow in completed_workflows:
            duration = workflow.completed_at - workflow.started_at
            total_hours += duration.total_seconds() / 3600
            count += 1
        
        if count == 0:
            return None
        
        avg_hours = total_hours / count
        if avg_hours < 24:
            return f"{avg_hours:.1f} hours"
        else:
            return f"{avg_hours/24:.1f} days"

class WorkflowTemplateCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Krijimi i workflow template"""
    model = WorkflowTemplate
    form_class = WorkflowTemplateForm
    template_name = 'document_editor/workflows/templates/create.html'

    def test_func(self):
        return self.request.user.role in ['admin', 'lawyer']

    def form_valid(self, form):
        template = form.save(commit=False)
        template.created_by = self.request.user
        
        # Parse steps configuration from form data
        steps_config = self._parse_steps_from_form()
        template.steps_config = steps_config
        
        template.save()
        form.save_m2m()  # Save document_types
        
        messages.success(self.request, f"Workflow template '{template.name}' created successfully!")
        return redirect('document_editor:workflow_template_detail', pk=template.pk)

    def _parse_steps_from_form(self):
        """Parse workflow steps from form data"""
        steps = []
        step_count = int(self.request.POST.get('step_count', 0))
        
        for i in range(step_count):
            step_data = {
                'name': self.request.POST.get(f'step_{i}_name', ''),
                'type': self.request.POST.get(f'step_{i}_type', 'review'),
                'description': self.request.POST.get(f'step_{i}_description', ''),
                'deadline_hours': int(self.request.POST.get(f'step_{i}_deadline', 24)),
                'required_approvals': int(self.request.POST.get(f'step_{i}_approvals', 1)),
                'assigned_roles': self.request.POST.getlist(f'step_{i}_roles'),
                'allowed_actions': self.request.POST.getlist(f'step_{i}_actions')
            }
            steps.append(step_data)
        
        return steps

@login_required
@require_POST
def workflow_action_execute(request, step_id):
    """Execute workflow action"""
    try:
        step = get_object_or_404(WorkflowStep, id=step_id)
        
        # Check permissions
        if not step.assigned_users.filter(id=request.user.id).exists():
            if request.user.role != 'admin':
                return JsonResponse({'success': False, 'error': 'Permission denied'})
        
        action_type_str = request.POST.get('action_type')
        comment = request.POST.get('comment', '')
        
        try:
            action_type = ActionType(action_type_str)
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Invalid action type'})
        
        # Execute action using workflow engine
        workflow_engine = WorkflowEngine()
        success = workflow_engine.execute_action(
            step=step,
            action_type=action_type,
            user=request.user,
            comment=comment,
            metadata={'ip_address': request.META.get('REMOTE_ADDR')}
        )
        
        if success:
            # Refresh step to get updated status
            step.refresh_from_db()
            
            return JsonResponse({
                'success': True,
                'action': action_type.value,
                'step_status': step.status,
                'workflow_status': step.workflow.status,
                'message': f'Action "{action_type.value}" executed successfully'
            })
        else:
            return JsonResponse({'success': False, 'error': 'Action execution failed'})
        
    except (ValidationError, PermissionDenied) as e:
        return JsonResponse({'success': False, 'error': str(e)})
    except Exception as e:
        logger.error(f"Workflow action execute error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def workflow_create(request, document_id):
    """Create workflow for document"""
    try:
        document = get_object_or_404(Document, id=document_id)
        
        # Check permissions
        if not (document.owned_by == request.user or request.user.role == 'admin'):
            return JsonResponse({'success': False, 'error': 'Permission denied'})
        
        # Check if workflow already exists
        if hasattr(document, 'workflow'):
            return JsonResponse({'success': False, 'error': 'Workflow already exists for this document'})
        
        template_id = request.POST.get('template_id')
        workflow_engine = WorkflowEngine()
        
        if template_id:
            template = get_object_or_404(WorkflowTemplate, id=template_id)
            workflow = workflow_engine.create_workflow(document, template)
        else:
            workflow = workflow_engine.create_workflow(document)
        
        return JsonResponse({
            'success': True,
            'workflow_id': workflow.id,
            'redirect_url': reverse('document_editor:workflow_detail', kwargs={'pk': workflow.pk})
        })
        
    except ValidationError as e:
        return JsonResponse({'success': False, 'error': str(e)})
    except Exception as e:
        logger.error(f"Workflow create error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def workflow_cancel(request, workflow_id):
    """Cancel workflow"""
    try:
        workflow = get_object_or_404(DocumentWorkflow, id=workflow_id)
        
        # Check permissions
        if not (workflow.document.owned_by == request.user or request.user.role == 'admin'):
            return JsonResponse({'success': False, 'error': 'Permission denied'})
        
        # Update workflow status
        workflow.status = WorkflowStepStatus.CANCELLED.value
        workflow.completed_at = timezone.now()
        workflow.save()
        
        # Update current step
        try:
            current_step = workflow.steps.get(step_number=workflow.current_step)
            current_step.status = WorkflowStepStatus.CANCELLED.value
            current_step.completed_at = timezone.now()
            current_step.save()
        except WorkflowStep.DoesNotExist:
            pass
        
        # Log action
        DocumentAuditLog.objects.create(
            document=workflow.document,
            user=request.user,
            action='workflow_cancelled',
            details=f"Workflow cancelled by {request.user.username}"
        )
        
        messages.success(request, 'Workflow cancelled successfully')
        
        return JsonResponse({
            'success': True,
            'redirect_url': reverse('document_editor:document_detail', kwargs={'pk': workflow.document.pk})
        })
        
    except Exception as e:
        logger.error(f"Workflow cancel error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def workflow_step_details(request, step_id):
    """Get workflow step details"""
    try:
        step = get_object_or_404(
            WorkflowStep.objects.select_related('workflow__document').prefetch_related(
                'assigned_users', 'actions__user'
            ),
            id=step_id
        )
        
        # Check permissions
        user = request.user
        can_view = (
            user.role == 'admin' or
            step.workflow.document.owned_by == user or
            step.assigned_users.filter(id=user.id).exists()
        )
        
        if not can_view:
            return JsonResponse({'success': False, 'error': 'Permission denied'})
        
        # Prepare step data
        step_data = {
            'id': step.id,
            'name': step.name,
            'type': step.type,
            'description': step.description,
            'status': step.status,
            'started_at': step.started_at.isoformat() if step.started_at else None,
            'completed_at': step.completed_at.isoformat() if step.completed_at else None,
            'deadline': step.deadline.isoformat() if step.deadline else None,
            'assigned_users': [
                {
                    'id': user.id,
                    'username': user.username,
                    'full_name': user.get_full_name()
                } for user in step.assigned_users.all()
            ],
            'actions': [
                {
                    'id': action.id,
                    'action_type': action.action_type,
                    'comment': action.comment,
                    'user': action.user.username,
                    'created_at': action.created_at.isoformat()
                } for action in step.actions.all()[:10]
            ],
            'config': step.config
        }
        
        return JsonResponse({
            'success': True,
            'step': step_data
        })
        
    except Exception as e:
        logger.error(f"Workflow step details error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def workflow_analytics(request):
    """Workflow analytics dashboard"""
    if request.user.role not in ['admin', 'lawyer']:
        raise PermissionDenied("Access denied")
    
    # Get date range
    from datetime import datetime, timedelta
    
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)  # Last 30 days
    
    # Workflow statistics
    workflows = DocumentWorkflow.objects.filter(
        started_at__gte=start_date,
        started_at__lte=end_date
    )
    
    stats = {
        'total_workflows': workflows.count(),
        'completed_workflows': workflows.filter(status=WorkflowStepStatus.COMPLETED.value).count(),
        'pending_workflows': workflows.filter(status=WorkflowStepStatus.IN_PROGRESS.value).count(),
        'cancelled_workflows': workflows.filter(status=WorkflowStepStatus.CANCELLED.value).count(),
    }
    
    # Success rate
    if stats['total_workflows'] > 0:
        stats['success_rate'] = round((stats['completed_workflows'] / stats['total_workflows']) * 100, 1)
    else:
        stats['success_rate'] = 0
    
    # Workflow by template
    template_stats = workflows.values('template__name').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Average completion time
    completed_workflows = workflows.filter(
        status=WorkflowStepStatus.COMPLETED.value,
        completed_at__isnull=False
    )
    
    if completed_workflows.exists():
        total_hours = sum([
            (w.completed_at - w.started_at).total_seconds() / 3600
            for w in completed_workflows
        ])
        avg_completion_hours = total_hours / completed_workflows.count()
    else:
        avg_completion_hours = 0
    
    context = {
        'stats': stats,
        'template_stats': template_stats,
        'avg_completion_hours': round(avg_completion_hours, 1),
        'date_range': {
            'start': start_date.strftime('%Y-%m-%d'),
            'end': end_date.strftime('%Y-%m-%d')
        }
    }
    
    return render(request, 'document_editor/workflows/analytics.html', context)

@login_required
@require_POST
def workflow_step_assign(request, step_id):
    """Assign user to workflow step"""
    try:
        step = get_object_or_404(WorkflowStep, id=step_id)
        
        # Check permissions
        if request.user.role != 'admin' and step.workflow.document.owned_by != request.user:
            return JsonResponse({'success': False, 'error': 'Permission denied'})
        
        user_id = request.POST.get('user_id')
        if not user_id:
            return JsonResponse({'success': False, 'error': 'User ID required'})
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            assignee = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User not found'})
        
        # Add user to step
        from ..advanced_features.workflow_system import WorkflowStepAssignment
        
        assignment, created = WorkflowStepAssignment.objects.get_or_create(
            step=step,
            user=assignee,
            defaults={'assigned_by': request.user}
        )
        
        if created:
            # Send notification to assigned user
            # TODO: Implement notification system
            pass
        
        return JsonResponse({
            'success': True,
            'assigned': created,
            'user': {
                'id': assignee.id,
                'username': assignee.username,
                'full_name': assignee.get_full_name()
            }
        })
        
    except Exception as e:
        logger.error(f"Workflow step assign error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def workflow_export(request, workflow_id):
    """Export workflow data"""
    try:
        workflow = get_object_or_404(DocumentWorkflow, id=workflow_id)
        
        # Check permissions
        if not (workflow.document.owned_by == request.user or request.user.role == 'admin'):
            return JsonResponse({'success': False, 'error': 'Permission denied'})
        
        # Prepare export data
        export_data = {
            'workflow': {
                'id': workflow.id,
                'document_title': workflow.document.title,
                'template_name': workflow.template.name if workflow.template else 'No template',
                'status': workflow.status,
                'started_at': workflow.started_at.isoformat(),
                'completed_at': workflow.completed_at.isoformat() if workflow.completed_at else None,
                'total_steps': workflow.total_steps,
                'completed_steps': workflow.completed_steps,
                'progress_percentage': workflow.progress_percentage
            },
            'steps': []
        }
        
        # Add steps data
        for step in workflow.steps.all():
            step_data = {
                'step_number': step.step_number,
                'name': step.name,
                'type': step.type,
                'status': step.status,
                'started_at': step.started_at.isoformat() if step.started_at else None,
                'completed_at': step.completed_at.isoformat() if step.completed_at else None,
                'deadline': step.deadline.isoformat() if step.deadline else None,
                'assigned_users': [user.username for user in step.assigned_users.all()],
                'actions': []
            }
            
            # Add actions
            for action in step.actions.all():
                action_data = {
                    'action_type': action.action_type,
                    'user': action.user.username,
                    'comment': action.comment,
                    'created_at': action.created_at.isoformat()
                }
                step_data['actions'].append(action_data)
            
            export_data['steps'].append(step_data)
        
        # Export metadata
        export_data['export_info'] = {
            'exported_by': request.user.username,
            'exported_at': timezone.now().isoformat(),
            'version': '1.0'
        }
        
        response = JsonResponse(export_data, json_dumps_params={'indent': 2})
        response['Content-Disposition'] = f'attachment; filename="workflow_{workflow.id}_export.json"'
        
        return response
        
    except Exception as e:
        logger.error(f"Workflow export error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})
