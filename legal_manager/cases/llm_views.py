from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.utils.decorators import method_decorator
from django.core.files.base import ContentFile
from django.conf import settings
import json
import logging
from datetime import datetime, timedelta
from .models import CaseDocument, Case
from .llm_service import LLMService

logger = logging.getLogger(__name__)

class DocumentEditorView(LoginRequiredMixin, TemplateView):
    """
    AI-powered document editor view
    """
    template_name = 'llm/document_editor.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get document if editing existing one
        document_id = self.kwargs.get('document_id')
        if document_id:
            try:
                document = get_object_or_404(CaseDocument, id=document_id)
                if self.request.user.role == 'client' and document.case.client.user != self.request.user:
                    raise PermissionError("Access denied")
                context['document'] = document
                context['document_content'] = document.content if hasattr(document, 'content') else ''
            except CaseDocument.DoesNotExist:
                context['document'] = None
        
        # Add recent documents for reference
        recent_docs = CaseDocument.objects.filter(
            uploaded_by=self.request.user
        ).order_by('-created_at')[:5]
        context['recent_documents'] = recent_docs
        
        # Add available templates
        context['document_templates'] = [
            {
                'id': 'contract',
                'name': 'Service Contract',
                'description': 'Standard service agreement template',
                'icon': 'bi-file-earmark-text'
            },
            {
                'id': 'nda',
                'name': 'NDA Agreement',
                'description': 'Non-disclosure agreement',
                'icon': 'bi-file-earmark-lock'
            },
            {
                'id': 'demand-letter',
                'name': 'Demand Letter',
                'description': 'Formal demand letter template',
                'icon': 'bi-file-earmark-arrow-up'
            },
            {
                'id': 'motion',
                'name': 'Court Motion',
                'description': 'Legal motion template',
                'icon': 'bi-file-earmark-ruled'
            },
            {
                'id': 'complaint',
                'name': 'Complaint',
                'description': 'Legal complaint template',
                'icon': 'bi-file-earmark-plus'
            },
            {
                'id': 'memo',
                'name': 'Legal Memo',
                'description': 'Legal memorandum template',
                'icon': 'bi-file-earmark-text'
            }
        ]
        
        return context

