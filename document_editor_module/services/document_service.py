"""
Document Editor Service
Menaxhon editimin, versionimin, collaboration dhe integrim me LLM
"""

import json
import difflib
import re
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.conf import settings

from ..models.document_models import (
    Document, DocumentVersion, DocumentComment, 
    DocumentAuditLog, LLMInteraction, DocumentEditor
)
from .llm_service import LegalLLMService, DocumentContext, LLMResponse

User = get_user_model()

class EditAction(Enum):
    """Llojet e veprimeve të editimit"""
    INSERT = "insert"
    DELETE = "delete"
    REPLACE = "replace"
    FORMAT = "format"
    MOVE = "move"

@dataclass
class EditOperation:
    """Operacion editimi"""
    action: EditAction
    position: int
    length: int = 0
    content: str = ""
    old_content: str = ""
    timestamp: datetime = None
    user_id: int = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = timezone.now()

@dataclass
class DocumentDiff:
    """Diferenca midis versioneve"""
    added_lines: List[str]
    removed_lines: List[str]
    modified_lines: List[Tuple[str, str]]  # (old, new)
    stats: Dict[str, int]

class DocumentEditingService:
    """
    Service për editimin e dokumenteve me mbështetje për:
    - Real-time collaboration
    - Version control
    - LLM integration
    - Conflict resolution
    """

    def __init__(self):
        self.llm_service = LegalLLMService()
        self.lock_timeout = getattr(settings, 'DOCUMENT_LOCK_TIMEOUT', 300)  # 5 minuta
        self.auto_save_interval = getattr(settings, 'DOCUMENT_AUTO_SAVE_INTERVAL', 30)  # 30 sekonda

    def get_document_for_editing(self, document_id: int, user: User) -> Document:
        """
        Merr dokumentin për editim duke kontrolluar permissions dhe locks
        """
        try:
            document = Document.objects.select_related(
                'case', 'document_type', 'status', 'owned_by', 'locked_by'
            ).get(id=document_id)
        except Document.DoesNotExist:
            raise ValidationError("Dokumenti nuk u gjet.")

        # Kontrollo permissions
        if not document.can_edit(user):
            raise PermissionDenied("Nuk keni leje për të edituar këtë dokument.")

        # Kontrollo lock status
        if document.is_locked and document.locked_by != user:
            lock_age = timezone.now() - document.locked_at
            if lock_age.total_seconds() > self.lock_timeout:
                # Lock ka skaduar, çblloko automatikisht
                document.unlock_document(user)
            else:
                remaining_time = self.lock_timeout - lock_age.total_seconds()
                raise ValidationError(
                    f"Dokumenti është i bllokuar nga {document.locked_by.username}. "
                    f"Mbeten {int(remaining_time/60)} minuta."
                )

        # Blloko dokumentin për user-in aktual
        if not document.is_locked:
            document.lock_document(user)

        # Log action
        self._log_action(document, user, 'edit_start', {
            'lock_acquired': True,
            'lock_timeout': self.lock_timeout
        })

        return document

    def save_document_content(self, 
                            document: Document, 
                            content: str, 
                            content_html: str = "", 
                            user: User = None,
                            auto_save: bool = False,
                            create_version: bool = False) -> Document:
        """
        Ruaj përmbajtjen e dokumentit me version control
        """
        if not document.can_edit(user):
            raise PermissionDenied("Nuk keni leje për të edituar këtë dokument.")

        old_content = document.content
        old_content_html = document.content_html

        with transaction.atomic():
            # Përditëso dokumentin
            document.content = content
            document.content_html = content_html
            document.last_edited_by = user
            document.last_edited_at = timezone.now()
            
            # Përditëso metadata nëse ka ndryshime
            if old_content != content:
                if not document.metadata:
                    document.metadata = {}
                document.metadata['last_significant_change'] = timezone.now().isoformat()
                document.metadata['edit_count'] = document.metadata.get('edit_count', 0) + 1

            document.save()

            # Krijo version të ri nëse kërkohet ose ndryshimet janë të rëndësishme
            if create_version or self._should_create_version(old_content, content):
                self._create_document_version(document, old_content, old_content_html, user)

            # Log action
            action_type = 'auto_save' if auto_save else 'manual_save'
            self._log_action(document, user, action_type, {
                'content_length': len(content),
                'content_changed': old_content != content,
                'html_changed': old_content_html != content_html
            })

        return document

    def _should_create_version(self, old_content: str, new_content: str) -> bool:
        """
        Vendos nëse duhet krijuar një version i ri bazuar në sasinë e ndryshimeve
        """
        if not old_content:
            return True  # Dokument i ri

        # Kalkulo përqindjen e ndryshimeve
        diff = list(difflib.unified_diff(
            old_content.splitlines(),
            new_content.splitlines(),
            lineterm=''
        ))
        
        total_lines = max(len(old_content.splitlines()), len(new_content.splitlines()))
        changed_lines = len([line for line in diff if line.startswith('+') or line.startswith('-')])
        
        if total_lines == 0:
            return False
        
        change_percentage = changed_lines / total_lines
        
        # Krijo version nëse ndryshimet janë mbi 10%
        return change_percentage > 0.1

    def _create_document_version(self, 
                               document: Document, 
                               old_content: str, 
                               old_content_html: str, 
                               user: User) -> DocumentVersion:
        """
        Krijn një version të ri të dokumentit
        """
        # Gjenero diff
        diff_result = self._generate_diff(old_content, document.content)
        
        version = DocumentVersion.objects.create(
            document=document,
            version_number=document.version_number,
            content_snapshot=old_content,
            content_html_snapshot=old_content_html,
            metadata_snapshot=document.metadata.copy() if document.metadata else {},
            changes_summary=self._generate_changes_summary(diff_result),
            created_by=user,
            added_content='\n'.join(diff_result.added_lines),
            removed_content='\n'.join(diff_result.removed_lines)
        )

        # Përditëso version number të dokumentit
        document.version_number += 1
        document.save(update_fields=['version_number'])

        return version

    def _generate_diff(self, old_content: str, new_content: str) -> DocumentDiff:
        """
        Gjeneron diferenca të detajuara midis versioneve
        """
        old_lines = old_content.splitlines() if old_content else []
        new_lines = new_content.splitlines() if new_content else []
        
        diff = list(difflib.unified_diff(old_lines, new_lines, lineterm=''))
        
        added_lines = []
        removed_lines = []
        modified_lines = []
        
        i = 0
        while i < len(diff):
            line = diff[i]
            if line.startswith('+') and not line.startswith('+++'):
                added_lines.append(line[1:])
            elif line.startswith('-') and not line.startswith('---'):
                removed_lines.append(line[1:])
            i += 1

        # Statistika
        stats = {
            'lines_added': len(added_lines),
            'lines_removed': len(removed_lines),
            'lines_modified': len(modified_lines),
            'total_changes': len(added_lines) + len(removed_lines) + len(modified_lines)
        }

        return DocumentDiff(
            added_lines=added_lines,
            removed_lines=removed_lines,
            modified_lines=modified_lines,
            stats=stats
        )

    def _generate_changes_summary(self, diff_result: DocumentDiff) -> str:
        """
        Gjeneron një përmbledhje të ndryshimeve
        """
        stats = diff_result.stats
        summary_parts = []

        if stats['lines_added'] > 0:
            summary_parts.append(f"{stats['lines_added']} rreshta të shtuar")
        
        if stats['lines_removed'] > 0:
            summary_parts.append(f"{stats['lines_removed']} rreshta të hequr")
        
        if stats['lines_modified'] > 0:
            summary_parts.append(f"{stats['lines_modified']} rreshta të modifikuar")

        if not summary_parts:
            return "Ndryshime të vogla formatimi"

        return ", ".join(summary_parts)

    def get_document_versions(self, document: Document, limit: int = 10) -> List[DocumentVersion]:
        """
        Merr historikun e versioneve të dokumentit
        """
        return document.version_history.select_related('created_by')[:limit]

    def restore_document_version(self, 
                                document: Document, 
                                version_number: int, 
                                user: User) -> Document:
        """
        Rikthe një version të mëparshëm të dokumentit
        """
        if not document.can_edit(user):
            raise PermissionDenied("Nuk keni leje për të edituar këtë dokument.")

        try:
            version = document.version_history.get(version_number=version_number)
        except DocumentVersion.DoesNotExist:
            raise ValidationError(f"Versioni {version_number} nuk u gjet.")

        # Ruaj versionin aktual para se të rikthehesh
        self._create_document_version(document, document.content, document.content_html, user)

        with transaction.atomic():
            # Rikthe përmbajtjen
            document.content = version.content_snapshot
            document.content_html = version.content_html_snapshot
            document.metadata = version.metadata_snapshot.copy()
            document.last_edited_by = user
            document.last_edited_at = timezone.now()
            document.save()

            # Log action
            self._log_action(document, user, 'version_restore', {
                'restored_version': version_number,
                'previous_version': document.version_number
            })

        return document

    def add_comment(self, 
                   document: Document, 
                   content: str, 
                   user: User,
                   position_start: int = None,
                   position_end: int = None,
                   selected_text: str = "",
                   parent_comment_id: int = None) -> DocumentComment:
        """
        Shton një koment në dokument
        """
        parent_comment = None
        if parent_comment_id:
            try:
                parent_comment = DocumentComment.objects.get(
                    id=parent_comment_id, 
                    document=document
                )
            except DocumentComment.DoesNotExist:
                raise ValidationError("Komenti prind nuk u gjet.")

        comment = DocumentComment.objects.create(
            document=document,
            content=content,
            author=user,
            position_start=position_start,
            position_end=position_end,
            selected_text=selected_text,
            parent_comment=parent_comment
        )

        # Log action
        self._log_action(document, user, 'comment_add', {
            'comment_id': comment.id,
            'is_reply': parent_comment is not None,
            'has_position': position_start is not None
        })

        return comment

    def resolve_comment(self, comment_id: int, user: User) -> DocumentComment:
        """
        Zgjidh një koment
        """
        try:
            comment = DocumentComment.objects.get(id=comment_id)
        except DocumentComment.DoesNotExist:
            raise ValidationError("Komenti nuk u gjet.")

        if comment.is_resolved:
            raise ValidationError("Komenti është tashmë i zgjidhur.")

        comment.is_resolved = True
        comment.resolved_by = user
        comment.resolved_at = timezone.now()
        comment.save()

        # Log action
        self._log_action(comment.document, user, 'comment_resolve', {
            'comment_id': comment.id
        })

        return comment

    def get_document_comments(self, document: Document, include_resolved: bool = False) -> List[DocumentComment]:
        """
        Merr komentet e dokumentit
        """
        queryset = document.comments.select_related('author', 'resolved_by', 'parent_comment')
        
        if not include_resolved:
            queryset = queryset.filter(is_resolved=False)
        
        return queryset.order_by('position_start', 'created_at')

    # LLM Integration Methods

    def generate_document_with_llm(self, 
                                 document_type: str,
                                 case_info: Dict[str, Any],
                                 template_vars: Dict[str, Any],
                                 user: User) -> LLMResponse:
        """
        Gjeneron një dokument duke përdorur LLM
        """
        context = DocumentContext(
            title=template_vars.get('title', f'Dokument i Ri - {document_type}'),
            content="",
            document_type=document_type,
            case_type=case_info.get('case_type'),
            metadata=case_info
        )

        response = self.llm_service.generate_document(
            document_type=document_type,
            context=context,
            template_vars=template_vars
        )

        # Ruaj interaktimin
        if hasattr(user, 'id'):  # Sigurohu që user është valid
            LLMInteraction.objects.create(
                document_id=template_vars.get('document_id'),  # Mund të jetë None për dokumente të reja
                user=user,
                interaction_type='generate',
                prompt=f"Generate {document_type} with vars: {json.dumps(template_vars)}",
                llm_response=response.text,
                confidence_score=response.confidence,
                processing_time=response.processing_time,
                llm_model=response.model_used,
                llm_provider=response.provider,
                token_usage=response.token_usage or {}
            )

        return response

    def review_document_with_llm(self, 
                               document: Document, 
                               focus_areas: List[str],
                               user: User) -> LLMResponse:
        """
        Rishikon një dokument duke përdorur LLM
        """
        context = DocumentContext(
            title=document.title,
            content=document.content,
            document_type=document.document_type.name,
            case_type=document.case.case_type if hasattr(document.case, 'case_type') else None,
            metadata={
                'case_title': document.case.title if document.case else None,
                'document_status': document.status.name if document.status else None
            }
        )

        response = self.llm_service.review_document(
            context=context,
            focus_areas=focus_areas
        )

        # Ruaj interaktimin
        LLMInteraction.objects.create(
            document=document,
            user=user,
            interaction_type='review',
            prompt=f"Review document with focus on: {', '.join(focus_areas)}",
            llm_response=response.text,
            confidence_score=response.confidence,
            processing_time=response.processing_time,
            llm_model=response.model_used,
            llm_provider=response.provider,
            token_usage=response.token_usage or {},
            context_data={'focus_areas': focus_areas}
        )

        # Përditëso document metadata
        if not document.metadata:
            document.metadata = {}
        document.metadata['llm_last_review'] = timezone.now().isoformat()
        document.metadata['llm_review_focus'] = focus_areas
        document.llm_last_analysis = timezone.now()
        document.save(update_fields=['metadata', 'llm_last_analysis'])

        return response

    def get_suggestions_with_llm(self, 
                               document: Document, 
                               specific_section: str,
                               user: User) -> LLMResponse:
        """
        Merr sugjerime për përmirësim nga LLM
        """
        context = DocumentContext(
            title=document.title,
            content=document.content,
            document_type=document.document_type.name,
            case_type=document.case.case_type if hasattr(document.case, 'case_type') else None
        )

        response = self.llm_service.suggest_improvements(
            context=context,
            specific_section=specific_section
        )

        # Ruaj interaktimin
        LLMInteraction.objects.create(
            document=document,
            user=user,
            interaction_type='suggest',
            prompt=f"Suggest improvements for: {specific_section or 'entire document'}",
            llm_response=response.text,
            confidence_score=response.confidence,
            processing_time=response.processing_time,
            llm_model=response.model_used,
            llm_provider=response.provider,
            token_usage=response.token_usage or {},
            context_data={'section': specific_section}
        )

        # Përditëso suggestions në dokument
        if not document.llm_suggestions:
            document.llm_suggestions = []
        
        document.llm_suggestions.append({
            'timestamp': timezone.now().isoformat(),
            'section': specific_section,
            'suggestions': response.text,
            'user_id': user.id
        })
        
        document.save(update_fields=['llm_suggestions'])

        return response

    def translate_document_with_llm(self, 
                                  document: Document, 
                                  target_language: str,
                                  user: User) -> LLMResponse:
        """
        Përktheun një dokument duke përdorur LLM
        """
        context = DocumentContext(
            title=document.title,
            content=document.content,
            document_type=document.document_type.name,
            case_type=document.case.case_type if hasattr(document.case, 'case_type') else None
        )

        response = self.llm_service.translate_document(
            context=context,
            target_language=target_language
        )

        # Ruaj interaktimin
        LLMInteraction.objects.create(
            document=document,
            user=user,
            interaction_type='translate',
            prompt=f"Translate to {target_language}",
            llm_response=response.text,
            confidence_score=response.confidence,
            processing_time=response.processing_time,
            llm_model=response.model_used,
            llm_provider=response.provider,
            token_usage=response.token_usage or {},
            context_data={'target_language': target_language}
        )

        return response

    def auto_save_document(self, document: Document, content: str, user: User):
        """
        Auto-save funksionaliteti
        """
        cache_key = f"document_auto_save_{document.id}_{user.id}"
        last_save = cache.get(cache_key)
        
        current_time = timezone.now()
        
        if last_save is None or (current_time - last_save).total_seconds() >= self.auto_save_interval:
            self.save_document_content(
                document=document,
                content=content,
                user=user,
                auto_save=True
            )
            cache.set(cache_key, current_time, self.auto_save_interval * 2)

    def release_document_lock(self, document: Document, user: User):
        """
        Liro lock-un e dokumentit
        """
        if document.unlock_document(user):
            self._log_action(document, user, 'edit_end', {
                'lock_released': True,
                'edit_duration': (timezone.now() - document.locked_at).total_seconds() if document.locked_at else 0
            })

    def _log_action(self, document: Document, user: User, action: str, metadata: Dict[str, Any] = None):
        """
        Regjistron një veprim në audit log
        """
        DocumentAuditLog.objects.create(
            document=document,
            user=user,
            action=action,
            details=f"{action} performed by {user.username if user else 'system'}",
            metadata=metadata or {},
            timestamp=timezone.now()
        )

    def get_document_statistics(self, document: Document) -> Dict[str, Any]:
        """
        Merr statistika për dokumentin
        """
        stats = {
            'total_versions': document.version_history.count(),
            'total_comments': document.comments.count(),
            'unresolved_comments': document.comments.filter(is_resolved=False).count(),
            'total_llm_interactions': document.llm_interactions.count(),
            'word_count': len(document.content.split()) if document.content else 0,
            'character_count': len(document.content) if document.content else 0,
            'last_edited': document.last_edited_at,
            'creation_date': document.created_at,
            'edit_count': document.metadata.get('edit_count', 0) if document.metadata else 0
        }

        # Shto statistika të LLM interaktimeve
        llm_interactions = document.llm_interactions.all()
        if llm_interactions:
            stats['llm_stats'] = {
                'total_interactions': len(llm_interactions),
                'interaction_types': {},
                'avg_processing_time': 0,
                'total_tokens': 0
            }

            total_time = 0
            total_tokens = 0
            
            for interaction in llm_interactions:
                interaction_type = interaction.interaction_type
                stats['llm_stats']['interaction_types'][interaction_type] = (
                    stats['llm_stats']['interaction_types'].get(interaction_type, 0) + 1
                )
                
                if interaction.processing_time:
                    total_time += interaction.processing_time
                
                if interaction.token_usage:
                    total_tokens += interaction.token_usage.get('total_tokens', 0)

            if llm_interactions:
                stats['llm_stats']['avg_processing_time'] = total_time / len(llm_interactions)
                stats['llm_stats']['total_tokens'] = total_tokens

        return stats

    def search_documents_by_content(self, query: str, user: User, limit: int = 50) -> List[Document]:
        """
        Kërkon dokumente bazuar në përmbajtje
        """
        # Për tani përdor një kërkim të thjeshtë
        # Në të ardhmen mund të integrohet me Elasticsearch ose vector search
        documents = Document.objects.filter(
            content__icontains=query
        ).select_related('case', 'document_type', 'status', 'owned_by')

        # Filtro bazuar në permissions
        if not user.has_perm('documents.view_all_documents'):
            documents = documents.filter(
                models.Q(owned_by=user) |
                models.Q(created_by=user) |
                models.Q(editors__user=user) |
                models.Q(case__assigned_to=user)
            ).distinct()

        return documents[:limit]
