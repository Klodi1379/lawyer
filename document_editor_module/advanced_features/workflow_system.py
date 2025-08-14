"""
Document Workflow System - Sistem i avancuar për menaxhimin e workflow-ve të dokumenteve juridike
Përfshin approval processes, notifications, dhe automated routing
"""

from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import logging

from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.db.models import Q

from ..models.document_models import Document, DocumentStatus, DocumentAuditLog
from ..services.llm_service import LegalLLMService, DocumentContext

User = get_user_model()
logger = logging.getLogger(__name__)

class WorkflowStepType(Enum):
    """Llojet e hapave në workflow"""
    REVIEW = "review"
    APPROVAL = "approval"
    SIGNATURE = "signature"
    NOTIFICATION = "notification"
    AUTOMATED_CHECK = "automated_check"
    CONDITIONAL = "conditional"
    PARALLEL = "parallel"
    DELAY = "delay"

class WorkflowStepStatus(Enum):
    """Statuset e hapave të workflow"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    ERROR = "error"

class ActionType(Enum):
    """Llojet e veprimeve në workflow"""
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"
    DELEGATE = "delegate"
    ESCALATE = "escalate"
    COMPLETE = "complete"

@dataclass
class WorkflowAction:
    """Veprim në workflow"""
    type: ActionType
    user: User
    comment: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=timezone.now)

@dataclass
class WorkflowStepConfig:
    """Konfigurimi i një hapi workflow"""
    name: str
    type: WorkflowStepType
    description: str = ""
    
    # Assignee configuration
    assigned_users: List[User] = field(default_factory=list)
    assigned_roles: List[str] = field(default_factory=list)
    auto_assign_rules: Dict[str, Any] = field(default_factory=dict)
    
    # Timing
    deadline_hours: Optional[int] = None
    reminder_hours: List[int] = field(default_factory=list)  # Reminder intervals
    
    # Conditions
    conditions: Dict[str, Any] = field(default_factory=dict)
    required_approvals: int = 1  # Për parallel approvals
    
    # Actions
    allowed_actions: List[ActionType] = field(default_factory=list)
    auto_actions: Dict[str, Any] = field(default_factory=dict)
    
    # Notifications
    notification_templates: Dict[str, str] = field(default_factory=dict)
    
    # LLM Integration
    ai_checks: Dict[str, Any] = field(default_factory=dict)

# Django Models for Workflow System

class WorkflowTemplate(models.Model):
    """Template për workflow-et e dokumenteve"""
    name = models.CharField(max_length=255, verbose_name="Emri")
    description = models.TextField(blank=True, verbose_name="Përshkrimi")
    document_types = models.ManyToManyField(
        'document_editor_module.DocumentType',
        verbose_name="Llojet e Dokumenteve"
    )
    
    # Workflow configuration as JSON
    steps_config = models.JSONField(default=list, verbose_name="Konfigurimi i Hapave")
    
    # Metadata
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Template Workflow"
        verbose_name_plural = "Template Workflow-sh"
        ordering = ['name']

    def __str__(self):
        return self.name

class DocumentWorkflow(models.Model):
    """Workflow instance për një dokument specifik"""
    document = models.OneToOneField(
        Document, 
        on_delete=models.CASCADE,
        related_name='workflow'
    )
    template = models.ForeignKey(
        WorkflowTemplate, 
        on_delete=models.PROTECT,
        verbose_name="Template"
    )
    
    # Status tracking
    current_step = models.PositiveIntegerField(default=0, verbose_name="Hapi Aktual")
    status = models.CharField(
        max_length=20,
        choices=[(status.value, status.value.title()) for status in WorkflowStepStatus],
        default=WorkflowStepStatus.PENDING.value
    )
    
    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    
    # Progress tracking
    total_steps = models.PositiveIntegerField(default=0)
    completed_steps = models.PositiveIntegerField(default=0)
    
    # Metadata
    data = models.JSONField(default=dict, blank=True)  # Extra workflow data
    
    class Meta:
        verbose_name = "Workflow Dokumenti"
        verbose_name_plural = "Workflow Dokumentesh"

    def __str__(self):
        return f"Workflow për {self.document.title}"

    @property
    def progress_percentage(self) -> int:
        """Përqindja e përfundimit"""
        if self.total_steps == 0:
            return 0
        return int((self.completed_steps / self.total_steps) * 100)

    @property
    def is_overdue(self) -> bool:
        """A është vonuar workflow"""
        return self.deadline and timezone.now() > self.deadline

class WorkflowStep(models.Model):
    """Hapi individual në workflow"""
    workflow = models.ForeignKey(
        DocumentWorkflow, 
        on_delete=models.CASCADE,
        related_name='steps'
    )
    step_number = models.PositiveIntegerField(verbose_name="Numri i Hapit")
    name = models.CharField(max_length=255, verbose_name="Emri")
    type = models.CharField(
        max_length=20,
        choices=[(step_type.value, step_type.value.title()) for step_type in WorkflowStepType]
    )
    description = models.TextField(blank=True, verbose_name="Përshkrimi")
    
    # Assignment
    assigned_users = models.ManyToManyField(
        User, 
        through='WorkflowStepAssignment',
        related_name='workflow_steps'
    )
    
    # Status and timing
    status = models.CharField(
        max_length=20,
        choices=[(status.value, status.value.title()) for status in WorkflowStepStatus],
        default=WorkflowStepStatus.PENDING.value
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    
    # Configuration
    config = models.JSONField(default=dict, blank=True)
    
    # Results
    result_data = models.JSONField(default=dict, blank=True)
    
    class Meta:
        unique_together = ['workflow', 'step_number']
        ordering = ['step_number']

    def __str__(self):
        return f"Hapi {self.step_number}: {self.name}"

class WorkflowStepAssignment(models.Model):
    """Assignment i një hapi tek user"""
    step = models.ForeignKey(WorkflowStep, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='assigned_workflow_steps'
    )
    
    # Status
    is_primary = models.BooleanField(default=True)  # Primary vs backup assignee
    notification_sent = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['step', 'user']

class WorkflowAction(models.Model):
    """Veprimet e kryera në workflow"""
    step = models.ForeignKey(
        WorkflowStep, 
        on_delete=models.CASCADE,
        related_name='actions'
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action_type = models.CharField(
        max_length=20,
        choices=[(action.value, action.value.title()) for action in ActionType]
    )
    
    # Content
    comment = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action_type} nga {self.user.username}"

# Service Classes

class WorkflowEngine:
    """Engine kryesor për menaxhimin e workflow-ve"""
    
    def __init__(self):
        self.llm_service = LegalLLMService()
        
    def create_workflow(self, document: Document, template: WorkflowTemplate = None) -> DocumentWorkflow:
        """Krijn një workflow të ri për dokument"""
        if not template:
            # Gjej template automatikisht bazuar në document type
            template = self._find_default_template(document)
            
        if not template:
            raise ValidationError("Nuk u gjet template workflow për këtë lloj dokumenti")
        
        with transaction.atomic():
            # Krijo workflow instance
            workflow = DocumentWorkflow.objects.create(
                document=document,
                template=template,
                total_steps=len(template.steps_config)
            )
            
            # Krijo hapat
            for i, step_config in enumerate(template.steps_config):
                self._create_workflow_step(workflow, i, step_config)
            
            # Fillo workflow
            self._start_workflow(workflow)
            
            # Log action
            DocumentAuditLog.objects.create(
                document=document,
                action='workflow_created',
                details=f"Workflow krijuar me template: {template.name}",
                metadata={
                    'template_id': template.id,
                    'total_steps': workflow.total_steps
                }
            )
            
        return workflow
    
    def _find_default_template(self, document: Document) -> Optional[WorkflowTemplate]:
        """Gjej template default për dokument"""
        return WorkflowTemplate.objects.filter(
            document_types=document.document_type,
            is_active=True
        ).first()
    
    def _create_workflow_step(self, workflow: DocumentWorkflow, step_index: int, config: Dict[str, Any]):
        """Krijn një hap workflow"""
        step = WorkflowStep.objects.create(
            workflow=workflow,
            step_number=step_index + 1,
            name=config.get('name', f'Hapi {step_index + 1}'),
            type=config.get('type', WorkflowStepType.REVIEW.value),
            description=config.get('description', ''),
            config=config,
            deadline=self._calculate_step_deadline(config)
        )
        
        # Assign users
        self._assign_step_users(step, config)
        
        return step
    
    def _calculate_step_deadline(self, config: Dict[str, Any]) -> Optional[datetime]:
        """Kalkulon deadline për një hap"""
        deadline_hours = config.get('deadline_hours')
        if deadline_hours:
            return timezone.now() + timedelta(hours=deadline_hours)
        return None
    
    def _assign_step_users(self, step: WorkflowStep, config: Dict[str, Any]):
        """Assign users në një hap"""
        # Assigned users directly
        user_ids = config.get('assigned_users', [])
        for user_id in user_ids:
            try:
                user = User.objects.get(id=user_id)
                WorkflowStepAssignment.objects.create(
                    step=step,
                    user=user,
                    is_primary=True
                )
            except User.DoesNotExist:
                continue
        
        # Assigned by roles
        roles = config.get('assigned_roles', [])
        for role in roles:
            users = User.objects.filter(role=role)
            for user in users:
                WorkflowStepAssignment.objects.get_or_create(
                    step=step,
                    user=user,
                    defaults={'is_primary': False}
                )
        
        # Auto-assign rules (AI-powered)
        auto_assign_rules = config.get('auto_assign_rules', {})
        if auto_assign_rules:
            self._apply_auto_assign_rules(step, auto_assign_rules)
    
    def _apply_auto_assign_rules(self, step: WorkflowStep, rules: Dict[str, Any]):
        """Apliko rregulla automatike për assignment"""
        # Implemento logjikën për auto-assignment
        # Mund të përdorë AI për të sugjeruar reviewers bazuar në dokumentin
        pass
    
    def _start_workflow(self, workflow: DocumentWorkflow):
        """Fillo workflow"""
        workflow.status = WorkflowStepStatus.IN_PROGRESS.value
        workflow.save()
        
        # Fillo hapin e parë
        first_step = workflow.steps.first()
        if first_step:
            self._start_step(first_step)
    
    def _start_step(self, step: WorkflowStep):
        """Fillo një hap specifik"""
        step.status = WorkflowStepStatus.IN_PROGRESS.value
        step.started_at = timezone.now()
        step.save()
        
        # Dërgo notification
        self._send_step_notifications(step, 'started')
        
        # Kryej automated checks nëse ka
        if step.type == WorkflowStepType.AUTOMATED_CHECK.value:
            self._run_automated_checks(step)
    
    def execute_action(self, 
                      step: WorkflowStep, 
                      action_type: ActionType, 
                      user: User,
                      comment: str = "",
                      metadata: Dict[str, Any] = None) -> bool:
        """Ekzekuto një veprim në workflow"""
        
        # Kontrollo permissions
        if not self._can_user_act_on_step(user, step):
            raise PermissionDenied("Nuk keni leje për të kryer këtë veprim")
        
        # Kontrollo nëse veprimi është i lejuar
        allowed_actions = step.config.get('allowed_actions', [action.value for action in ActionType])
        if action_type.value not in allowed_actions:
            raise ValidationError(f"Veprimi {action_type.value} nuk është i lejuar për këtë hap")
        
        metadata = metadata or {}
        
        with transaction.atomic():
            # Regjistroj veprimin
            workflow_action = WorkflowAction.objects.create(
                step=step,
                user=user,
                action_type=action_type.value,
                comment=comment,
                metadata=metadata
            )
            
            # Procesoj veprimin
            success = self._process_action(step, action_type, user, workflow_action)
            
            if success:
                # Log në document audit
                DocumentAuditLog.objects.create(
                    document=step.workflow.document,
                    user=user,
                    action='workflow_action',
                    details=f"Veprim: {action_type.value} në hapin: {step.name}",
                    metadata={
                        'step_id': step.id,
                        'action_type': action_type.value,
                        'comment': comment
                    }
                )
        
        return success
    
    def _can_user_act_on_step(self, user: User, step: WorkflowStep) -> bool:
        """Kontrollon nëse user mund të veprojë në hap"""
        # Kontrollo nëse është assigned
        if step.assigned_users.filter(id=user.id).exists():
            return True
        
        # Kontrollo permissions të tjera
        if user.has_perm('document_editor_module.manage_workflows'):
            return True
        
        # Kontrollo nëse është owner i dokumentit
        if step.workflow.document.owned_by == user:
            return True
        
        return False
    
    def _process_action(self, 
                       step: WorkflowStep, 
                       action_type: ActionType, 
                       user: User,
                       action: WorkflowAction) -> bool:
        """Procesoj veprimin e kryer"""
        
        if action_type == ActionType.APPROVE:
            return self._handle_approval(step, user, action)
        elif action_type == ActionType.REJECT:
            return self._handle_rejection(step, user, action)
        elif action_type == ActionType.REQUEST_CHANGES:
            return self._handle_change_request(step, user, action)
        elif action_type == ActionType.DELEGATE:
            return self._handle_delegation(step, user, action)
        elif action_type == ActionType.COMPLETE:
            return self._handle_completion(step, user, action)
        
        return False
    
    def _handle_approval(self, step: WorkflowStep, user: User, action: WorkflowAction) -> bool:
        """Menaxho aprovimin"""
        required_approvals = step.config.get('required_approvals', 1)
        current_approvals = step.actions.filter(action_type=ActionType.APPROVE.value).count()
        
        if current_approvals >= required_approvals:
            # Complete step
            step.status = WorkflowStepStatus.COMPLETED.value
            step.completed_at = timezone.now()
            step.save()
            
            # Move to next step
            self._advance_workflow(step.workflow)
            
            return True
        
        return True  # Approved but waiting for more approvals
    
    def _handle_rejection(self, step: WorkflowStep, user: User, action: WorkflowAction) -> bool:
        """Menaxho refuzimin"""
        step.status = WorkflowStepStatus.REJECTED.value
        step.completed_at = timezone.now()
        step.save()
        
        # Handle rejection based on config
        rejection_action = step.config.get('on_rejection', 'stop')
        
        if rejection_action == 'stop':
            # Stop entire workflow
            step.workflow.status = WorkflowStepStatus.REJECTED.value
            step.workflow.save()
        elif rejection_action == 'restart':
            # Restart workflow from beginning
            self._restart_workflow(step.workflow)
        elif rejection_action == 'previous_step':
            # Go back to previous step
            self._go_to_previous_step(step.workflow)
        
        return True
    
    def _handle_change_request(self, step: WorkflowStep, user: User, action: WorkflowAction) -> bool:
        """Menaxho kërkesën për ndryshime"""
        # Kthe dokumentin te autor për ndryshime
        step.workflow.document.status = DocumentStatus.objects.get(name='Draft')
        step.workflow.document.save()
        
        # Send notification to document owner
        self._send_change_request_notification(step, action)
        
        return True
    
    def _advance_workflow(self, workflow: DocumentWorkflow):
        """Vazhdo workflow në hapin tjetër"""
        next_step = workflow.steps.filter(
            step_number=workflow.current_step + 1
        ).first()
        
        if next_step:
            workflow.current_step = next_step.step_number
            workflow.completed_steps += 1
            workflow.save()
            
            self._start_step(next_step)
        else:
            # Complete workflow
            self._complete_workflow(workflow)
    
    def _complete_workflow(self, workflow: DocumentWorkflow):
        """Përfundo workflow"""
        workflow.status = WorkflowStepStatus.COMPLETED.value
        workflow.completed_at = timezone.now()
        workflow.completed_steps = workflow.total_steps
        workflow.save()
        
        # Update document status
        final_status = DocumentStatus.objects.get(name='Approved')
        workflow.document.status = final_status
        workflow.document.save()
        
        # Send completion notifications
        self._send_workflow_completion_notification(workflow)
    
    def _send_step_notifications(self, step: WorkflowStep, event_type: str):
        """Dërgo notification për një hap"""
        # Get assigned users
        assigned_users = step.assigned_users.all()
        
        for user in assigned_users:
            try:
                self._send_notification(
                    user=user,
                    subject=f"Workflow Step: {step.name}",
                    template_name=f'workflow_step_{event_type}',
                    context={
                        'step': step,
                        'document': step.workflow.document,
                        'user': user
                    }
                )
                
                # Mark notification as sent
                assignment = WorkflowStepAssignment.objects.get(step=step, user=user)
                assignment.notification_sent = True
                assignment.save()
                
            except Exception as e:
                logger.error(f"Failed to send notification to {user.email}: {str(e)}")
    
    def _send_notification(self, user: User, subject: str, template_name: str, context: Dict[str, Any]):
        """Dërgo notification email"""
        try:
            html_content = render_to_string(f'workflows/emails/{template_name}.html', context)
            text_content = render_to_string(f'workflows/emails/{template_name}.txt', context)
            
            send_mail(
                subject=subject,
                message=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_content,
                fail_silently=False
            )
        except Exception as e:
            logger.error(f"Failed to send email notification: {str(e)}")
    
    def _run_automated_checks(self, step: WorkflowStep):
        """Kryej automated checks me AI"""
        ai_checks = step.config.get('ai_checks', {})
        
        if not ai_checks:
            # Complete step immediately if no checks
            step.status = WorkflowStepStatus.COMPLETED.value
            step.completed_at = timezone.now()
            step.save()
            self._advance_workflow(step.workflow)
            return
        
        document = step.workflow.document
        context = DocumentContext(
            title=document.title,
            content=document.content,
            document_type=document.document_type.name,
            case_type=document.case.case_type if hasattr(document.case, 'case_type') else None
        )
        
        # Run different types of AI checks
        results = {}
        
        for check_type, check_config in ai_checks.items():
            try:
                if check_type == 'compliance_check':
                    result = self.llm_service.analyze_legal_compliance(context, check_config.get('regulations', []))
                elif check_type == 'quality_review':
                    result = self.llm_service.review_document(context, check_config.get('focus_areas', []))
                elif check_type == 'completeness_check':
                    result = self.llm_service.extract_key_information(context, check_config.get('required_info', []))
                else:
                    continue
                
                results[check_type] = {
                    'success': not result.error,
                    'result': result.text if not result.error else result.error,
                    'confidence': result.confidence,
                    'processing_time': result.processing_time
                }
                
            except Exception as e:
                results[check_type] = {
                    'success': False,
                    'error': str(e)
                }
        
        # Store results
        step.result_data = results
        
        # Determine if checks passed
        all_passed = all(result.get('success', False) for result in results.values())
        
        if all_passed:
            step.status = WorkflowStepStatus.COMPLETED.value
            self._advance_workflow(step.workflow)
        else:
            step.status = WorkflowStepStatus.ERROR.value
            # Handle failed checks based on configuration
            self._handle_failed_automated_checks(step, results)
        
        step.completed_at = timezone.now()
        step.save()
    
    def _handle_failed_automated_checks(self, step: WorkflowStep, results: Dict[str, Any]):
        """Menaxho automated checks që dështuan"""
        failure_action = step.config.get('on_failure', 'notify_owner')
        
        if failure_action == 'notify_owner':
            # Notify document owner about issues
            self._send_automated_check_failure_notification(step, results)
        elif failure_action == 'request_review':
            # Add manual review step
            self._add_manual_review_step(step.workflow, results)
        elif failure_action == 'reject':
            # Reject the document
            step.workflow.status = WorkflowStepStatus.REJECTED.value
            step.workflow.save()

def get_workflow_engine() -> WorkflowEngine:
    """Factory function për WorkflowEngine"""
    return WorkflowEngine()
