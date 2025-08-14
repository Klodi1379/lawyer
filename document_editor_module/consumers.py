"""
WebSocket Consumers për Real-time Collaboration
Menaxhon real-time editing, comments, notifications dhe presence
"""

import json
import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import PermissionDenied

from .models.document_models import Document, DocumentComment, DocumentAuditLog
from .services.document_service import DocumentEditingService

User = get_user_model()
logger = logging.getLogger(__name__)

@dataclass
class UserPresence:
    """User presence në dokument"""
    user_id: int
    username: str
    full_name: str
    role: str
    cursor_position: int = 0
    selection_start: int = 0
    selection_end: int = 0
    last_seen: datetime = None
    color: str = "#007bff"  # Default color
    
    def __post_init__(self):
        if self.last_seen is None:
            self.last_seen = timezone.now()

@dataclass
class EditOperation:
    """Operacion editimi në real-time"""
    operation_id: str
    user_id: int
    operation_type: str  # insert, delete, replace
    position: int
    length: int = 0
    content: str = ""
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = timezone.now()

class DocumentCollaborationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer për collaboration në dokumente
    Menaxhon real-time editing, presence, comments dhe notifications
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.document_id = None
        self.document_group_name = None
        self.user = None
        self.user_presence = None
        self.editing_service = DocumentEditingService()
        
        # In-memory storage për operations (në production përdor Redis)
        self.pending_operations = []
        self.applied_operations = []
        
    async def connect(self):
        """Connect në WebSocket"""
        try:
            # Get document ID from URL
            self.document_id = self.scope['url_route']['kwargs']['document_id']
            self.document_group_name = f'document_{self.document_id}'
            self.user = self.scope['user']
            
            # Check authentication
            if not self.user.is_authenticated:
                await self.close(code=4001)
                return
            
            # Check document permissions
            can_access = await self.check_document_access()
            if not can_access:
                await self.close(code=4003)
                return
            
            # Join document group
            await self.channel_layer.group_add(
                self.document_group_name,
                self.channel_name
            )
            
            # Accept connection
            await self.accept()
            
            # Create user presence
            self.user_presence = UserPresence(
                user_id=self.user.id,
                username=self.user.username,
                full_name=self.user.get_full_name() or self.user.username,
                role=getattr(self.user, 'role', 'user'),
                color=self._generate_user_color()
            )
            
            # Notify group about new user
            await self.channel_layer.group_send(
                self.document_group_name,
                {
                    'type': 'user_joined',
                    'user': asdict(self.user_presence)
                }
            )
            
            # Send current document state to user
            await self.send_document_state()
            
            logger.info(f"User {self.user.username} connected to document {self.document_id}")
            
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            await self.close(code=4000)

    async def disconnect(self, close_code):
        """Disconnect nga WebSocket"""
        try:
            if self.document_group_name and self.user_presence:
                # Notify group about user leaving
                await self.channel_layer.group_send(
                    self.document_group_name,
                    {
                        'type': 'user_left',
                        'user_id': self.user_presence.user_id
                    }
                )
                
                # Leave group
                await self.channel_layer.group_discard(
                    self.document_group_name,
                    self.channel_name
                )
                
                logger.info(f"User {self.user.username} disconnected from document {self.document_id}")
                
        except Exception as e:
            logger.error(f"WebSocket disconnect error: {e}")

    async def receive(self, text_data):
        """Receive message nga WebSocket"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            # Route message në handler të përshtatshëm
            if message_type == 'edit_operation':
                await self.handle_edit_operation(data)
            elif message_type == 'cursor_update':
                await self.handle_cursor_update(data)
            elif message_type == 'selection_update':
                await self.handle_selection_update(data)
            elif message_type == 'comment_add':
                await self.handle_comment_add(data)
            elif message_type == 'document_lock':
                await self.handle_document_lock(data)
            elif message_type == 'document_save':
                await self.handle_document_save(data)
            elif message_type == 'presence_update':
                await self.handle_presence_update(data)
            else:
                await self.send_error(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"WebSocket receive error: {e}")
            await self.send_error(str(e))

    async def handle_edit_operation(self, data):
        """Handle edit operation"""
        try:
            # Validate edit operation
            operation_data = data.get('operation', {})
            required_fields = ['operation_id', 'operation_type', 'position']
            
            for field in required_fields:
                if field not in operation_data:
                    await self.send_error(f"Missing required field: {field}")
                    return
            
            # Check if user can edit document
            can_edit = await self.check_edit_permission()
            if not can_edit:
                await self.send_error("Permission denied: Cannot edit document")
                return
            
            # Create edit operation
            edit_op = EditOperation(
                operation_id=operation_data['operation_id'],
                user_id=self.user.id,
                operation_type=operation_data['operation_type'],
                position=operation_data['position'],
                length=operation_data.get('length', 0),
                content=operation_data.get('content', '')
            )
            
            # Apply operation locally (operational transformation mund të shtohet këtu)
            self.pending_operations.append(edit_op)
            
            # Broadcast operation to all clients
            await self.channel_layer.group_send(
                self.document_group_name,
                {
                    'type': 'edit_operation_broadcast',
                    'operation': asdict(edit_op),
                    'sender_channel': self.channel_name
                }
            )
            
            # Save operation to database (periodic save)
            await self.queue_document_save()
            
        except Exception as e:
            logger.error(f"Edit operation error: {e}")
            await self.send_error(f"Edit operation failed: {str(e)}")

    async def handle_cursor_update(self, data):
        """Handle cursor position update"""
        try:
            cursor_position = data.get('position', 0)
            
            if self.user_presence:
                self.user_presence.cursor_position = cursor_position
                self.user_presence.last_seen = timezone.now()
            
            # Broadcast cursor update
            await self.channel_layer.group_send(
                self.document_group_name,
                {
                    'type': 'cursor_update_broadcast',
                    'user_id': self.user.id,
                    'position': cursor_position,
                    'sender_channel': self.channel_name
                }
            )
            
        except Exception as e:
            logger.error(f"Cursor update error: {e}")

    async def handle_selection_update(self, data):
        """Handle text selection update"""
        try:
            selection_start = data.get('start', 0)
            selection_end = data.get('end', 0)
            
            if self.user_presence:
                self.user_presence.selection_start = selection_start
                self.user_presence.selection_end = selection_end
                self.user_presence.last_seen = timezone.now()
            
            # Broadcast selection update
            await self.channel_layer.group_send(
                self.document_group_name,
                {
                    'type': 'selection_update_broadcast',
                    'user_id': self.user.id,
                    'start': selection_start,
                    'end': selection_end,
                    'sender_channel': self.channel_name
                }
            )
            
        except Exception as e:
            logger.error(f"Selection update error: {e}")

    async def handle_comment_add(self, data):
        """Handle new comment"""
        try:
            comment_data = data.get('comment', {})
            
            # Validate comment data
            if not comment_data.get('content'):
                await self.send_error("Comment content is required")
                return
            
            # Save comment to database
            comment = await self.save_comment(comment_data)
            
            if comment:
                # Broadcast new comment
                await self.channel_layer.group_send(
                    self.document_group_name,
                    {
                        'type': 'comment_added_broadcast',
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
                            'created_at': comment.created_at.isoformat()
                        },
                        'sender_channel': self.channel_name
                    }
                )
            
        except Exception as e:
            logger.error(f"Comment add error: {e}")
            await self.send_error(f"Failed to add comment: {str(e)}")

    async def handle_document_lock(self, data):
        """Handle document lock/unlock"""
        try:
            action = data.get('action')  # 'lock' or 'unlock'
            
            if action == 'lock':
                success = await self.lock_document()
            elif action == 'unlock':
                success = await self.unlock_document()
            else:
                await self.send_error("Invalid lock action")
                return
            
            if success:
                # Broadcast lock status change
                await self.channel_layer.group_send(
                    self.document_group_name,
                    {
                        'type': 'document_lock_broadcast',
                        'action': action,
                        'user_id': self.user.id,
                        'username': self.user.username,
                        'sender_channel': self.channel_name
                    }
                )
            else:
                await self.send_error(f"Failed to {action} document")
                
        except Exception as e:
            logger.error(f"Document lock error: {e}")
            await self.send_error(f"Lock operation failed: {str(e)}")

    async def handle_document_save(self, data):
        """Handle document save"""
        try:
            content = data.get('content', '')
            content_html = data.get('content_html', '')
            
            # Check edit permissions
            can_edit = await self.check_edit_permission()
            if not can_edit:
                await self.send_error("Permission denied: Cannot save document")
                return
            
            # Save document
            success = await self.save_document(content, content_html)
            
            if success:
                # Broadcast save success
                await self.channel_layer.group_send(
                    self.document_group_name,
                    {
                        'type': 'document_saved_broadcast',
                        'user_id': self.user.id,
                        'username': self.user.username,
                        'timestamp': timezone.now().isoformat(),
                        'sender_channel': self.channel_name
                    }
                )
                
                await self.send_success("Document saved successfully")
            else:
                await self.send_error("Failed to save document")
                
        except Exception as e:
            logger.error(f"Document save error: {e}")
            await self.send_error(f"Save failed: {str(e)}")

    async def handle_presence_update(self, data):
        """Handle presence update"""
        try:
            if self.user_presence:
                self.user_presence.last_seen = timezone.now()
                
                # Update any additional presence data
                if 'cursor_position' in data:
                    self.user_presence.cursor_position = data['cursor_position']
                
                # Broadcast updated presence
                await self.channel_layer.group_send(
                    self.document_group_name,
                    {
                        'type': 'presence_update_broadcast',
                        'user': asdict(self.user_presence),
                        'sender_channel': self.channel_name
                    }
                )
                
        except Exception as e:
            logger.error(f"Presence update error: {e}")

    # Broadcast handlers (receive messages from group)
    
    async def user_joined(self, event):
        """Handle user joined broadcast"""
        if event.get('sender_channel') != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'user_joined',
                'user': event['user']
            }))

    async def user_left(self, event):
        """Handle user left broadcast"""
        await self.send(text_data=json.dumps({
            'type': 'user_left',
            'user_id': event['user_id']
        }))

    async def edit_operation_broadcast(self, event):
        """Handle edit operation broadcast"""
        # Don't send back to sender
        if event.get('sender_channel') != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'edit_operation',
                'operation': event['operation']
            }))

    async def cursor_update_broadcast(self, event):
        """Handle cursor update broadcast"""
        if event.get('sender_channel') != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'cursor_update',
                'user_id': event['user_id'],
                'position': event['position']
            }))

    async def selection_update_broadcast(self, event):
        """Handle selection update broadcast"""
        if event.get('sender_channel') != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'selection_update',
                'user_id': event['user_id'],
                'start': event['start'],
                'end': event['end']
            }))

    async def comment_added_broadcast(self, event):
        """Handle comment added broadcast"""
        if event.get('sender_channel') != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'comment_added',
                'comment': event['comment']
            }))

    async def document_lock_broadcast(self, event):
        """Handle document lock broadcast"""
        if event.get('sender_channel') != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'document_lock',
                'action': event['action'],
                'user_id': event['user_id'],
                'username': event['username']
            }))

    async def document_saved_broadcast(self, event):
        """Handle document saved broadcast"""
        if event.get('sender_channel') != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'document_saved',
                'user_id': event['user_id'],
                'username': event['username'],
                'timestamp': event['timestamp']
            }))

    async def presence_update_broadcast(self, event):
        """Handle presence update broadcast"""
        if event.get('sender_channel') != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'presence_update',
                'user': event['user']
            }))

    # Utility methods
    
    async def send_error(self, message: str):
        """Send error message to client"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message
        }))

    async def send_success(self, message: str):
        """Send success message to client"""
        await self.send(text_data=json.dumps({
            'type': 'success',
            'message': message
        }))

    async def send_document_state(self):
        """Send current document state to client"""
        try:
            document = await self.get_document()
            if document:
                await self.send(text_data=json.dumps({
                    'type': 'document_state',
                    'document': {
                        'id': document.id,
                        'title': document.title,
                        'content': document.content,
                        'content_html': document.content_html or '',
                        'is_locked': document.is_locked,
                        'locked_by': {
                            'id': document.locked_by.id,
                            'username': document.locked_by.username
                        } if document.locked_by else None,
                        'version_number': document.version_number,
                        'last_edited_at': document.last_edited_at.isoformat() if document.last_edited_at else None
                    }
                }))
        except Exception as e:
            logger.error(f"Send document state error: {e}")
            await self.send_error("Failed to load document state")

    def _generate_user_color(self) -> str:
        """Generate unique color for user"""
        colors = [
            "#007bff", "#28a745", "#dc3545", "#ffc107", "#17a2b8",
            "#6f42c1", "#e83e8c", "#fd7e14", "#20c997", "#6c757d"
        ]
        return colors[self.user.id % len(colors)]

    async def queue_document_save(self):
        """Queue document save operation"""
        # Implement periodic saving logic
        # This could use Celery tasks or Redis queues
        pass

    # Database operations (async wrappers)
    
    @database_sync_to_async
    def check_document_access(self) -> bool:
        """Check if user can access document"""
        try:
            document = Document.objects.get(id=self.document_id)
            
            if self.user.role == 'admin':
                return True
            elif self.user.role == 'client':
                return document.case.client.user == self.user
            elif self.user.role in ['lawyer', 'paralegal']:
                return (
                    document.owned_by == self.user or
                    document.created_by == self.user or
                    document.editors.filter(user=self.user).exists() or
                    document.case.assigned_to == self.user
                )
            
            return False
        except Document.DoesNotExist:
            return False

    @database_sync_to_async
    def check_edit_permission(self) -> bool:
        """Check if user can edit document"""
        try:
            document = Document.objects.get(id=self.document_id)
            return document.can_edit(self.user)
        except Document.DoesNotExist:
            return False

    @database_sync_to_async
    def get_document(self) -> Optional[Document]:
        """Get document instance"""
        try:
            return Document.objects.select_related('locked_by').get(id=self.document_id)
        except Document.DoesNotExist:
            return None

    @database_sync_to_async
    def save_comment(self, comment_data: Dict[str, Any]) -> Optional[DocumentComment]:
        """Save comment to database"""
        try:
            document = Document.objects.get(id=self.document_id)
            
            comment = DocumentComment.objects.create(
                document=document,
                content=comment_data['content'],
                author=self.user,
                position_start=comment_data.get('position_start'),
                position_end=comment_data.get('position_end'),
                selected_text=comment_data.get('selected_text', '')
            )
            
            return comment
        except Exception as e:
            logger.error(f"Save comment error: {e}")
            return None

    @database_sync_to_async
    def lock_document(self) -> bool:
        """Lock document for editing"""
        try:
            document = Document.objects.get(id=self.document_id)
            return document.lock_document(self.user)
        except Exception as e:
            logger.error(f"Lock document error: {e}")
            return False

    @database_sync_to_async
    def unlock_document(self) -> bool:
        """Unlock document"""
        try:
            document = Document.objects.get(id=self.document_id)
            return document.unlock_document(self.user)
        except Exception as e:
            logger.error(f"Unlock document error: {e}")
            return False

    @database_sync_to_async
    def save_document(self, content: str, content_html: str = '') -> bool:
        """Save document content"""
        try:
            document = Document.objects.get(id=self.document_id)
            
            if not document.can_edit(self.user):
                return False
            
            # Use editing service for proper saving
            editing_service = DocumentEditingService()
            editing_service.save_document_content(
                document=document,
                content=content,
                content_html=content_html,
                user=self.user,
                auto_save=True
            )
            
            return True
        except Exception as e:
            logger.error(f"Save document error: {e}")
            return False

