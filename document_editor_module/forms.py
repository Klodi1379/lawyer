"""
Forms për Document Editor Module
Përfshin të gjitha forms e nevojshme për dokumente, templates, workflows dhe signatures
"""

import json
from typing import Dict, List, Any
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils import timezone

from .models.document_models import (
    Document, DocumentTemplate, DocumentType, DocumentStatus,
    DocumentComment, DocumentSignature
)
from .advanced_features.workflow_system import WorkflowTemplate
from .advanced_features.signature_system import SignatureProvider

User = get_user_model()

class DocumentForm(forms.ModelForm):
    """Form për krijim dhe editim dokumentesh"""
    
    content_html = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
        help_text="HTML version of content for rich text editing"
    )
    
    create_workflow = forms.BooleanField(
        required=False,
        initial=False,
        help_text="Create automatic workflow for this document"
    )
    
    workflow_template = forms.ModelChoiceField(
        queryset=WorkflowTemplate.objects.filter(is_active=True),
        required=False,
        empty_label="Select workflow template",
        help_text="Choose a workflow template to apply"
    )

    class Meta:
        model = Document
        fields = [
            'title', 'description', 'case', 'document_type', 'status', 
            'content', 'content_html', 'template_used'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter document title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Brief description of the document'
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control document-editor',
                'rows': 20,
                'placeholder': 'Document content...'
            }),
            'case': forms.Select(attrs={'class': 'form-select'}),
            'document_type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'template_used': forms.Select(attrs={'class': 'form-select'})
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter choices based on user permissions
        if self.user:
            if self.user.role == 'client':
                # Clients can only see their own cases
                from cases.models import Case
                self.fields['case'].queryset = Case.objects.filter(client__user=self.user)
                # Remove some fields for clients
                del self.fields['workflow_template']
                del self.fields['create_workflow']
            elif self.user.role in ['lawyer', 'paralegal']:
                from cases.models import Case
                self.fields['case'].queryset = Case.objects.filter(
                    Q(assigned_to=self.user) | Q(client__user=self.user)
                )
        
        # Make template_used optional and add empty option
        self.fields['template_used'].required = False
        self.fields['template_used'].empty_label = "No template"

    def clean_title(self):
        title = self.cleaned_data.get('title')
        if len(title) < 3:
            raise ValidationError("Title must be at least 3 characters long")
        return title

    def clean_content(self):
        content = self.cleaned_data.get('content')
        if not content or len(content.strip()) < 10:
            raise ValidationError("Document content is required and must be at least 10 characters")
        return content

class DocumentCommentForm(forms.ModelForm):
    """Form për komente në dokument"""
    
    position_start = forms.IntegerField(
        widget=forms.HiddenInput(),
        required=False
    )
    position_end = forms.IntegerField(
        widget=forms.HiddenInput(),
        required=False
    )
    selected_text = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )
    parent_comment_id = forms.IntegerField(
        widget=forms.HiddenInput(),
        required=False
    )

    class Meta:
        model = DocumentComment
        fields = ['content', 'position_start', 'position_end', 'selected_text']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Add your comment...',
                'required': True
            })
        }

    def clean_content(self):
        content = self.cleaned_data.get('content')
        if not content or len(content.strip()) < 1:
            raise ValidationError("Comment content is required")
        return content.strip()

class DocumentUploadForm(forms.Form):
    """Form për upload të dokumenteve"""
    
    file = forms.FileField(
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'docx', 'doc', 'txt', 'html'])],
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.docx,.doc,.txt,.html'
        }),
        help_text="Supported formats: PDF, DOCX, DOC, TXT, HTML (Max 10MB)"
    )
    title = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Document title'
        })
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional description'
        })
    )
    case = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    document_type = forms.ModelChoiceField(
        queryset=DocumentType.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    extract_content = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Extract text content from uploaded file"
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            from cases.models import Case
            if user.role == 'client':
                self.fields['case'].queryset = Case.objects.filter(client__user=user)
            else:
                self.fields['case'].queryset = Case.objects.filter(
                    Q(assigned_to=user) | Q(client__user=user)
                )

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            if file.size > 10 * 1024 * 1024:  # 10MB limit
                raise ValidationError("File size cannot exceed 10MB")
        return file

class TemplateForm(forms.ModelForm):
    """Form për template-t e dokumenteve"""
    
    variables_json = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
        help_text="JSON representation of template variables"
    )

    class Meta:
        model = DocumentTemplate
        fields = ['name', 'description', 'category', 'content', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Template name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Template description'
            }),
            'category': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Contract, Complaint, Motion',
                'list': 'category-suggestions'
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control template-editor',
                'rows': 20,
                'placeholder': 'Template content with Jinja2 syntax...'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if len(name) < 3:
            raise ValidationError("Template name must be at least 3 characters long")
        
        # Check for duplicate names (excluding current instance if editing)
        queryset = DocumentTemplate.objects.filter(name=name)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        
        if queryset.exists():
            raise ValidationError("A template with this name already exists")
        
        return name

    def clean_content(self):
        content = self.cleaned_data.get('content')
        if not content or len(content.strip()) < 10:
            raise ValidationError("Template content is required and must be at least 10 characters")
        
        # Basic validation for Jinja2 syntax
        try:
            from jinja2 import Environment, meta
            env = Environment()
            env.parse(content)
        except Exception as e:
            raise ValidationError(f"Template syntax error: {str(e)}")
        
        return content

