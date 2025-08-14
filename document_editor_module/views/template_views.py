"""
Template Views - Views për menaxhimin e template-ve juridikë
Integron LegalTemplateEngine me AI-powered features
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

from ..models.document_models import DocumentTemplate, DocumentType, Document
from ..advanced_features.template_engine import (
    LegalTemplateEngine, TemplateContext, TemplateVariable, TemplateVariableType
)
from ..advanced_features.document_automation import DocumentAutomationEngine
from ..forms import TemplateForm, TemplateVariableFormSet

logger = logging.getLogger(__name__)

class TemplateListView(LoginRequiredMixin, ListView):
    """Lista e template-ve"""
    model = DocumentTemplate
    template_name = 'document_editor/templates/list.html'
    context_object_name = 'templates'
    paginate_by = 20

    def get_queryset(self):
        queryset = DocumentTemplate.objects.select_related('created_by')
        
        # Filter by permissions
        if self.request.user.role != 'admin':
            queryset = queryset.filter(is_active=True)
        
        # Apply search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(category__icontains=search)
            )
        
        # Apply category filter
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        return queryset.order_by('-updated_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add categories
        context['categories'] = DocumentTemplate.objects.values_list(
            'category', flat=True
        ).distinct().order_by('category')
        
        # Add current filters
        context['current_filters'] = {
            'search': self.request.GET.get('search', ''),
            'category': self.request.GET.get('category', '')
        }
        
        # Add statistics
        context['stats'] = {
            'total_templates': DocumentTemplate.objects.count(),
            'active_templates': DocumentTemplate.objects.filter(is_active=True).count(),
            'user_templates': DocumentTemplate.objects.filter(created_by=self.request.user).count()
        }
        
        return context

class TemplateDetailView(LoginRequiredMixin, DetailView):
    """Detajet e template"""
    model = DocumentTemplate
    template_name = 'document_editor/templates/detail.html'
    context_object_name = 'template'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        template = self.object
        
        # Parse template variables
        template_engine = LegalTemplateEngine()
        variables = template_engine.parse_template_variables(template.content)
        context['template_variables'] = variables
        
        # Generate preview
        try:
            preview_content = template_engine.preview_template(template)
            context['preview_content'] = preview_content
        except Exception as e:
            context['preview_error'] = str(e)
        
        # Validate template syntax
        is_valid, errors = template_engine.validate_template_syntax(template.content)
        context['template_valid'] = is_valid
        context['template_errors'] = errors
        
        # Add usage statistics
        context['usage_stats'] = {
            'documents_created': Document.objects.filter(template_used=template).count(),
            'recent_usage': Document.objects.filter(
                template_used=template,
                created_at__gte=timezone.now() - timedelta(days=30)
            ).count()
        }
        
        return context

class TemplateCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Krijimi i template të ri"""
    model = DocumentTemplate
    form_class = TemplateForm
    template_name = 'document_editor/templates/create.html'

    def test_func(self):
        return self.request.user.role in ['admin', 'lawyer']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add document types
        context['document_types'] = DocumentType.objects.all()
        
        # Add existing templates for reference
        context['existing_templates'] = DocumentTemplate.objects.filter(
            is_active=True
        )[:10]
        
        # Add AI capabilities
        context['ai_enabled'] = True
        
        return context

    def form_valid(self, form):
        template = form.save(commit=False)
        template.created_by = self.request.user
        
        # Validate template syntax
        template_engine = LegalTemplateEngine()
        is_valid, errors = template_engine.validate_template_syntax(template.content)
        
        if not is_valid:
            form.add_error('content', f'Template syntax errors: {", ".join(errors)}')
            return self.form_invalid(form)
        
        # Parse and save variables
        try:
            variables = template_engine.parse_template_variables(template.content)
            template.variables = {
                'parsed_variables': [
                    {
                        'name': var.name,
                        'type': var.type.value,
                        'label': var.label,
                        'description': var.description,
                        'required': var.required
                    } for var in variables
                ]
            }
        except Exception as e:
            form.add_error('content', f'Error parsing variables: {str(e)}')
            return self.form_invalid(form)
        
        template.save()
        
        messages.success(self.request, f"Template '{template.name}' created successfully!")
        return redirect('document_editor:template_detail', pk=template.pk)

class TemplateUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Editimi i template"""
    model = DocumentTemplate
    form_class = TemplateForm
    template_name = 'document_editor/templates/edit.html'

    def test_func(self):
        template = self.get_object()
        return (
            self.request.user.role == 'admin' or
            template.created_by == self.request.user
        )

    def form_valid(self, form):
        template = form.save(commit=False)
        
        # Validate template syntax
        template_engine = LegalTemplateEngine()
        is_valid, errors = template_engine.validate_template_syntax(template.content)
        
        if not is_valid:
            form.add_error('content', f'Template syntax errors: {", ".join(errors)}')
            return self.form_invalid(form)
        
        # Update variables
        try:
            variables = template_engine.parse_template_variables(template.content)
            template.variables = {
                'parsed_variables': [
                    {
                        'name': var.name,
                        'type': var.type.value,
                        'label': var.label,
                        'description': var.description,
                        'required': var.required
                    } for var in variables
                ]
            }
        except Exception as e:
            form.add_error('content', f'Error parsing variables: {str(e)}')
            return self.form_invalid(form)
        
        template.save()
        
        messages.success(self.request, f"Template '{template.name}' updated successfully!")
        return redirect('document_editor:template_detail', pk=template.pk)

class TemplateDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Fshirja e template"""
    model = DocumentTemplate
    template_name = 'document_editor/templates/confirm_delete.html'
    success_url = reverse_lazy('document_editor:template_list')

    def test_func(self):
        template = self.get_object()
        return (
            self.request.user.role == 'admin' or
            template.created_by == self.request.user
        )

    def delete(self, request, *args, **kwargs):
        template = self.get_object()
        
        # Check if template is in use
        documents_using_template = Document.objects.filter(template_used=template).count()
        
        if documents_using_template > 0:
            messages.error(
                request, 
                f"Cannot delete template '{template.name}' - it's used by {documents_using_template} documents"
            )
            return redirect('document_editor:template_detail', pk=template.pk)
        
        messages.success(request, f"Template '{template.name}' deleted successfully!")
        return super().delete(request, *args, **kwargs)