class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer për notifications
    Menaxhon workflow notifications, document updates, etc.
    """
    
    async def connect(self):
        """Connect për notifications"""
        if not self.scope['user'].is_authenticated:
            await self.close(code=4001)
            return
        
        self.user = self.scope['user']
        self.notification_group_name = f'notifications_{self.user.id}'
        
        # Join notification group
        await self.channel_layer.group_add(
            self.notification_group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"User {self.user.username} connected to notifications")

    async def disconnect(self, close_code):
        """Disconnect nga notifications"""
        if hasattr(self, 'notification_group_name'):
            await self.channel_layer.group_discard(
                self.notification_group_name,
                self.channel_name
            )
            logger.info(f"User {self.user.username} disconnected from notifications")

    async def receive(self, text_data):
        """Handle incoming notification messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'mark_read':
                notification_id = data.get('notification_id')
                await self.mark_notification_read(notification_id)
            elif message_type == 'get_unread_count':
                count = await self.get_unread_count()
                await self.send(text_data=json.dumps({
                    'type': 'unread_count',
                    'count': count
                }))
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))

    # Notification broadcasters
    
    async def workflow_notification(self, event):
        """Handle workflow notification"""
        await self.send(text_data=json.dumps({
            'type': 'workflow_notification',
            'notification': event['notification']
        }))

    async def document_notification(self, event):
        """Handle document notification"""
        await self.send(text_data=json.dumps({
            'type': 'document_notification',
            'notification': event['notification']
        }))

    async def comment_notification(self, event):
        """Handle comment notification"""
        await self.send(text_data=json.dumps({
            'type': 'comment_notification',
            'notification': event['notification']
        }))

    @database_sync_to_async
    def mark_notification_read(self, notification_id: int):
        """Mark notification as read"""
        # Implement notification marking logic
        pass

    @database_sync_to_async
    def get_unread_count(self) -> int:
        """Get unread notification count"""
        # Implement unread count logic
        return 0

class TemplateEditingConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer për template editing me live preview
    """
    
    async def connect(self):
        """Connect për template editing"""
        if not self.scope['user'].is_authenticated:
            await self.close(code=4001)
            return
        
        self.template_id = self.scope['url_route']['kwargs']['template_id']
        self.template_group_name = f'template_{self.template_id}'
        self.user = self.scope['user']
        
        # Check permissions
        can_edit = await self.check_template_edit_permission()
        if not can_edit:
            await self.close(code=4003)
            return
        
        await self.channel_layer.group_add(
            self.template_group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"User {self.user.username} connected to template {self.template_id} editing")

    async def disconnect(self, close_code):
        """Disconnect nga template editing"""
        if hasattr(self, 'template_group_name'):
            await self.channel_layer.group_discard(
                self.template_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        """Handle template editing messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'template_update':
                await self.handle_template_update(data)
            elif message_type == 'preview_request':
                await self.handle_preview_request(data)
            elif message_type == 'variable_update':
                await self.handle_variable_update(data)
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Template editing error: {e}")
            await self.send_error(str(e))

    async def handle_template_update(self, data):
        """Handle template content update"""
        content = data.get('content', '')
        
        # Broadcast update to other editors
        await self.channel_layer.group_send(
            self.template_group_name,
            {
                'type': 'template_update_broadcast',
                'content': content,
                'user_id': self.user.id,
                'timestamp': timezone.now().isoformat(),
                'sender_channel': self.channel_name
            }
        )

    async def handle_preview_request(self, data):
        """Handle live preview request"""
        try:
            from .advanced_features.template_engine import LegalTemplateEngine
            
            content = data.get('content', '')
            variables = data.get('variables', {})
            
            # Generate preview
            template_engine = LegalTemplateEngine()
            preview = await self.generate_template_preview(content, variables)
            
            await self.send(text_data=json.dumps({
                'type': 'preview_result',
                'preview': preview,
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as e:
            await self.send_error(f"Preview generation failed: {str(e)}")

    async def template_update_broadcast(self, event):
        """Handle template update broadcast"""
        if event.get('sender_channel') != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'template_update',
                'content': event['content'],
                'user_id': event['user_id'],
                'timestamp': event['timestamp']
            }))

    @database_sync_to_async
    def check_template_edit_permission(self) -> bool:
        """Check template edit permission"""
        try:
            from .models.document_models import DocumentTemplate
            template = DocumentTemplate.objects.get(id=self.template_id)
            return (
                self.user.role == 'admin' or
                template.created_by == self.user
            )
        except DocumentTemplate.DoesNotExist:
            return False

    @database_sync_to_async
    def generate_template_preview(self, content: str, variables: dict) -> str:
        """Generate template preview"""
        try:
            from .advanced_features.template_engine import LegalTemplateEngine, TemplateContext
            
            engine = LegalTemplateEngine()
            context = TemplateContext(variables=variables)
            
            # Create temporary template for preview
            from .models.document_models import DocumentTemplate
            temp_template = DocumentTemplate(content=content)
            
            return engine.render_template(temp_template, context, validate_variables=False)
        except Exception as e:
            return f"Preview Error: {str(e)}"

    async def send_error(self, message: str):
        """Send error message"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message
        }))

class WorkflowUpdatesConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer për workflow updates në real-time
    """
    
    async def connect(self):
        """Connect për workflow updates"""
        if not self.scope['user'].is_authenticated:
            await self.close(code=4001)
            return
        
        self.workflow_id = self.scope['url_route']['kwargs']['workflow_id']
        self.workflow_group_name = f'workflow_{self.workflow_id}'
        self.user = self.scope['user']
        
        # Check permissions
        can_view = await self.check_workflow_view_permission()
        if not can_view:
            await self.close(code=4003)
            return
        
        await self.channel_layer.group_add(
            self.workflow_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send current workflow status
        await self.send_workflow_status()

    async def disconnect(self, close_code):
        """Disconnect nga workflow updates"""
        if hasattr(self, 'workflow_group_name'):
            await self.channel_layer.group_discard(
                self.workflow_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        """Handle workflow update messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'action_execute':
                await self.handle_workflow_action(data)
            elif message_type == 'status_request':
                await self.send_workflow_status()
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")

    async def handle_workflow_action(self, data):
        """Handle workflow action execution"""
        try:
            step_id = data.get('step_id')
            action_type = data.get('action_type')
            comment = data.get('comment', '')
            
            # Execute action using workflow engine
            success = await self.execute_workflow_action(step_id, action_type, comment)
            
            if success:
                # Broadcast action to all viewers
                await self.channel_layer.group_send(
                    self.workflow_group_name,
                    {
                        'type': 'workflow_action_broadcast',
                        'step_id': step_id,
                        'action_type': action_type,
                        'user_id': self.user.id,
                        'username': self.user.username,
                        'comment': comment,
                        'timestamp': timezone.now().isoformat(),
                        'sender_channel': self.channel_name
                    }
                )
            else:
                await self.send_error("Action execution failed")
                
        except Exception as e:
            await self.send_error(f"Workflow action error: {str(e)}")

    async def workflow_action_broadcast(self, event):
        """Handle workflow action broadcast"""
        await self.send(text_data=json.dumps({
            'type': 'workflow_action',
            'step_id': event['step_id'],
            'action_type': event['action_type'],
            'user_id': event['user_id'],
            'username': event['username'],
            'comment': event['comment'],
            'timestamp': event['timestamp']
        }))

    async def workflow_status_update(self, event):
        """Handle workflow status update"""
        await self.send(text_data=json.dumps({
            'type': 'status_update',
            'workflow_status': event['status'],
            'current_step': event['current_step'],
            'progress': event['progress']
        }))

    async def send_workflow_status(self):
        """Send current workflow status"""
        status = await self.get_workflow_status()
        if status:
            await self.send(text_data=json.dumps({
                'type': 'workflow_status',
                'status': status
            }))

    @database_sync_to_async
    def check_workflow_view_permission(self) -> bool:
        """Check workflow view permission"""
        try:
            from .advanced_features.workflow_system import DocumentWorkflow
            workflow = DocumentWorkflow.objects.get(id=self.workflow_id)
            
            if self.user.role == 'admin':
                return True
            
            document = workflow.document
            return (
                document.owned_by == self.user or
                document.case.assigned_to == self.user or
                workflow.steps.filter(assigned_users=self.user).exists()
            )
        except Exception:
            return False

    @database_sync_to_async
    def execute_workflow_action(self, step_id: int, action_type: str, comment: str) -> bool:
        """Execute workflow action"""
        try:
            from .advanced_features.workflow_system import WorkflowEngine, WorkflowStep, ActionType
            
            step = WorkflowStep.objects.get(id=step_id)
            engine = WorkflowEngine()
            
            return engine.execute_action(
                step=step,
                action_type=ActionType(action_type),
                user=self.user,
                comment=comment
            )
        except Exception as e:
            logger.error(f"Workflow action execution error: {e}")
            return False

    @database_sync_to_async
    def get_workflow_status(self) -> Optional[Dict[str, Any]]:
        """Get workflow status"""
        try:
            from .advanced_features.workflow_system import DocumentWorkflow
            workflow = DocumentWorkflow.objects.get(id=self.workflow_id)
            
            return {
                'id': workflow.id,
                'status': workflow.status,
                'current_step': workflow.current_step,
                'total_steps': workflow.total_steps,
                'completed_steps': workflow.completed_steps,
                'progress_percentage': workflow.progress_percentage,
                'started_at': workflow.started_at.isoformat(),
                'completed_at': workflow.completed_at.isoformat() if workflow.completed_at else None
            }
        except Exception:
            return None

    async def send_error(self, message: str):
        """Send error message"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message
        }))

class SignatureStatusConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer për signature process status updates
    """
    
    async def connect(self):
        """Connect për signature status"""
        if not self.scope['user'].is_authenticated:
            await self.close(code=4001)
            return
        
        self.request_id = self.scope['url_route']['kwargs']['request_id']
        self.signature_group_name = f'signature_{self.request_id}'
        self.user = self.scope['user']
        
        # Check permissions
        can_view = await self.check_signature_view_permission()
        if not can_view:
            await self.close(code=4003)
            return
        
        await self.channel_layer.group_add(
            self.signature_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send current signature status
        await self.send_signature_status()

    async def disconnect(self, close_code):
        """Disconnect nga signature status"""
        if hasattr(self, 'signature_group_name'):
            await self.channel_layer.group_discard(
                self.signature_group_name,
                self.channel_name
            )

    async def signature_signed(self, event):
        """Handle signature signed event"""
        await self.send(text_data=json.dumps({
            'type': 'signature_signed',
            'signer': event['signer'],
            'timestamp': event['timestamp'],
            'progress': event['progress']
        }))

    async def signature_completed(self, event):
        """Handle signature process completed"""
        await self.send(text_data=json.dumps({
            'type': 'signature_completed',
            'completed_at': event['completed_at'],
            'all_signers': event['all_signers']
        }))

    async def signature_declined(self, event):
        """Handle signature declined"""
        await self.send(text_data=json.dumps({
            'type': 'signature_declined',
            'declined_by': event['declined_by'],
            'reason': event.get('reason', ''),
            'timestamp': event['timestamp']
        }))

    async def send_signature_status(self):
        """Send current signature status"""
        status = await self.get_signature_status()
        if status:
            await self.send(text_data=json.dumps({
                'type': 'signature_status',
                'status': status
            }))

    @database_sync_to_async
    def check_signature_view_permission(self) -> bool:
        """Check signature view permission"""
        try:
            from .advanced_features.signature_system import SignatureRequest
            request = SignatureRequest.objects.get(id=self.request_id)
            
            if self.user.role == 'admin':
                return True
            
            # Check if user is document owner or signer
            document = request.document
            if document.owned_by == self.user:
                return True
            
            # Check if user is one of the signers
            signers = request.signers_data.get('signers', [])
            return any(signer.get('email') == self.user.email for signer in signers)
            
        except Exception:
            return False

    @database_sync_to_async
    def get_signature_status(self) -> Optional[Dict[str, Any]]:
        """Get signature status"""
        try:
            from .advanced_features.signature_system import SignatureRequest
            request = SignatureRequest.objects.get(id=self.request_id)
            
            return {
                'id': request.id,
                'status': request.status,
                'signers_count': request.signers_count,
                'signed_count': request.signed_count,
                'progress_percentage': request.progress_percentage,
                'created_at': request.created_at.isoformat(),
                'expires_at': request.expires_at.isoformat() if request.expires_at else None
            }
        except Exception:
            return None

class DashboardConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer për dashboard real-time updates
    """
    
    async def connect(self):
        """Connect për dashboard"""
        if not self.scope['user'].is_authenticated:
            await self.close(code=4001)
            return
        
        self.user = self.scope['user']
        self.dashboard_group_name = f'dashboard_{self.user.id}'
        
        await self.channel_layer.group_add(
            self.dashboard_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial dashboard data
        await self.send_dashboard_data()

    async def disconnect(self, close_code):
        """Disconnect nga dashboard"""
        if hasattr(self, 'dashboard_group_name'):
            await self.channel_layer.group_discard(
                self.dashboard_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        """Handle dashboard messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'refresh_data':
                await self.send_dashboard_data()
                
        except json.JSONDecodeError:
            pass

    async def dashboard_update(self, event):
        """Handle dashboard update"""
        await self.send(text_data=json.dumps({
            'type': 'dashboard_update',
            'update_type': event['update_type'],
            'data': event['data']
        }))

    async def task_notification(self, event):
        """Handle task notification"""
        await self.send(text_data=json.dumps({
            'type': 'task_notification',
            'notification': event['notification']
        }))

    async def send_dashboard_data(self):
        """Send dashboard data"""
        data = await self.get_dashboard_data()
        await self.send(text_data=json.dumps({
            'type': 'dashboard_data',
            'data': data
        }))

    @database_sync_to_async
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get dashboard data"""
        try:
            from .models.document_models import Document
            from .advanced_features.workflow_system import WorkflowStep, WorkflowStepStatus
            
            # Get user's pending tasks
            pending_tasks = WorkflowStep.objects.filter(
                assigned_users=self.user,
                status__in=[WorkflowStepStatus.PENDING.value, WorkflowStepStatus.IN_PROGRESS.value]
            ).count()
            
            # Get user's recent documents
            recent_documents = Document.objects.filter(
                Q(owned_by=self.user) | Q(last_edited_by=self.user)
            ).order_by('-updated_at')[:5].count()
            
            # Get overdue tasks
            overdue_tasks = WorkflowStep.objects.filter(
                assigned_users=self.user,
                status__in=[WorkflowStepStatus.PENDING.value, WorkflowStepStatus.IN_PROGRESS.value],
                deadline__lt=timezone.now()
            ).count()
            
            return {
                'pending_tasks': pending_tasks,
                'recent_documents': recent_documents,
                'overdue_tasks': overdue_tasks,
                'timestamp': timezone.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Dashboard data error: {e}")
            return {}