@login_required
@require_http_methods(["POST"])
def llm_chat_api(request):
    """
    API endpoint for AI chat functionality
    """
    try:
        data = json.loads(request.body)
        message = data.get('message', '')
        context = data.get('context', '')
        document_type = data.get('document_type', 'general')
        
        if not message:
            return JsonResponse({'error': 'Message is required'}, status=400)
        
        # Initialize LLM service
        llm_service = LLMService()
        
        # Create context-aware prompt
        system_prompt = f"""You are a legal assistant specialized in Albanian law. 
        You are helping to create a {document_type} document. 
        Current document context: {context[:500] if context else 'No content yet'}
        
        Provide helpful, accurate legal guidance while noting that this is informational only 
        and not legal advice. Always reference relevant Albanian legal provisions when applicable."""
        
        # Call LLM
        response = llm_service.call(
            prompt=f"{system_prompt}\n\nUser question: {message}",
            max_tokens=1000,
            temperature=0.3
        )
        
        # Log the interaction for audit purposes
        logger.info(f"LLM Chat - User: {request.user.username}, Message: {message[:100]}...")
        
        return JsonResponse({
            'response': response.get('text', 'I apologize, but I encountered an error processing your request.'),
            'timestamp': datetime.now().isoformat()
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"LLM Chat API Error: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)

@login_required
@require_http_methods(["POST"])
def document_save_api(request):
    """
    API endpoint for saving documents
    """
    try:
        data = json.loads(request.body)
        title = data.get('title', 'Untitled Document')
        content = data.get('content', '')
        document_type = data.get('document_type', 'general')
        is_auto_save = data.get('is_auto_save', False)
        document_id = data.get('document_id')
        
        # Create or update document
        if document_id:
            try:
                document = get_object_or_404(CaseDocument, id=document_id)
                if request.user.role == 'client' and document.case.client.user != request.user:
                    return JsonResponse({'error': 'Access denied'}, status=403)
            except CaseDocument.DoesNotExist:
                return JsonResponse({'error': 'Document not found'}, status=404)
        else:
            # Create new document - need to associate with a case or create as standalone
            # For now, we'll create a temporary case if none specified
            case_id = data.get('case_id')
            if case_id:
                case = get_object_or_404(Case, id=case_id)
            else:
                # Create a default case for standalone documents
                from .models import Client
                default_client, created = Client.objects.get_or_create(
                    full_name=f"{request.user.get_full_name()} - Personal Documents",
                    defaults={'email': request.user.email}
                )
                case, created = Case.objects.get_or_create(
                    title="Personal Documents",
                    client=default_client,
                    assigned_to=request.user,
                    defaults={
                        'description': 'Container for personal legal documents',
                        'case_type': 'general'
                    }
                )
            
            document = CaseDocument.objects.create(
                case=case,
                uploaded_by=request.user,
                title=title,
                doc_type=document_type
            )
        
        # Save content as metadata for now (in production, consider separate content field)
        if not hasattr(document, 'content'):
            document.metadata = document.metadata or {}
            document.metadata['content'] = content
            document.metadata['editor_data'] = data.get('editor_data', {})
            document.metadata['last_saved'] = datetime.now().isoformat()
            document.metadata['save_type'] = 'auto' if is_auto_save else 'manual'
        
        document.title = title
        document.save()
        
        # Log the save operation
        logger.info(f"Document saved - User: {request.user.username}, Doc: {document.id}, Auto: {is_auto_save}")
        
        return JsonResponse({
            'id': document.id,
            'title': document.title,
            'saved_at': document.updated_at.isoformat(),
            'version': {
                'id': document.id,
                'number': document.version,
                'created_at': document.updated_at.strftime('%Y-%m-%d %H:%M'),
                'type': 'auto' if is_auto_save else 'manual'
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Document Save API Error: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)

@login_required
@require_http_methods(["POST"])
def document_export_api(request, document_id):
    """
    API endpoint for exporting documents
    """
    try:
        document = get_object_or_404(CaseDocument, id=document_id)
        if request.user.role == 'client' and document.case.client.user != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        data = json.loads(request.body)
        export_format = data.get('format', 'pdf').lower()
        
        if export_format not in ['pdf', 'docx', 'html', 'txt']:
            return JsonResponse({'error': 'Unsupported format'}, status=400)
        
        # Get document content
        content = document.metadata.get('content', '') if document.metadata else ''
        
        # For now, return content as-is (in production, implement proper format conversion)
        if export_format == 'html':
            response_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>{document.title}</title>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
                    h1, h2, h3 {{ color: #333; }}
                </style>
            </head>
            <body>
                <h1>{document.title}</h1>
                <p><strong>Created:</strong> {document.created_at.strftime('%Y-%m-%d %H:%M')}</p>
                <p><strong>Case:</strong> {document.case.title}</p>
                <hr>
                <div>{content}</div>
            </body>
            </html>
            """
            response = HttpResponse(response_content, content_type='text/html')
        elif export_format == 'txt':
            # Strip HTML for plain text
            import re
            plain_content = re.sub('<[^<]+?>', '', content)
            response_content = f"""
{document.title}

Created: {document.created_at.strftime('%Y-%m-%d %H:%M')}
Case: {document.case.title}

{plain_content}
            """
            response = HttpResponse(response_content, content_type='text/plain')
        else:
            # For PDF and DOCX, return HTML for now (implement proper conversion later)
            response_content = content
            response = HttpResponse(response_content, content_type='application/octet-stream')
        
        response['Content-Disposition'] = f'attachment; filename="{document.title}.{export_format}"'
        
        # Log the export
        logger.info(f"Document exported - User: {request.user.username}, Doc: {document.id}, Format: {export_format}")
        
        return response
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Document Export API Error: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)

@login_required
@require_http_methods(["GET"])
def document_templates_api(request):
    """
    API endpoint for getting document templates
    """
    try:
        template_type = request.GET.get('type', 'contract')
        
        # Initialize LLM service
        llm_service = LLMService()
        
        # Define template prompts
        template_prompts = {
            'contract': """Generate a comprehensive service contract template in Albanian, including:
            - Parties identification
            - Service description
            - Payment terms
            - Duration and termination
            - Liability and warranties
            - Dispute resolution
            Make it professional and legally compliant with Albanian law.""",
            
            'nda': """Generate a non-disclosure agreement template in Albanian, including:
            - Definition of confidential information
            - Obligations of receiving party
            - Exceptions to confidentiality
            - Duration of agreement
            - Remedies for breach
            Ensure compliance with Albanian privacy laws.""",
            
            'demand-letter': """Generate a formal demand letter template in Albanian, including:
            - Sender and recipient information
            - Statement of facts
            - Legal basis for demand
            - Specific demand and deadline
            - Consequences of non-compliance
            Make it professional yet firm.""",
            
            'motion': """Generate a court motion template for Albanian courts, including:
            - Court and case information
            - Parties representation
            - Statement of facts
            - Legal arguments
            - Prayer for relief
            - Signature block
            Follow Albanian court procedures.""",
            
            'complaint': """Generate a legal complaint template for Albanian courts, including:
            - Jurisdiction and venue
            - Parties identification
            - Statement of facts
            - Causes of action
            - Damages claimed
            - Prayer for relief
            Follow Albanian civil procedure rules.""",
            
            'memo': """Generate a legal memorandum template, including:
            - Header with case information
            - Executive summary
            - Statement of facts
            - Legal analysis
            - Conclusion and recommendations
            Make it clear and professional."""
        }
        
        prompt = template_prompts.get(template_type, template_prompts['contract'])
        
        # Generate template content
        response = llm_service.call(
            prompt=prompt,
            max_tokens=2000,
            temperature=0.2
        )
        
        # Log the template generation
        logger.info(f"Template generated - User: {request.user.username}, Type: {template_type}")
        
        return JsonResponse({
            'template': response.get('text', 'Error generating template'),
            'type': template_type,
            'generated_at': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Template API Error: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)

@login_required
@require_http_methods(["GET"])
def quick_stats_api(request):
    """
    API endpoint for sidebar quick stats
    """
    try:
        user = request.user
        
        # Calculate stats based on user role
        if user.role == 'client':
            # Client sees only their cases and documents
            from django.db.models import Q
            client_cases = Case.objects.filter(client__email=user.email)
            stats = {
                'total_cases': client_cases.count(),
                'open_cases': client_cases.filter(status='open').count(),
                'closed_cases': client_cases.filter(status='closed').count(),
                'total_documents': CaseDocument.objects.filter(case__in=client_cases).count(),
                'draft_documents': 0,  # Implement draft status
                'upcoming_deadlines': 0  # Implement deadline checking
            }
        else:
            # Lawyers and admins see assigned/all cases
            if user.role == 'admin':
                user_cases = Case.objects.all()
                user_documents = CaseDocument.objects.all()
            else:
                user_cases = Case.objects.filter(assigned_to=user)
                user_documents = CaseDocument.objects.filter(uploaded_by=user)
            
            stats = {
                'total_cases': user_cases.count(),
                'open_cases': user_cases.filter(status='open').count(),
                'closed_cases': user_cases.filter(status='closed').count(),
                'total_documents': user_documents.count(),
                'draft_documents': 0,  # Implement draft status
                'upcoming_deadlines': 0  # Implement deadline checking
            }
        
        # Add time-based stats
        from django.utils import timezone
        week_ago = timezone.now() - timedelta(days=7)
        month_ago = timezone.now() - timedelta(days=30)
        
        stats.update({
            'cases_this_week': user_cases.filter(created_at__gte=week_ago).count() if 'user_cases' in locals() else 0,
            'docs_this_week': user_documents.filter(created_at__gte=week_ago).count() if 'user_documents' in locals() else 0,
            'cases_this_month': user_cases.filter(created_at__gte=month_ago).count() if 'user_cases' in locals() else 0
        })
        
        return JsonResponse(stats)
        
    except Exception as e:
        logger.error(f"Quick Stats API Error: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)

@login_required
@require_http_methods(["POST"])
def llm_document_analysis_api(request):
    """
    API endpoint for AI document analysis
    """
    try:
        data = json.loads(request.body)
        document_content = data.get('content', '')
        analysis_type = data.get('analysis_type', 'general')
        
        if not document_content:
            return JsonResponse({'error': 'Document content is required'}, status=400)
        
        # Initialize LLM service
        llm_service = LLMService()
        
        # Define analysis prompts
        analysis_prompts = {
            'compliance': f"""Analyze this legal document for compliance with Albanian law:

{document_content}

Please provide:
1. Compliance score (1-100)
2. Identified issues or risks
3. Missing required clauses
4. Recommendations for improvement
5. Relevant Albanian legal references

Format your response as a structured analysis.""",
            
            'risk_assessment': f"""Perform a risk assessment of this legal document:

{document_content}

Please identify:
1. High-risk clauses or terms
2. Potential legal vulnerabilities  
3. Enforceability concerns
4. Recommended risk mitigation strategies
5. Overall risk rating (Low/Medium/High)""",
            
            'clause_suggestions': f"""Review this document and suggest additional clauses:

{document_content}

Please suggest:
1. Essential missing clauses
2. Protective provisions to add
3. Standard industry clauses
4. Compliance-related clauses
5. Specific wording recommendations""",
            
            'general': f"""Provide a comprehensive analysis of this legal document:

{document_content}

Please analyze:
1. Document structure and completeness
2. Legal language clarity
3. Potential issues or improvements
4. Compliance considerations
5. Overall assessment and recommendations"""
        }
        
        prompt = analysis_prompts.get(analysis_type, analysis_prompts['general'])
        
        # Get AI analysis
        response = llm_service.call(
            prompt=prompt,
            max_tokens=1500,
            temperature=0.2
        )
        
        # Log the analysis
        logger.info(f"Document analysis - User: {request.user.username}, Type: {analysis_type}")
        
        return JsonResponse({
            'analysis': response.get('text', 'Error performing analysis'),
            'analysis_type': analysis_type,
            'analyzed_at': datetime.now().isoformat(),
            'content_length': len(document_content)
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Document Analysis API Error: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)
