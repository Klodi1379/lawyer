"""
Electronic Signature System - Sistem i avancuar për nënshkrime elektronike
Integron me DocuSign, Adobe Sign dhe sisteme të tjera e-signature
"""

import base64
import hashlib
import hmac
import json
import uuid
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import requests
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization

from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from ..models.document_models import Document, DocumentSignature, DocumentAuditLog

User = get_user_model()

class SignatureProvider(Enum):
    """Providerat e nënshkrimit elektronik"""
    INTERNAL = "internal"
    DOCUSIGN = "docusign"
    ADOBE_SIGN = "adobe_sign"
    HELLOSIGN = "hellosign"
    PANDADOC = "pandadoc"

class SignatureType(Enum):
    """Llojet e nënshkrimit"""
    SIMPLE = "simple"          # Simple electronic signature
    ADVANCED = "advanced"      # Advanced electronic signature
    QUALIFIED = "qualified"    # Qualified electronic signature (highest level)

class SignatureStatus(Enum):
    """Statuset e procesit të nënshkrimit"""
    DRAFT = "draft"
    SENT = "sent" 
    DELIVERED = "delivered"
    SIGNED = "signed"
    COMPLETED = "completed"
    DECLINED = "declined"
    CANCELLED = "cancelled"
    EXPIRED = "expired"

@dataclass
class SignerInfo:
    """Informacioni i nënshkruesit"""
    name: str
    email: str
    phone: Optional[str] = None
    role: str = "Signer"
    order: int = 1
    authentication_method: str = "email"
    required: bool = True
    user_id: Optional[int] = None

@dataclass
class SignatureField:
    """Fusha e nënshkrimit në dokument"""
    page_number: int
    x_position: int
    y_position: int
    width: int = 150
    height: int = 50
    signer_email: str = ""
    field_type: str = "signature"  # signature, initial, date, text
    required: bool = True
    field_name: str = ""

