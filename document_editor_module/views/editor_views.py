"""
Document Editor Views
Views për editimin e dokumenteve, collaboration, dhe integrim LLM
"""

import json
import logging
from typing import Dict, Any, List

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseBadRequest, Http404
from django.views.generic import View, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.conf import settings
from django.urls import reverse
from django.contrib import messages

from ..models.document_models import (
    Document, DocumentTemplate, DocumentType, DocumentStatus,
    DocumentComment, LLMInteraction, DocumentAuditLog
)
from ..services.document_service import DocumentEditingService
from ..services.llm_service import LegalLLMService, DocumentContext

logger = logging.getLogger(__name__)

class DocumentEditorView(LoginRequiredMixin, TemplateView):
    """
    Main view për document editor interface
    """
    template_name = 'document_editor/editor.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        document_id = kwargs.get('document_id')
        
        if document_id:
            document = get_object_or_404(Document, id=document_id)
            
            # Kontrollo permissions
            if not document.can_edit(self.request.user):
                raise PermissionDenied("Nuk keni leje për të edituar këtë dokument.")
            
            context['document'] = document
            context['can_edit'] = True
            context['document_json'] = json.dumps({
                'id': document.id,
                'title': document.title,
                'content': document.content,
                'content_html': document.content_html,
                'version': document.version_number,
                'is_locked': document.is_locked,
                'locked_by': document.locked_by.username if document.locked_by else None
            })
        else:
            context['document'] = None
            context['can_edit'] = True
            context['document_json'] = json.dumps({'id': None})

        # Shto konfigurimin e editorit
        context['editor_config'] = json.dumps({
            'auto_save_interval': getattr(settings, 'DOCUMENT_AUTO_SAVE_INTERVAL', 30),
            'llm_enabled': getattr(settings, 'LLM_ENABLED', True),
            'collaboration_enabled': getattr(settings, 'COLLABORATION_ENABLED', True),
            'spell_check_enabled': True,
            'grammar_check_enabled': True
        })

        # Shto template dhe types
        context['document_types'] = DocumentType.objects.filter(is_legal_document=True)
        context['document_templates'] = DocumentTemplate.objects.filter(is_active=True)
        context['document_statuses'] = DocumentStatus.objects.all().order_by('order')

        return context