class TemplateVariableForm(forms.Form):
    """Form për variablat e template"""
    
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'variable_name'
        })
    )
    label = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Human readable label'
        })
    )
    type = forms.ChoiceField(
        choices=[
            ('text', 'Text'),
            ('number', 'Number'),
            ('date', 'Date'),
            ('boolean', 'Boolean'),
            ('choice', 'Choice'),
            ('multiple_choice', 'Multiple Choice')
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Variable description'
        })
    )
    required = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    default_value = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Default value'
        })
    )
    choices = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'One choice per line (for choice fields)'
        }),
        help_text="For choice fields, enter one option per line"
    )

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name.isidentifier():
            raise ValidationError("Variable name must be a valid Python identifier")
        return name

class WorkflowTemplateForm(forms.ModelForm):
    """Form për workflow templates"""
    
    steps_json = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
        help_text="JSON representation of workflow steps"
    )

    class Meta:
        model = WorkflowTemplate
        fields = ['name', 'description', 'document_types', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Workflow template name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Workflow description'
            }),
            'document_types': forms.SelectMultiple(attrs={
                'class': 'form-select',
                'multiple': True
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

    def clean_steps_json(self):
        steps_json = self.cleaned_data.get('steps_json', '[]')
        try:
            steps = json.loads(steps_json)
            if not isinstance(steps, list):
                raise ValidationError("Steps must be a list")
            if len(steps) == 0:
                raise ValidationError("At least one workflow step is required")
            return steps
        except json.JSONDecodeError:
            raise ValidationError("Invalid JSON format for steps")

class WorkflowActionForm(forms.Form):
    """Form për workflow actions"""
    
    action_type = forms.ChoiceField(
        choices=[
            ('approve', 'Approve'),
            ('reject', 'Reject'),
            ('request_changes', 'Request Changes'),
            ('delegate', 'Delegate'),
            ('complete', 'Complete')
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional comment for this action'
        })
    )
    delegate_to = forms.ModelChoiceField(
        queryset=User.objects.filter(role__in=['lawyer', 'paralegal', 'admin']),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Required only for delegation actions"
    )

    def clean(self):
        cleaned_data = super().clean()
        action_type = cleaned_data.get('action_type')
        delegate_to = cleaned_data.get('delegate_to')
        
        if action_type == 'delegate' and not delegate_to:
            raise ValidationError("Delegate to user is required for delegation actions")
        
        return cleaned_data

class SignatureRequestForm(forms.Form):
    """Form për signature requests"""
    
    document = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    title = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Signature request title (optional)'
        })
    )
    message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Message to signers (optional)'
        })
    )
    provider = forms.ChoiceField(
        choices=[(p.value, p.value.title()) for p in SignatureProvider],
        initial=SignatureProvider.INTERNAL.value,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    signers_json = forms.CharField(
        widget=forms.HiddenInput(),
        help_text="JSON representation of signers"
    )
    signature_fields_json = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
        help_text="JSON representation of signature fields"
    )
    expires_in_days = forms.IntegerField(
        initial=30,
        min_value=1,
        max_value=365,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '1',
            'max': '365'
        }),
        help_text="Days until the signature request expires"
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            # Filter documents user can request signatures for
            self.fields['document'].queryset = Document.objects.filter(
                Q(owned_by=user) | Q(case__assigned_to=user)
            ).select_related('case', 'document_type')

    def clean_signers_json(self):
        signers_json = self.cleaned_data.get('signers_json', '[]')
        try:
            signers = json.loads(signers_json)
            if not isinstance(signers, list):
                raise ValidationError("Signers must be a list")
            if len(signers) == 0:
                raise ValidationError("At least one signer is required")
            
            # Validate each signer
            for i, signer in enumerate(signers):
                if not isinstance(signer, dict):
                    raise ValidationError(f"Signer {i+1} must be an object")
                
                required_fields = ['name', 'email']
                for field in required_fields:
                    if field not in signer or not signer[field]:
                        raise ValidationError(f"Signer {i+1} is missing required field: {field}")
                
                # Validate email
                email = signer['email']
                from django.core.validators import validate_email
                try:
                    validate_email(email)
                except ValidationError:
                    raise ValidationError(f"Signer {i+1} has invalid email: {email}")
            
            return signers
        except json.JSONDecodeError:
            raise ValidationError("Invalid JSON format for signers")