@login_required
@require_POST
def template_preview(request, template_id):
    """Preview template me sample data"""
    try:
        template = get_object_or_404(DocumentTemplate, id=template_id)
        
        # Get variables from POST data
        variables = {}
        for key, value in request.POST.items():
            if key.startswith('var_'):
                var_name = key[4:]  # Remove 'var_' prefix
                variables[var_name] = value
        
        # Generate preview
        template_engine = LegalTemplateEngine()
        
        if variables:
            # Use provided variables
            context = TemplateContext(variables=variables)
            content = template_engine.render_template(template, context)
        else:
            # Use sample data
            content = template_engine.preview_template(template)
        
        return JsonResponse({
            'success': True,
            'content': content,
            'variables_used': variables
        })
        
    except Exception as e:
        logger.error(f"Template preview error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def template_ai_enhance(request, template_id):
    """AI enhancement i template"""
    try:
        template = get_object_or_404(DocumentTemplate, id=template_id)
        
        if not (request.user.role == 'admin' or template.created_by == request.user):
            return JsonResponse({'success': False, 'error': 'Permission denied'})
        
        enhancement_type = request.POST.get('enhancement_type', 'improve')
        
        template_engine = LegalTemplateEngine()
        enhanced_content = template_engine.enhance_template_with_ai(
            template, enhancement_type
        )
        
        return JsonResponse({
            'success': True,
            'enhanced_content': enhanced_content,
            'original_content': template.content,
            'enhancement_type': enhancement_type
        })
        
    except ValidationError as e:
        return JsonResponse({'success': False, 'error': str(e)})
    except Exception as e:
        logger.error(f"Template AI enhance error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def template_ai_suggestions(request):
    """AI suggestions për template të ri"""
    try:
        document_type = request.GET.get('document_type', '')
        case_info = request.GET.get('case_info', '{}')
        
        try:
            case_data = json.loads(case_info)
        except json.JSONDecodeError:
            case_data = {}
        
        # Use automation engine for suggestions
        automation_engine = DocumentAutomationEngine()
        suggestions = automation_engine.suggest_document_template(case_data)
        
        return JsonResponse({
            'success': True,
            'suggestions': [
                {
                    'type': s.type,
                    'title': s.title,
                    'description': s.description,
                    'confidence': s.confidence,
                    'template_id': s.template_id,
                    'variables': s.variables
                } for s in suggestions
            ]
        })
        
    except Exception as e:
        logger.error(f"Template AI suggestions error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def template_create_from_document(request, document_id):
    """Krijo template nga dokument ekzistues"""
    try:
        document = get_object_or_404(Document, id=document_id)
        
        if not (request.user.role == 'admin' or document.owned_by == request.user):
            return JsonResponse({'success': False, 'error': 'Permission denied'})
        
        template_name = request.POST.get('template_name')
        extract_variables = request.POST.get('extract_variables', 'true').lower() == 'true'
        
        if not template_name:
            return JsonResponse({'success': False, 'error': 'Template name required'})
        
        # Use template engine to create template from document
        template_engine = LegalTemplateEngine()
        template = template_engine.create_template_from_document(
            document=document,
            template_name=template_name,
            extract_variables=extract_variables
        )
        
        return JsonResponse({
            'success': True,
            'template_id': template.id,
            'template_name': template.name,
            'redirect_url': reverse('document_editor:template_detail', kwargs={'pk': template.pk})
        })
        
    except Exception as e:
        logger.error(f"Create template from document error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def template_variables_analyze(request, template_id):
    """Analizoj variablat e template me AI"""
    try:
        template = get_object_or_404(DocumentTemplate, id=template_id)
        
        template_engine = LegalTemplateEngine()
        
        # Get AI-powered variable suggestions
        ai_variables = template_engine.suggest_template_variables_with_ai(
            template.content, template.category
        )
        
        # Get parsed variables
        parsed_variables = template_engine.parse_template_variables(template.content)
        
        return JsonResponse({
            'success': True,
            'ai_suggestions': [
                {
                    'name': var.name,
                    'type': var.type.value,
                    'label': var.label,
                    'description': var.description,
                    'required': var.required,
                    'validation_rules': var.validation_rules,
                    'choices': var.choices,
                    'ai_suggested': var.ai_suggested
                } for var in ai_variables
            ],
            'parsed_variables': [
                {
                    'name': var.name,
                    'type': var.type.value,
                    'label': var.label,
                    'description': var.description,
                    'required': var.required
                } for var in parsed_variables
            ]
        })
        
    except Exception as e:
        logger.error(f"Template variables analyze error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def template_export(request, template_id):
    """Export template në JSON format"""
    try:
        template = get_object_or_404(DocumentTemplate, id=template_id)
        
        # Create export data
        export_data = {
            'name': template.name,
            'description': template.description,
            'category': template.category,
            'content': template.content,
            'variables': template.variables,
            'version': '1.0',
            'export_date': timezone.now().isoformat(),
            'exported_by': request.user.username
        }
        
        response = JsonResponse(export_data, json_dumps_params={'indent': 2, 'ensure_ascii': False})
        response['Content-Disposition'] = f'attachment; filename="{template.name}.json"'
        
        return response
        
    except Exception as e:
        logger.error(f"Template export error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

class TemplateImportView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    """Import template nga JSON"""
    template_name = 'document_editor/templates/import.html'
    form_class = TemplateUploadForm

    def test_func(self):
        return self.request.user.role in ['admin', 'lawyer']

    def form_valid(self, form):
        try:
            uploaded_file = form.cleaned_data['file']
            
            # Read and parse JSON
            file_content = uploaded_file.read().decode('utf-8')
            template_data = json.loads(file_content)
            
            # Validate required fields
            required_fields = ['name', 'category', 'content']
            for field in required_fields:
                if field not in template_data:
                    messages.error(self.request, f"Missing required field: {field}")
                    return self.form_invalid(form)
            
            # Check if template with same name exists
            if DocumentTemplate.objects.filter(name=template_data['name']).exists():
                template_data['name'] = f"{template_data['name']} (Imported)"
            
            # Create template
            template = DocumentTemplate.objects.create(
                name=template_data['name'],
                description=template_data.get('description', ''),
                category=template_data['category'],
                content=template_data['content'],
                variables=template_data.get('variables', {}),
                created_by=self.request.user
            )
            
            # Validate template
            template_engine = LegalTemplateEngine()
            is_valid, errors = template_engine.validate_template_syntax(template.content)
            
            if not is_valid:
                template.is_active = False
                template.save()
                messages.warning(
                    self.request, 
                    f"Template imported but deactivated due to syntax errors: {', '.join(errors)}"
                )
            else:
                messages.success(self.request, f"Template '{template.name}' imported successfully!")
            
            return redirect('document_editor:template_detail', pk=template.pk)
            
        except json.JSONDecodeError:
            messages.error(self.request, "Invalid JSON file")
            return self.form_invalid(form)
        except Exception as e:
            logger.error(f"Template import error: {e}")
            messages.error(self.request, f"Import failed: {str(e)}")
            return self.form_invalid(form)

class TemplateLibraryView(LoginRequiredMixin, TemplateView):
    """Template library me pre-built templates"""
    template_name = 'document_editor/templates/library.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Group templates by category
        categories = {}
        templates = DocumentTemplate.objects.filter(is_active=True).order_by('category', 'name')
        
        for template in templates:
            if template.category not in categories:
                categories[template.category] = []
            categories[template.category].append(template)
        
        context['template_categories'] = categories
        
        # Add popular templates
        context['popular_templates'] = Document.objects.values(
            'template_used__name', 'template_used__id'
        ).annotate(
            usage_count=Count('template_used')
        ).filter(
            template_used__isnull=False,
            usage_count__gt=0
        ).order_by('-usage_count')[:10]
        
        return context

@login_required
@require_POST
def template_clone(request, template_id):
    """Klono një template ekzistues"""
    try:
        original_template = get_object_or_404(DocumentTemplate, id=template_id)
        
        # Create clone
        cloned_template = DocumentTemplate.objects.create(
            name=f"{original_template.name} (Copy)",
            description=original_template.description,
            category=original_template.category,
            content=original_template.content,
            variables=original_template.variables.copy(),
            created_by=request.user
        )
        
        return JsonResponse({
            'success': True,
            'template_id': cloned_template.id,
            'template_name': cloned_template.name,
            'redirect_url': reverse('document_editor:template_detail', kwargs={'pk': cloned_template.pk})
        })
        
    except Exception as e:
        logger.error(f"Template clone error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})