class DocumentLoadView(LoginRequiredMixin, View):
    """
    API endpoint për të ngarkuar një dokument për editim
    """
    
    def get(self, request, document_id):
        try:
            editing_service = DocumentEditingService()
            document = editing_service.get_document_for_editing(document_id, request.user)
            
            # Merr komentet
            comments = editing_service.get_document_comments(document)
            
            # Merr versionet e fundit
            versions = editing_service.get_document_versions(document, limit=5)
            
            # Merr statistikat
            stats = editing_service.get_document_statistics(document)
            
            return JsonResponse({
                'success': True,
                'document': {
                    'id': document.id,
                    'uid': str(document.uid),
                    'title': document.title,
                    'description': document.description,
                    'content': document.content,
                    'content_html': document.content_html,
                    'version_number': document.version_number,
                    'document_type': {
                        'id': document.document_type.id,
                        'name': document.document_type.name
                    },
                    'status': {
                        'id': document.status.id,
                        'name': document.status.name,
                        'color': document.status.color
                    },
                    'case': {
                        'id': document.case.id,
                        'title': document.case.title,
                        'uid': document.case.uid
                    } if document.case else None,
                    'is_locked': document.is_locked,
                    'locked_by': document.locked_by.username if document.locked_by else None,
                    'locked_at': document.locked_at.isoformat() if document.locked_at else None,
                    'created_at': document.created_at.isoformat(),
                    'updated_at': document.updated_at.isoformat(),
                    'last_edited_at': document.last_edited_at.isoformat() if document.last_edited_at else None,
                    'last_edited_by': document.last_edited_by.username if document.last_edited_by else None,
                    'metadata': document.metadata or {}
                },
                'comments': [
                    {
                        'id': comment.id,
                        'content': comment.content,
                        'author': comment.author.username,
                        'position_start': comment.position_start,
                        'position_end': comment.position_end,
                        'selected_text': comment.selected_text,
                        'is_resolved': comment.is_resolved,
                        'created_at': comment.created_at.isoformat(),
                        'parent_id': comment.parent_comment.id if comment.parent_comment else None
                    } for comment in comments
                ],
                'versions': [
                    {
                        'version_number': version.version_number,
                        'created_by': version.created_by.username if version.created_by else None,
                        'created_at': version.created_at.isoformat(),
                        'changes_summary': version.changes_summary
                    } for version in versions
                ],
                'statistics': stats,
                'permissions': {
                    'can_edit': document.can_edit(request.user),
                    'can_comment': True,  # Të gjithë mund të komentojnë
                    'can_delete': request.user == document.owned_by or request.user.has_perm('documents.delete_document')
                }
            })
            
        except ValidationError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        except PermissionDenied as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=403)
        except Exception as e:
            logger.error(f"Error loading document {document_id}: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Gabim në ngarkimin e dokumentit'}, status=500)

class DocumentSaveView(LoginRequiredMixin, View):
    """
    API endpoint për të ruajtur një dokument
    """
    
    def post(self, request, document_id):
        try:
            data = json.loads(request.body)
            content = data.get('content', '')
            content_html = data.get('content_html', '')
            auto_save = data.get('auto_save', False)
            create_version = data.get('create_version', False)
            
            document = get_object_or_404(Document, id=document_id)
            editing_service = DocumentEditingService()
            
            if auto_save:
                editing_service.auto_save_document(document, content, request.user)
            else:
                document = editing_service.save_document_content(
                    document=document,
                    content=content,
                    content_html=content_html,
                    user=request.user,
                    create_version=create_version
                )
            
            return JsonResponse({
                'success': True,
                'message': 'Dokumenti u ruajt me sukses',
                'auto_save': auto_save,
                'version_number': document.version_number,
                'last_saved': document.last_edited_at.isoformat() if document.last_edited_at else None
            })
            
        except ValidationError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        except PermissionDenied as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=403)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            logger.error(f"Error saving document {document_id}: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Gabim në ruajtjen e dokumentit'}, status=500)

class DocumentLockView(LoginRequiredMixin, View):
    """
    API endpoint për të bllokuar/çbllokuar një dokument
    """
    
    def post(self, request, document_id):
        try:
            data = json.loads(request.body)
            action = data.get('action')  # 'lock' or 'unlock'
            
            document = get_object_or_404(Document, id=document_id)
            editing_service = DocumentEditingService()
            
            if action == 'lock':
                success = document.lock_document(request.user)
                message = 'Dokumenti u bllokua për editim' if success else 'Dokumenti është tashmë i bllokuar'
            elif action == 'unlock':
                editing_service.release_document_lock(document, request.user)
                success = True
                message = 'Dokumenti u çbllokua'
            else:
                return JsonResponse({'success': False, 'error': 'Invalid action'}, status=400)
            
            return JsonResponse({
                'success': success,
                'message': message,
                'is_locked': document.is_locked,
                'locked_by': document.locked_by.username if document.locked_by else None
            })
            
        except ValidationError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        except Exception as e:
            logger.error(f"Error locking/unlocking document {document_id}: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Gabim në operacion'}, status=500)

class DocumentCommentsView(LoginRequiredMixin, View):
    """
    API endpoint për menaxhimin e komenteve
    """
    
    def get(self, request, document_id):
        """Merr komentet e dokumentit"""
        try:
            document = get_object_or_404(Document, id=document_id)
            editing_service = DocumentEditingService()
            
            include_resolved = request.GET.get('include_resolved', 'false').lower() == 'true'
            comments = editing_service.get_document_comments(document, include_resolved)
            
            return JsonResponse({
                'success': True,
                'comments': [
                    {
                        'id': comment.id,
                        'content': comment.content,
                        'author': {
                            'id': comment.author.id,
                            'username': comment.author.username,
                            'full_name': comment.author.get_full_name()
                        },
                        'position_start': comment.position_start,
                        'position_end': comment.position_end,
                        'selected_text': comment.selected_text,
                        'is_resolved': comment.is_resolved,
                        'resolved_by': comment.resolved_by.username if comment.resolved_by else None,
                        'resolved_at': comment.resolved_at.isoformat() if comment.resolved_at else None,
                        'created_at': comment.created_at.isoformat(),
                        'updated_at': comment.updated_at.isoformat(),
                        'parent_id': comment.parent_comment.id if comment.parent_comment else None,
                        'replies': []  # Do të popullohet në frontend
                    } for comment in comments
                ]
            })
            
        except Exception as e:
            logger.error(f"Error fetching comments for document {document_id}: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Gabim në ngarkimin e komenteve'}, status=500)
    
    def post(self, request, document_id):
        """Shton një koment të ri"""
        try:
            data = json.loads(request.body)
            content = data.get('content', '').strip()
            position_start = data.get('position_start')
            position_end = data.get('position_end')
            selected_text = data.get('selected_text', '')
            parent_comment_id = data.get('parent_comment_id')
            
            if not content:
                return JsonResponse({'success': False, 'error': 'Përmbajtja e komentit është e detyrueshme'}, status=400)
            
            document = get_object_or_404(Document, id=document_id)
            editing_service = DocumentEditingService()
            
            comment = editing_service.add_comment(
                document=document,
                content=content,
                user=request.user,
                position_start=position_start,
                position_end=position_end,
                selected_text=selected_text,
                parent_comment_id=parent_comment_id
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Komenti u shtua me sukses',
                'comment': {
                    'id': comment.id,
                    'content': comment.content,
                    'author': {
                        'id': comment.author.id,
                        'username': comment.author.username,
                        'full_name': comment.author.get_full_name()
                    },
                    'position_start': comment.position_start,
                    'position_end': comment.position_end,
                    'selected_text': comment.selected_text,
                    'is_resolved': comment.is_resolved,
                    'created_at': comment.created_at.isoformat(),
                    'parent_id': comment.parent_comment.id if comment.parent_comment else None
                }
            })
            
        except ValidationError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            logger.error(f"Error adding comment to document {document_id}: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Gabim në shtimin e komentit'}, status=500)

class DocumentCommentResolveView(LoginRequiredMixin, View):
    """
    API endpoint për të zgjidhur komentet
    """
    
    def post(self, request, comment_id):
        try:
            editing_service = DocumentEditingService()
            comment = editing_service.resolve_comment(comment_id, request.user)
            
            return JsonResponse({
                'success': True,
                'message': 'Komenti u zgjidh me sukses',
                'comment_id': comment.id,
                'resolved_at': comment.resolved_at.isoformat(),
                'resolved_by': comment.resolved_by.username
            })
            
        except ValidationError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        except Exception as e:
            logger.error(f"Error resolving comment {comment_id}: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Gabim në zgjidhjen e komentit'}, status=500)

class DocumentVersionsView(LoginRequiredMixin, View):
    """
    API endpoint për menaxhimin e versioneve
    """
    
    def get(self, request, document_id):
        """Merr historikun e versioneve"""
        try:
            document = get_object_or_404(Document, id=document_id)
            editing_service = DocumentEditingService()
            
            limit = int(request.GET.get('limit', 20))
            versions = editing_service.get_document_versions(document, limit)
            
            return JsonResponse({
                'success': True,
                'versions': [
                    {
                        'version_number': version.version_number,
                        'created_by': {
                            'id': version.created_by.id,
                            'username': version.created_by.username
                        } if version.created_by else None,
                        'created_at': version.created_at.isoformat(),
                        'changes_summary': version.changes_summary,
                        'content_preview': version.content_snapshot[:200] + '...' if len(version.content_snapshot) > 200 else version.content_snapshot,
                        'stats': {
                            'added_lines': len(version.added_content.split('\n')) if version.added_content else 0,
                            'removed_lines': len(version.removed_content.split('\n')) if version.removed_content else 0
                        }
                    } for version in versions
                ]
            })
            
        except Exception as e:
            logger.error(f"Error fetching versions for document {document_id}: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Gabim në ngarkimin e versioneve'}, status=500)

class DocumentVersionRestoreView(LoginRequiredMixin, View):
    """
    API endpoint për të rikthyer një version të mëparshëm
    """
    
    def post(self, request, document_id, version_number):
        try:
            document = get_object_or_404(Document, id=document_id)
            editing_service = DocumentEditingService()
            
            document = editing_service.restore_document_version(document, version_number, request.user)
            
            return JsonResponse({
                'success': True,
                'message': f'Versioni {version_number} u rikthye me sukses',
                'current_version': document.version_number,
                'content': document.content,
                'content_html': document.content_html
            })
            
        except ValidationError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        except PermissionDenied as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=403)
        except Exception as e:
            logger.error(f"Error restoring version {version_number} for document {document_id}: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Gabim në rikthimin e versionit'}, status=500)

# LLM Integration Views

class DocumentLLMGenerateView(LoginRequiredMixin, View):
    """
    API endpoint për gjenerimin e dokumenteve me LLM
    """
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            document_type = data.get('document_type')
            case_id = data.get('case_id')
            template_vars = data.get('template_vars', {})
            
            if not document_type:
                return JsonResponse({'success': False, 'error': 'Tipi i dokumentit është i detyrueshëm'}, status=400)
            
            # Merr informacionin e rastit nëse është dhënë
            case_info = {}
            if case_id:
                try:
                    from cases.models import Case  # Import here to avoid circular imports
                    case = Case.objects.get(id=case_id)
                    case_info = {
                        'case_type': case.case_type,
                        'case_title': case.title,
                        'case_description': case.description,
                        'client_name': case.client.full_name if case.client else None
                    }
                    template_vars['case_info'] = case_info
                except Case.DoesNotExist:
                    pass
            
            editing_service = DocumentEditingService()
            response = editing_service.generate_document_with_llm(
                document_type=document_type,
                case_info=case_info,
                template_vars=template_vars,
                user=request.user
            )
            
            if response.error:
                return JsonResponse({
                    'success': False, 
                    'error': f'Gabim në gjenerimin e dokumentit: {response.error}'
                }, status=500)
            
            return JsonResponse({
                'success': True,
                'content': response.text,
                'metadata': {
                    'model_used': response.model_used,
                    'provider': response.provider,
                    'processing_time': response.processing_time,
                    'confidence': response.confidence,
                    'token_usage': response.token_usage
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            logger.error(f"Error generating document with LLM: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Gabim në gjenerimin e dokumentit'}, status=500)

class DocumentLLMReviewView(LoginRequiredMixin, View):
    """
    API endpoint për rishikimin e dokumenteve me LLM
    """
    
    def post(self, request, document_id):
        try:
            data = json.loads(request.body)
            focus_areas = data.get('focus_areas', ['legal_accuracy', 'format', 'language', 'completeness'])
            
            document = get_object_or_404(Document, id=document_id)
            editing_service = DocumentEditingService()
            
            response = editing_service.review_document_with_llm(
                document=document,
                focus_areas=focus_areas,
                user=request.user
            )
            
            if response.error:
                return JsonResponse({
                    'success': False, 
                    'error': f'Gabim në rishikimin e dokumentit: {response.error}'
                }, status=500)
            
            return JsonResponse({
                'success': True,
                'review': response.text,
                'metadata': {
                    'model_used': response.model_used,
                    'provider': response.provider,
                    'processing_time': response.processing_time,
                    'confidence': response.confidence,
                    'focus_areas': focus_areas
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            logger.error(f"Error reviewing document {document_id} with LLM: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Gabim në rishikimin e dokumentit'}, status=500)

class DocumentLLMSuggestView(LoginRequiredMixin, View):
    """
    API endpoint për sugjerime përmirësimi me LLM
    """
    
    def post(self, request, document_id):
        try:
            data = json.loads(request.body)
            specific_section = data.get('specific_section', '')
            
            document = get_object_or_404(Document, id=document_id)
            editing_service = DocumentEditingService()
            
            response = editing_service.get_suggestions_with_llm(
                document=document,
                specific_section=specific_section,
                user=request.user
            )
            
            if response.error:
                return JsonResponse({
                    'success': False, 
                    'error': f'Gabim në marrjen e sugjerimeve: {response.error}'
                }, status=500)
            
            return JsonResponse({
                'success': True,
                'suggestions': response.text,
                'section': specific_section,
                'metadata': {
                    'model_used': response.model_used,
                    'provider': response.provider,
                    'processing_time': response.processing_time,
                    'confidence': response.confidence
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            logger.error(f"Error getting suggestions for document {document_id} with LLM: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Gabim në marrjen e sugjerimeve'}, status=500)

class DocumentLLMTranslateView(LoginRequiredMixin, View):
    """
    API endpoint për përkthimin e dokumenteve me LLM
    """
    
    def post(self, request, document_id):
        try:
            data = json.loads(request.body)
            target_language = data.get('target_language', 'English')
            
            if not target_language:
                return JsonResponse({'success': False, 'error': 'Gjuha e destinacionit është e detyrueshme'}, status=400)
            
            document = get_object_or_404(Document, id=document_id)
            editing_service = DocumentEditingService()
            
            response = editing_service.translate_document_with_llm(
                document=document,
                target_language=target_language,
                user=request.user
            )
            
            if response.error:
                return JsonResponse({
                    'success': False, 
                    'error': f'Gabim në përkthimin e dokumentit: {response.error}'
                }, status=500)
            
            return JsonResponse({
                'success': True,
                'translated_content': response.text,
                'target_language': target_language,
                'metadata': {
                    'model_used': response.model_used,
                    'provider': response.provider,
                    'processing_time': response.processing_time,
                    'confidence': response.confidence
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            logger.error(f"Error translating document {document_id} with LLM: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Gabim në përkthimin e dokumentit'}, status=500)

class DocumentTemplatesView(LoginRequiredMixin, View):
    """
    API endpoint për menaxhimin e template-ave
    """
    
    def get(self, request):
        """Merr template-at e disponueshme"""
        try:
            category = request.GET.get('category')
            
            templates = DocumentTemplate.objects.filter(is_active=True)
            if category:
                templates = templates.filter(category=category)
            
            templates = templates.select_related('created_by')
            
            return JsonResponse({
                'success': True,
                'templates': [
                    {
                        'id': template.id,
                        'name': template.name,
                        'description': template.description,
                        'category': template.category,
                        'variables': template.variables,
                        'created_by': template.created_by.username if template.created_by else None,
                        'created_at': template.created_at.isoformat()
                    } for template in templates
                ]
            })
            
        except Exception as e:
            logger.error(f"Error fetching templates: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Gabim në ngarkimin e template-ave'}, status=500)

class DocumentFromTemplateView(LoginRequiredMixin, View):
    """
    API endpoint për krijimin e dokumenteve nga template
    """
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            template_id = data.get('template_id')
            template_vars = data.get('template_vars', {})
            case_id = data.get('case_id')
            title = data.get('title', '')
            
            if not template_id:
                return JsonResponse({'success': False, 'error': 'Template ID është i detyrueshëm'}, status=400)
            
            template = get_object_or_404(DocumentTemplate, id=template_id, is_active=True)
            
            # Zëvendëso variablat në template
            content = template.content
            for var_name, var_value in template_vars.items():
                placeholder = f"{{{var_name}}}"
                content = content.replace(placeholder, str(var_value))
            
            # Krijo dokumentin e ri
            with transaction.atomic():
                # Merr objekte të nevojshme
                case = None
                if case_id:
                    try:
                        from cases.models import Case
                        case = Case.objects.get(id=case_id)
                    except Case.DoesNotExist:
                        return JsonResponse({'success': False, 'error': 'Rasti nuk u gjet'}, status=400)
                
                # Dokument type dhe status default
                doc_type = DocumentType.objects.first()  # Përdor të parin si default
                doc_status = DocumentStatus.objects.filter(name__icontains='draft').first() or DocumentStatus.objects.first()
                
                document = Document.objects.create(
                    title=title or f"{template.name} - {timezone.now().strftime('%Y-%m-%d')}",
                    content=content,
                    case=case,
                    document_type=doc_type,
                    status=doc_status,
                    template_used=template,
                    created_by=request.user,
                    owned_by=request.user,
                    metadata={
                        'created_from_template': template.id,
                        'template_variables': template_vars
                    }
                )
            
            return JsonResponse({
                'success': True,
                'message': 'Dokumenti u krijua me sukses nga template',
                'document': {
                    'id': document.id,
                    'title': document.title,
                    'content': document.content,
                    'uid': str(document.uid)
                },
                'redirect_url': reverse('document_editor', kwargs={'document_id': document.id})
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            logger.error(f"Error creating document from template: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Gabim në krijimin e dokumentit'}, status=500)

class DocumentSearchView(LoginRequiredMixin, View):
    """
    API endpoint për kërkimin e dokumenteve
    """
    
    def get(self, request):
        try:
            query = request.GET.get('q', '').strip()
            if not query:
                return JsonResponse({'success': False, 'error': 'Query është i detyrueshëm'}, status=400)
            
            limit = int(request.GET.get('limit', 20))
            
            editing_service = DocumentEditingService()
            documents = editing_service.search_documents_by_content(query, request.user, limit)
            
            return JsonResponse({
                'success': True,
                'query': query,
                'results': [
                    {
                        'id': doc.id,
                        'title': doc.title,
                        'document_type': doc.document_type.name,
                        'case_title': doc.case.title if doc.case else None,
                        'case_uid': doc.case.uid if doc.case else None,
                        'status': doc.status.name,
                        'status_color': doc.status.color,
                        'created_at': doc.created_at.isoformat(),
                        'last_edited_at': doc.last_edited_at.isoformat() if doc.last_edited_at else None,
                        'owned_by': doc.owned_by.username,
                        'preview': doc.content[:200] + '...' if len(doc.content) > 200 else doc.content
                    } for doc in documents
                ],
                'total_results': len(documents)
            })
            
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Invalid limit parameter'}, status=400)
        except Exception as e:
            logger.error(f"Error searching documents: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Gabim në kërkim'}, status=500)

# Utility Views

class DocumentStatsView(LoginRequiredMixin, View):
    """
    API endpoint për statistikat e dokumentit
    """
    
    def get(self, request, document_id):
        try:
            document = get_object_or_404(Document, id=document_id)
            editing_service = DocumentEditingService()
            
            stats = editing_service.get_document_statistics(document)
            
            return JsonResponse({
                'success': True,
                'statistics': stats
            })
            
        except Exception as e:
            logger.error(f"Error fetching stats for document {document_id}: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Gabim në ngarkimin e statistikave'}, status=500)

@login_required
@require_POST
def document_export(request, document_id):
    """
    Export document në formate të ndryshme
    """
    try:
        export_format = request.POST.get('format', 'pdf')
        document = get_object_or_404(Document, id=document_id)
        
        # Kontrollo permissions
        if not document.can_edit(request.user):
            raise PermissionDenied("Nuk keni leje për të eksportuar këtë dokument.")
        
        # Implemento logjikën e eksportimit (PDF, DOCX, etj.)
        # Ky kod duhet zgjeruar me biblioteka si reportlab, python-docx, etj.
        
        return JsonResponse({
            'success': True,
            'message': f'Dokumenti u eksportua në format {export_format}',
            'download_url': f'/documents/{document_id}/download/{export_format}/'
        })
        
    except Exception as e:
        logger.error(f"Error exporting document {document_id}: {str(e)}")
        return JsonResponse({'success': False, 'error': 'Gabim në eksportim'}, status=500)