class SigningForm(forms.Form):
    """Form për nënshkrim elektronik"""
    
    signature_data = forms.CharField(
        widget=forms.HiddenInput(),
        help_text="Base64 encoded signature data"
    )
    agree_terms = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="I agree to sign this document electronically"
    )

    def clean_signature_data(self):
        signature_data = self.cleaned_data.get('signature_data')
        if not signature_data:
            raise ValidationError("Signature data is required")
        
        # Basic validation for base64 data
        try:
            import base64
            base64.b64decode(signature_data)
        except Exception:
            raise ValidationError("Invalid signature data format")
        
        return signature_data

class DocumentSearchForm(forms.Form):
    """Form për search dhe filtrim dokumentesh"""
    
    search = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search documents...',
            'autocomplete': 'off'
        })
    )
    document_type = forms.ModelChoiceField(
        queryset=DocumentType.objects.all(),
        required=False,
        empty_label="All types",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    status = forms.ModelChoiceField(
        queryset=DocumentStatus.objects.all(),
        required=False,
        empty_label="All statuses",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    case_type = forms.ChoiceField(
        choices=[
            ('', 'All case types'),
            ('civil', 'Civil'),
            ('criminal', 'Criminal'),
            ('commercial', 'Commercial'),
            ('family', 'Family')
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    created_by = forms.ModelChoiceField(
        queryset=User.objects.filter(role__in=['lawyer', 'paralegal', 'admin']),
        required=False,
        empty_label="Any author",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    sort_by = forms.ChoiceField(
        choices=[
            ('-updated_at', 'Recently updated'),
            ('-created_at', 'Recently created'),
            ('title', 'Title A-Z'),
            ('-title', 'Title Z-A'),
            ('case__title', 'Case A-Z'),
            ('-case__title', 'Case Z-A')
        ],
        initial='-updated_at',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise ValidationError("Start date cannot be after end date")
        
        return cleaned_data

class TemplateUploadForm(forms.Form):
    """Form për upload të template nga JSON"""
    
    file = forms.FileField(
        validators=[FileExtensionValidator(allowed_extensions=['json'])],
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.json'
        }),
        help_text="JSON file exported from another system"
    )
    overwrite_existing = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Overwrite if template with same name exists"
    )

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            if file.size > 5 * 1024 * 1024:  # 5MB limit
                raise ValidationError("File size cannot exceed 5MB")
            
            # Validate JSON structure
            try:
                import json
                content = file.read().decode('utf-8')
                data = json.loads(content)
                
                # Reset file position for later reading
                file.seek(0)
                
                # Validate required fields
                required_fields = ['name', 'category', 'content']
                for field in required_fields:
                    if field not in data:
                        raise ValidationError(f"Missing required field in JSON: {field}")
                        
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON file")
            except UnicodeDecodeError:
                raise ValidationError("File must be UTF-8 encoded")
        
        return file

class BulkActionForm(forms.Form):
    """Form për bulk actions në dokumente"""
    
    action = forms.ChoiceField(
        choices=[
            ('delete', 'Delete selected'),
            ('change_status', 'Change status'),
            ('change_type', 'Change document type'),
            ('assign_to', 'Assign to user'),
            ('add_to_workflow', 'Add to workflow'),
            ('export', 'Export selected')
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    selected_documents = forms.CharField(
        widget=forms.HiddenInput(),
        help_text="Comma-separated list of document IDs"
    )
    
    # Optional fields for specific actions
    new_status = forms.ModelChoiceField(
        queryset=DocumentStatus.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    new_type = forms.ModelChoiceField(
        queryset=DocumentType.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    assign_to_user = forms.ModelChoiceField(
        queryset=User.objects.filter(role__in=['lawyer', 'paralegal', 'admin']),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    workflow_template = forms.ModelChoiceField(
        queryset=WorkflowTemplate.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def clean_selected_documents(self):
        documents_str = self.cleaned_data.get('selected_documents', '')
        if not documents_str:
            raise ValidationError("No documents selected")
        
        try:
            document_ids = [int(id.strip()) for id in documents_str.split(',') if id.strip()]
            if not document_ids:
                raise ValidationError("No valid document IDs provided")
            return document_ids
        except ValueError:
            raise ValidationError("Invalid document ID format")

    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        
        # Validate required fields for specific actions
        if action == 'change_status' and not cleaned_data.get('new_status'):
            raise ValidationError("New status is required for status change action")
        
        if action == 'change_type' and not cleaned_data.get('new_type'):
            raise ValidationError("New type is required for type change action")
        
        if action == 'assign_to' and not cleaned_data.get('assign_to_user'):
            raise ValidationError("User is required for assign action")
        
        if action == 'add_to_workflow' and not cleaned_data.get('workflow_template'):
            raise ValidationError("Workflow template is required for workflow action")
        
        return cleaned_data

# FormSet për multiple template variables
TemplateVariableFormSet = forms.formset_factory(
    TemplateVariableForm,
    extra=0,
    min_num=0,
    validate_min=False,
    can_delete=True
)
