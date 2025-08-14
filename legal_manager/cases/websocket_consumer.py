# websocket_consumer.py - Real-time Dashboard WebSocket Consumer
import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from channels.exceptions import DenyConnection
from django.utils import timezone
from datetime import datetime, timedelta

from .models import User, CaseEvent, CaseDocument, Case, Client
from .dashboard_widgets.quick_actions import NotificationWidget
from .dashboard_widgets.analytics import get_all_widgets_data


class DashboardConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time dashboard updates and notifications
    """
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope["user"]
        
        # Reject anonymous users
        if self.user.is_anonymous:
            await self.close()
            return
        
        # Create room group name based on user ID
        self.room_group_name = f'dashboard_{self.user.id}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Dashboard WebSocket connected',
            'user_id': self.user.id,
            'timestamp': timezone.now().isoformat()
        }))
        
        # Send initial notifications
        await self.send_notifications()
        
        # Start periodic updates
        asyncio.create_task(self.periodic_updates())

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """Handle messages from WebSocket"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'request_notifications':
                await self.send_notifications()
                
            elif message_type == 'refresh_widget':
                widget_name = data.get('widget_name')
                await self.refresh_widget(widget_name)
                
            elif message_type == 'mark_notification_read':
                notification_id = data.get('notification_id')
                await self.mark_notification_read(notification_id)
                
            elif message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': timezone.now().isoformat()
                }))
                
            elif message_type == 'subscribe_to_case':
                case_id = data.get('case_id')
                await self.subscribe_to_case(case_id)
                
            elif message_type == 'unsubscribe_from_case':
                case_id = data.get('case_id')
                await self.unsubscribe_from_case(case_id)
                
        except json.JSONDecodeError:
            await self.send_error('Invalid JSON format')
        except Exception as e:
            await self.send_error(f'Error processing message: {str(e)}')

    async def send_notifications(self):
        """Send current notifications to the client"""
        try:
            notifications = await self.get_notifications()
            await self.send(text_data=json.dumps({
                'type': 'notifications_update',
                'notifications': notifications,
                'count': len(notifications),
                'timestamp': timezone.now().isoformat()
            }))
        except Exception as e:
            await self.send_error(f'Error getting notifications: {str(e)}')

    async def refresh_widget(self, widget_name):
        """Refresh specific widget data"""
        try:
            if not widget_name:
                await self.send_error('Widget name required')
                return
                
            widget_data = await self.get_widget_data(widget_name)
            await self.send(text_data=json.dumps({
                'type': 'widget_refresh',
                'widget_name': widget_name,
                'data': widget_data,
                'timestamp': timezone.now().isoformat()
            }))
        except Exception as e:
            await self.send_error(f'Error refreshing widget {widget_name}: {str(e)}')

    async def subscribe_to_case(self, case_id):
        """Subscribe to updates for a specific case"""
        try:
            case = await self.get_case(case_id)
            if not case:
                await self.send_error('Case not found')
                return
                
            # Check permissions
            if not await self.can_access_case(case):
                await self.send_error('Access denied')
                return
                
            # Add to case-specific group
            case_group_name = f'case_{case_id}'
            await self.channel_layer.group_add(
                case_group_name,
                self.channel_name
            )
            
            await self.send(text_data=json.dumps({
                'type': 'case_subscription_confirmed',
                'case_id': case_id,
                'case_title': case.title
            }))
            
        except Exception as e:
            await self.send_error(f'Error subscribing to case: {str(e)}')

    async def unsubscribe_from_case(self, case_id):
        """Unsubscribe from case updates"""
        try:
            case_group_name = f'case_{case_id}'
            await self.channel_layer.group_discard(
                case_group_name,
                self.channel_name
            )
            
            await self.send(text_data=json.dumps({
                'type': 'case_unsubscription_confirmed',
                'case_id': case_id
            }))
            
        except Exception as e:
            await self.send_error(f'Error unsubscribing from case: {str(e)}')

    async def periodic_updates(self):
        """Send periodic updates to the client"""
        while True:
            try:
                await asyncio.sleep(300)  # Update every 5 minutes
                
                # Send updated notifications
                await self.send_notifications()
                
                # Send system status
                await self.send_system_status()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in periodic updates: {e}")

    async def send_system_status(self):
        """Send system status information"""
        try:
            status = await self.get_system_status()
            await self.send(text_data=json.dumps({
                'type': 'system_status',
                'status': status,
                'timestamp': timezone.now().isoformat()
            }))
        except Exception as e:
            print(f"Error sending system status: {e}")

    # Group message handlers
    async def notification_update(self, event):
        """Handle notification updates from group"""
        await self.send(text_data=json.dumps({
            'type': 'new_notification',
            'notification': event['notification'],
            'timestamp': timezone.now().isoformat()
        }))

    async def widget_update(self, event):
        """Handle widget updates from group"""
        await self.send(text_data=json.dumps({
            'type': 'widget_data_update',
            'widget_name': event['widget_name'],
            'data': event['data'],
            'timestamp': timezone.now().isoformat()
        }))

    async def case_update(self, event):
        """Handle case updates from group"""
        await self.send(text_data=json.dumps({
            'type': 'case_update',
            'case_id': event['case_id'],
            'update_type': event['update_type'],
            'data': event['data'],
            'timestamp': timezone.now().isoformat()
        }))

    async def system_alert(self, event):
        """Handle system-wide alerts"""
        await self.send(text_data=json.dumps({
            'type': 'system_alert',
            'alert': event['alert'],
            'timestamp': timezone.now().isoformat()
        }))

    # Database operations
    @database_sync_to_async
    def get_notifications(self):
        """Get notifications for the current user"""
        notification_widget = NotificationWidget(self.user)
        return notification_widget.get_notifications()

    @database_sync_to_async
    def get_widget_data(self, widget_name):
        """Get data for a specific widget"""
        from .dashboard_widgets.analytics import get_widget_data
        return get_widget_data(widget_name, self.user)

    @database_sync_to_async
    def get_case(self, case_id):
        """Get case by ID"""
        try:
            return Case.objects.get(id=case_id)
        except Case.DoesNotExist:
            return None

    @database_sync_to_async
    def can_access_case(self, case):
        """Check if user can access the case"""
        if self.user.role == 'admin':
            return True
        elif self.user.role in ['lawyer', 'paralegal']:
            return case.assigned_to == self.user
        elif self.user.role == 'client':
            try:
                client = Client.objects.get(email=self.user.email)
                return case.client == client
            except Client.DoesNotExist:
                return False
        return False

    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """Mark notification as read"""
        # Implementation depends on notification storage
        # For now, just acknowledge the request
        return True

    @database_sync_to_async
    def get_system_status(self):
        """Get system status information"""
        # Basic system status
        total_cases = Case.objects.count()
        active_cases = Case.objects.exclude(status='closed').count()
        
        # User-specific counts
        if self.user.role == 'admin':
            user_cases = Case.objects.count()
        elif self.user.role in ['lawyer', 'paralegal']:
            user_cases = Case.objects.filter(assigned_to=self.user).count()
        else:
            try:
                client = Client.objects.get(email=self.user.email)
                user_cases = Case.objects.filter(client=client).count()
            except Client.DoesNotExist:
                user_cases = 0
        
        return {
            'total_cases': total_cases,
            'active_cases': active_cases,
            'user_cases': user_cases,
            'user_role': self.user.role,
            'online_users': 1,  # Could be enhanced with Redis tracking
            'server_time': timezone.now().isoformat()
        }

    # Utility methods
    async def send_error(self, message):
        """Send error message to client"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message,
            'timestamp': timezone.now().isoformat()
        }))


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    Specialized consumer for notifications only
    """
    
    async def connect(self):
        self.user = self.scope["user"]
        
        if self.user.is_anonymous:
            await self.close()
            return
        
        self.room_group_name = f'notifications_{self.user.id}'
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        
        if data['type'] == 'get_notifications':
            notifications = await self.get_notifications()
            await self.send(text_data=json.dumps({
                'type': 'notifications',
                'notifications': notifications
            }))

    async def notification_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'new_notification',
            'notification': event['notification']
        }))

    @database_sync_to_async
    def get_notifications(self):
        notification_widget = NotificationWidget(self.user)
        return notification_widget.get_notifications()


# Utility functions for sending group messages
async def send_user_notification(user_id, notification):
    """Send notification to specific user"""
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        f'dashboard_{user_id}',
        {
            'type': 'notification_update',
            'notification': notification
        }
    )

async def send_widget_update(user_id, widget_name, data):
    """Send widget update to specific user"""
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        f'dashboard_{user_id}',
        {
            'type': 'widget_update',
            'widget_name': widget_name,
            'data': data
        }
    )

async def send_case_update(case_id, update_type, data):
    """Send case update to all subscribers"""
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        f'case_{case_id}',
        {
            'type': 'case_update',
            'case_id': case_id,
            'update_type': update_type,
            'data': data
        }
    )

async def send_system_alert(alert_data):
    """Send system-wide alert to all connected users"""
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    # This would require a mechanism to track all active users
    # For now, it's a placeholder for future implementation
    pass
