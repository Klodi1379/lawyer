import os
import requests
import logging
from typing import Dict, Any, Optional, List
from requests.exceptions import RequestException
from django.conf import settings
from .models import AuditLog

logger = logging.getLogger(__name__)

class LLMService:
    """
    LLM Service wrapper for legal assistant functionality.
    Supports OpenAI, Anthropic, and other providers via API.
    """
    
    def __init__(self, api_key: str = None, endpoint: str = None, model: str = None):
        self.api_key = api_key or getattr(settings, 'LLM_API_KEY', os.getenv('LLM_API_KEY'))
        self.endpoint = endpoint or getattr(settings, 'LLM_API_ENDPOINT', 
                                          'https://api.openai.com/v1/chat/completions')
        self.model = model or getattr(settings, 'LLM_MODEL', 'gpt-4o-mini')
        
        if not self.api_key:
            logger.warning("LLM API key not configured. LLM functionality will be disabled.")

    def call(self, prompt: str, system_message: str = None, max_tokens: int = 1024, 
             temperature: float = 0.0, user=None) -> Dict[str, Any]:
        """
        Make a call to the LLM API.
        
        Args:
            prompt: The user prompt
            system_message: System message to set context
            max_tokens: Maximum tokens to generate
            temperature: Temperature for randomness (0.0 = deterministic)
            user: Django user object for audit logging
            
        Returns:
            Dict containing response text or error
        """
        if not self.api_key:
            return {'error': 'LLM API key not configured'}
        
        # Default system message for legal assistant
        if not system_message:
            system_message = (
                "You are a legal assistant for Albania. Always include references to statutes "
                "with article numbers and dates. Add disclaimers that this is informational "
                "only and not legal advice."
            )
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': system_message},
                {'role': 'user', 'content': prompt}
            ],
            'max_tokens': max_tokens,
            'temperature': temperature
        }
        
        try:
            response = requests.post(self.endpoint, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            response_text = result['choices'][0]['message']['content']
            
            # Log the API call for audit purposes
            if user:
                AuditLog.objects.create(
                    user=user,
                    action='llm_query',
                    target_type='LLMService',
                    target_id=self.model,
                    metadata={
                        'prompt_length': len(prompt),
                        'response_length': len(response_text),
                        'model': self.model,
                        'temperature': temperature
                    }
                )
            
            return {'text': response_text}
            
        except RequestException as e:
            logger.error(f"LLM API request failed: {str(e)}")
            return {'error': f'API request failed: {str(e)}'}
        except KeyError as e:
            logger.error(f"Unexpected API response format: {str(e)}")
            return {'error': 'Unexpected API response format'}
        except Exception as e:
            logger.error(f"Unexpected error in LLM call: {str(e)}")
            return {'error': f'Unexpected error: {str(e)}'}

    def get_embeddings(self, text: str) -> List[float]:
        """
        Get text embeddings for similarity search.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding
        """
        if not self.api_key:
            return []
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': 'text-embedding-ada-002',
            'input': text
        }
        
        try:
            response = requests.post(
                'https://api.openai.com/v1/embeddings', 
                headers=headers, 
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            return result['data'][0]['embedding']
            
        except RequestException as e:
            logger.error(f"Embeddings API request failed: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in embeddings call: {str(e)}")
            return []

    def create_finetune_job(self, training_file_id: str, hyperparams: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create a fine-tuning job.
        
        Args:
            training_file_id: ID of uploaded training file
            hyperparams: Hyperparameters for fine-tuning
            
        Returns:
            Dict containing job information or error
        """
        if not self.api_key:
            return {'error': 'LLM API key not configured'}
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'training_file': training_file_id,
            'model': self.model
        }
        
        if hyperparams:
            payload.update(hyperparams)
        
        try:
            response = requests.post(
                'https://api.openai.com/v1/fine_tuning/jobs',
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
            
        except RequestException as e:
            logger.error(f"Fine-tuning API request failed: {str(e)}")
            return {'error': f'Fine-tuning request failed: {str(e)}'}
        except Exception as e:
            logger.error(f"Unexpected error in fine-tuning call: {str(e)}")
            return {'error': f'Unexpected error: {str(e)}'}

    def generate_legal_draft(self, case_title: str, facts: str, case_type: str, 
                           jurisdiction: str = "Albania", user=None) -> Dict[str, Any]:
        """
        Generate a legal document draft.
        
        Args:
            case_title: Title of the case
            facts: Case facts
            case_type: Type of case (civil, criminal, etc.)
            jurisdiction: Legal jurisdiction
            user: Django user for audit logging
            
        Returns:
            Dict containing generated draft or error
        """
        system_message = f"""
        You are a legal assistant specialized in {jurisdiction} law. 
        Generate professional legal document drafts with proper citations to statutes.
        Always include:
        1. Proper legal formatting
        2. References to relevant articles and laws
        3. Clear disclaimer about informational nature
        4. Professional legal language appropriate for {jurisdiction}
        """
        
        prompt = f"""
        Generate a draft legal document for:
        Case Title: {case_title}
        Case Type: {case_type}
        Facts: {facts}
        
        Please include:
        - Appropriate legal structure for {case_type} cases
        - Relevant statutory references
        - Professional formatting
        - Disclaimer about verification needed before filing
        """
        
        return self.call(prompt, system_message, max_tokens=2000, temperature=0.1, user=user)

    def analyze_legal_document(self, document_text: str, user=None) -> Dict[str, Any]:
        """
        Analyze a legal document and provide insights.
        
        Args:
            document_text: Text of the document to analyze
            user: Django user for audit logging
            
        Returns:
            Dict containing analysis or error
        """
        system_message = """
        You are a legal document analyzer. Provide concise analysis of legal documents including:
        1. Document type identification
        2. Key legal issues
        3. Potential concerns or missing elements
        4. Relevant legal references
        Always include disclaimers about professional review requirements.
        """
        
        prompt = f"""
        Please analyze this legal document:
        
        {document_text[:3000]}  # Limit text length
        
        Provide:
        - Document type and purpose
        - Key legal elements
        - Potential issues or gaps
        - Relevant legal considerations
        """
        
        return self.call(prompt, system_message, max_tokens=1500, temperature=0.0, user=user)

# Global instance for easy access
llm_service = LLMService()