class SignatureService:
    """Service kryesor për menaxhimin e nënshkrimeve elektronike"""
    
    def __init__(self, provider: SignatureProvider = None):
        self.provider = provider or SignatureProvider(
            getattr(settings, 'SIGNATURE_PROVIDER', 'internal')
        )
        self.api_key = self._get_api_key()
        self.base_url = self._get_base_url()
        self.encryption_key = self._get_encryption_key()
        
    def _get_api_key(self) -> str:
        """Merr API key për providerin"""
        key_mapping = {
            SignatureProvider.DOCUSIGN: 'DOCUSIGN_API_KEY',
            SignatureProvider.ADOBE_SIGN: 'ADOBE_SIGN_API_KEY',
            SignatureProvider.HELLOSIGN: 'HELLOSIGN_API_KEY',
            SignatureProvider.PANDADOC: 'PANDADOC_API_KEY'
        }
        
        if self.provider in key_mapping:
            return getattr(settings, key_mapping[self.provider], '')
        return ''
    
    def _get_base_url(self) -> str:
        """Merr base URL për providerin"""
        url_mapping = {
            SignatureProvider.DOCUSIGN: getattr(settings, 'DOCUSIGN_BASE_URL', 'https://demo.docusign.net/restapi'),
            SignatureProvider.ADOBE_SIGN: 'https://api.adobesign.com/api/rest/v6',
            SignatureProvider.HELLOSIGN: 'https://api.hellosign.com/v3',
            SignatureProvider.PANDADOC: 'https://api.pandadoc.com/public/v1'
        }
        return url_mapping.get(self.provider, '')
    
    def _get_encryption_key(self) -> bytes:
        """Merr encryption key për të dhënat sensitive"""
        key = getattr(settings, 'SIGNATURE_ENCRYPTION_KEY', None)
        if not key:
            # Gjenero një key të ri (duhet ruajtur në production)
            key = Fernet.generate_key()
        
        if isinstance(key, str):
            key = key.encode()
        
        return key

    def create_signature_request(self, 
                               document: Document,
                               signers: List[SignerInfo],
                               signature_fields: List[SignatureField] = None,
                               title: str = "",
                               message: str = "",
                               callback_url: str = "") -> Dict[str, Any]:
        """
        Krijn një kërkesë për nënshkrim elektronik
        """
        if not title:
            title = f"Nënshkrim për: {document.title}"
        
        # Validate signers
        if not signers:
            raise ValidationError("Duhet të specifikoni të paktën një nënshkrues")
        
        # Create signature request based on provider
        if self.provider == SignatureProvider.DOCUSIGN:
            return self._create_docusign_request(document, signers, signature_fields, title, message, callback_url)
        elif self.provider == SignatureProvider.INTERNAL:
            return self._create_internal_request(document, signers, signature_fields, title, message)
        else:
            raise ValidationError(f"Provider {self.provider.value} nuk është implementuar ende")

    def _create_docusign_request(self,
                               document: Document,
                               signers: List[SignerInfo],
                               signature_fields: List[SignatureField],
                               title: str,
                               message: str,
                               callback_url: str) -> Dict[str, Any]:
        """
        Krijn kërkesë me DocuSign
        """
        try:
            # Prepare document content
            if document.file:
                document_content = document.file.read()
                document_name = document.file.name
            else:
                # Convert HTML content to PDF
                document_content = self._convert_html_to_pdf(document.content_html or document.content)
                document_name = f"{document.title}.pdf"
            
            # Prepare envelope
            envelope_definition = {
                "emailSubject": title,
                "emailBody": message or f"Ju lutem nënshkruani dokumentin: {document.title}",
                "documents": [
                    {
                        "documentBase64": base64.b64encode(document_content).decode(),
                        "name": document_name,
                        "fileExtension": "pdf",
                        "documentId": "1"
                    }
                ],
                "recipients": {
                    "signers": []
                },
                "status": "sent"
            }
            
            # Add signers
            for i, signer in enumerate(signers):
                signer_data = {
                    "email": signer.email,
                    "name": signer.name,
                    "recipientId": str(i + 1),
                    "routingOrder": str(signer.order)
                }
                
                # Add tabs (signature fields)
                if signature_fields:
                    signer_tabs = {"signHereTabs": []}
                    for field in signature_fields:
                        if field.signer_email == signer.email:
                            signer_tabs["signHereTabs"].append({
                                "anchorString": field.field_name or f"{{sig{i+1}}}",
                                "anchorXOffset": str(field.x_position),
                                "anchorYOffset": str(field.y_position),
                                "documentId": "1",
                                "pageNumber": str(field.page_number)
                            })
                    
                    if signer_tabs["signHereTabs"]:
                        signer_data["tabs"] = signer_tabs
                
                envelope_definition["recipients"]["signers"].append(signer_data)
            
            # Add callback URL if provided
            if callback_url:
                envelope_definition["eventNotification"] = {
                    "url": callback_url,
                    "loggingEnabled": "true",
                    "requireAcknowledgment": "true",
                    "envelopeEvents": [
                        {"envelopeEventStatusCode": "completed"},
                        {"envelopeEventStatusCode": "declined"},
                        {"envelopeEventStatusCode": "voided"}
                    ]
                }
            
            # Make API call to DocuSign
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                f"{self.base_url}/v2.1/accounts/{self._get_docusign_account_id()}/envelopes",
                headers=headers,
                json=envelope_definition,
                timeout=30
            )
            
            if response.status_code == 201:
                envelope_data = response.json()
                
                # Save signature request in database
                signature_request = self._save_signature_request(
                    document=document,
                    external_id=envelope_data['envelopeId'],
                    provider=self.provider,
                    signers=signers,
                    status=SignatureStatus.SENT,
                    metadata={
                        'envelope_id': envelope_data['envelopeId'],
                        'title': title,
                        'message': message
                    }
                )
                
                return {
                    'success': True,
                    'envelope_id': envelope_data['envelopeId'],
                    'status': envelope_data['status'],
                    'signature_request_id': signature_request.id,
                    'signing_url': self._get_docusign_signing_url(envelope_data['envelopeId'])
                }
            else:
                return {
                    'success': False,
                    'error': f"DocuSign API Error: {response.text}"
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f"Error creating DocuSign request: {str(e)}"
            }

    def _create_internal_request(self,
                               document: Document,
                               signers: List[SignerInfo],
                               signature_fields: List[SignatureField],
                               title: str,
                               message: str) -> Dict[str, Any]:
        """
        Krijn kërkesë me sistemin e brendshëm
        """
        try:
            # Generate unique signing token
            signing_token = str(uuid.uuid4())
            
            # Save signature request
            signature_request = self._save_signature_request(
                document=document,
                external_id=signing_token,
                provider=self.provider,
                signers=signers,
                status=SignatureStatus.SENT,
                metadata={
                    'title': title,
                    'message': message,
                    'signature_fields': [
                        {
                            'page': field.page_number,
                            'x': field.x_position,
                            'y': field.y_position,
                            'width': field.width,
                            'height': field.height,
                            'signer': field.signer_email,
                            'type': field.field_type
                        } for field in signature_fields or []
                    ]
                }
            )
            
            # Send signing invitations
            signing_urls = {}
            for signer in signers:
                signing_url = self._generate_signing_url(signature_request.id, signer.email, signing_token)
                signing_urls[signer.email] = signing_url
                
                # Send email invitation
                self._send_signing_invitation(
                    signer=signer,
                    document=document,
                    signing_url=signing_url,
                    title=title,
                    message=message
                )
            
            return {
                'success': True,
                'signature_request_id': signature_request.id,
                'signing_token': signing_token,
                'signing_urls': signing_urls
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Error creating internal signature request: {str(e)}"
            }

    def get_signature_status(self, signature_request_id: int) -> Dict[str, Any]:
        """
        Merr statusin e një kërkese nënshkrimi
        """
        try:
            signature_request = SignatureRequest.objects.get(id=signature_request_id)
            
            if signature_request.provider == SignatureProvider.DOCUSIGN.value:
                return self._get_docusign_status(signature_request)
            elif signature_request.provider == SignatureProvider.INTERNAL.value:
                return self._get_internal_status(signature_request)
            else:
                return {'success': False, 'error': 'Provider not supported'}
                
        except SignatureRequest.DoesNotExist:
            return {'success': False, 'error': 'Signature request not found'}

    def sign_document(self,
                     signature_request_id: int,
                     signer_email: str,
                     signature_data: str,
                     signing_token: str = "",
                     ip_address: str = "",
                     user_agent: str = "") -> Dict[str, Any]:
        """
        Nënshkruan një dokument (për sistemin e brendshëm)
        """
        try:
            signature_request = SignatureRequest.objects.get(id=signature_request_id)
            
            # Validate signing token
            if signature_request.provider == SignatureProvider.INTERNAL.value:
                expected_token = signature_request.external_id
                if signing_token != expected_token:
                    return {'success': False, 'error': 'Invalid signing token'}
            
            # Validate signer
            signer_data = next(
                (s for s in signature_request.signers_data.get('signers', []) if s['email'] == signer_email),
                None
            )
            
            if not signer_data:
                return {'success': False, 'error': 'Signer not found'}
            
            # Check if already signed
            existing_signature = DocumentSignature.objects.filter(
                document=signature_request.document,
                signer__email=signer_email
            ).first()
            
            if existing_signature:
                return {'success': False, 'error': 'Document already signed by this user'}
            
            # Create signature
            with transaction.atomic():
                # Get or create user
                signer_user = User.objects.filter(email=signer_email).first()
                
                # Generate signature hash
                signature_content = f"{signature_data}:{signer_email}:{signature_request.document.id}:{timezone.now().isoformat()}"
                signature_hash = hashlib.sha256(signature_content.encode()).hexdigest()
                
                # Create signature record
                signature = DocumentSignature.objects.create(
                    document=signature_request.document,
                    signer=signer_user,
                    signature_type='electronic',
                    signature_data=self._encrypt_signature_data(signature_data),
                    signature_hash=signature_hash,
                    is_verified=True,
                    verification_method='email',
                    ip_address=ip_address,
                    device_info={
                        'user_agent': user_agent,
                        'timestamp': timezone.now().isoformat()
                    }
                )
                
                # Update signature request
                self._update_signature_request_progress(signature_request)
                
                # Log action
                DocumentAuditLog.objects.create(
                    document=signature_request.document,
                    user=signer_user,
                    action='document_signed',
                    details=f"Document signed by {signer_email}",
                    metadata={
                        'signature_id': signature.id,
                        'signature_hash': signature_hash,
                        'ip_address': ip_address
                    },
                    ip_address=ip_address,
                    user_agent=user_agent
                )
            
            return {
                'success': True,
                'signature_id': signature.id,
                'signature_hash': signature_hash,
                'signed_at': signature.signed_at.isoformat()
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def verify_signature(self, signature_id: int) -> Dict[str, Any]:
        """
        Verifikon një nënshkrim
        """
        try:
            signature = DocumentSignature.objects.get(id=signature_id)
            
            # Decrypt signature data
            decrypted_data = self._decrypt_signature_data(signature.signature_data)
            
            # Regenerate hash
            signature_content = f"{decrypted_data}:{signature.signer.email}:{signature.document.id}:{signature.signed_at.isoformat()}"
            expected_hash = hashlib.sha256(signature_content.encode()).hexdigest()
            
            is_valid = signature.signature_hash == expected_hash
            
            return {
                'success': True,
                'is_valid': is_valid,
                'signature_id': signature.id,
                'signer': signature.signer.email if signature.signer else 'Unknown',
                'signed_at': signature.signed_at.isoformat(),
                'verification_method': signature.verification_method,
                'ip_address': signature.ip_address
            }
            
        except DocumentSignature.DoesNotExist:
            return {'success': False, 'error': 'Signature not found'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _encrypt_signature_data(self, data: str) -> str:
        """Enkripton të dhënat e nënshkrimit"""
        fernet = Fernet(self.encryption_key)
        encrypted = fernet.encrypt(data.encode())
        return base64.b64encode(encrypted).decode()

    def _decrypt_signature_data(self, encrypted_data: str) -> str:
        """Dekripton të dhënat e nënshkrimit"""
        fernet = Fernet(self.encryption_key)
        decoded = base64.b64decode(encrypted_data.encode())
        decrypted = fernet.decrypt(decoded)
        return decrypted.decode()

    def _save_signature_request(self, 
                              document: Document,
                              external_id: str,
                              provider: SignatureProvider,
                              signers: List[SignerInfo],
                              status: SignatureStatus,
                              metadata: Dict[str, Any]) -> 'SignatureRequest':
        """
        Ruaj kërkesën e nënshkrimit në bazën e të dhënave
        """
        return SignatureRequest.objects.create(
            document=document,
            external_id=external_id,
            provider=provider.value,
            status=status.value,
            signers_data={
                'signers': [
                    {
                        'name': signer.name,
                        'email': signer.email,
                        'phone': signer.phone,
                        'role': signer.role,
                        'order': signer.order,
                        'required': signer.required,
                        'user_id': signer.user_id
                    } for signer in signers
                ]
            },
            metadata=metadata,
            expires_at=timezone.now() + timedelta(days=30)  # 30 days expiry
        )

    def _convert_html_to_pdf(self, html_content: str) -> bytes:
        """
        Konverton HTML në PDF për nënshkrim
        """
        try:
            import weasyprint
            pdf = weasyprint.HTML(string=html_content).write_pdf()
            return pdf
        except ImportError:
            # Fallback - përdor library tjetër ose kthe HTML si bytes
            return html_content.encode('utf-8')

# Django Models for Signature System

class SignatureRequest(models.Model):
    """
    Kërkesa për nënshkrim elektronik
    """
    document = models.ForeignKey(
        Document, 
        on_delete=models.CASCADE,
        related_name='signature_requests'
    )
    external_id = models.CharField(
        max_length=255, 
        unique=True,
        verbose_name="ID Eksternal"
    )
    provider = models.CharField(
        max_length=20,
        choices=[(p.value, p.value.title()) for p in SignatureProvider],
        default=SignatureProvider.INTERNAL.value
    )
    
    # Request details
    title = models.CharField(max_length=255, verbose_name="Titulli")
    message = models.TextField(blank=True, verbose_name="Mesazhi")
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=[(s.value, s.value.title()) for s in SignatureStatus],
        default=SignatureStatus.DRAFT.value
    )
    
    # Signers data (stored as JSON)
    signers_data = models.JSONField(default=dict)
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        verbose_name = "Kërkesë Nënshkrimi"
        verbose_name_plural = "Kërkesa Nënshkrimesh"
        ordering = ['-created_at']

    def __str__(self):
        return f"Nënshkrim për: {self.document.title}"

    @property
    def is_expired(self) -> bool:
        """A ka skaduar kërkesa"""
        return self.expires_at and timezone.now() > self.expires_at

    @property
    def signers_count(self) -> int:
        """Numri i nënshkruesve"""
        return len(self.signers_data.get('signers', []))

    @property
    def signed_count(self) -> int:
        """Numri i nënshkruesve që kanë nënshkruar"""
        return self.document.signatures.count()

    @property
    def progress_percentage(self) -> int:
        """Përqindja e përfundimit"""
        if self.signers_count == 0:
            return 0
        return int((self.signed_count / self.signers_count) * 100)

# Service factory function
def get_signature_service(provider: SignatureProvider = None) -> SignatureService:
    """Factory function për SignatureService"""
    return SignatureService(provider)
