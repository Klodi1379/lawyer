"""
WebSocket Routing për Document Editor Module
Definon WebSocket URLs për real-time collaboration dhe notifications
"""

from django.urls import re_path, path
from . import consumers

websocket_urlpatterns = [
    # Document collaboration WebSocket
    re_path(
        r'ws/documents/(?P<document_id>\d+)/collaborate/$',
        consumers.DocumentCollaborationConsumer.as_asgi(),
        name='document_collaboration'
    ),
    
    # Notifications WebSocket
    re_path(
        r'ws/notifications/$',
        consumers.NotificationConsumer.as_asgi(),
        name='notifications'
    ),
    
    # Template editing WebSocket (për live preview)
    re_path(
        r'ws/templates/(?P<template_id>\d+)/edit/$',
        consumers.TemplateEditingConsumer.as_asgi(),
        name='template_editing'
    ),
    
    # Workflow updates WebSocket
    re_path(
        r'ws/workflows/(?P<workflow_id>\d+)/updates/$',
        consumers.WorkflowUpdatesConsumer.as_asgi(),
        name='workflow_updates'
    ),
    
    # Signature process WebSocket
    re_path(
        r'ws/signatures/(?P<request_id>\d+)/status/$',
        consumers.SignatureStatusConsumer.as_asgi(),
        name='signature_status'
    ),
    
    # General document editor dashboard
    re_path(
        r'ws/dashboard/$',
        consumers.DashboardConsumer.as_asgi(),
        name='dashboard'
    ),
]
