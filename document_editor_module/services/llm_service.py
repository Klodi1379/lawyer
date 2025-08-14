"""
LLM Service për Document Editor
Integron LLM providers dhe siguron funksionalitete të avancuara për dokumente juridike
"""

import os
import time
import json
import hashlib
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

import requests
from requests.exceptions import RequestException, Timeout
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

class LLMProvider(Enum):
    """Providerat e LLM të mbështetur"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GROQ = "groq"
    OLLAMA = "ollama"
    CUSTOM = "custom"

@dataclass
class LLMResponse:
    """Struktura për përgjigjen e LLM"""
    text: str
    confidence: Optional[float] = None
    token_usage: Optional[Dict[str, int]] = None
    processing_time: float = 0.0
    model_used: str = ""
    provider: str = ""
    error: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class DocumentContext:
    """Konteksti i dokumentit për LLM"""
    title: str
    content: str
    document_type: str
    case_type: Optional[str] = None
    jurisdiction: str = "Albania"
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class LegalLLMService:
    """
    Service kryesor për integrim me LLM për dokumente juridike
    """
    
    def __init__(self, provider: LLMProvider = None, model: str = None):
        self.provider = provider or LLMProvider(getattr(settings, 'LLM_PROVIDER', 'openai'))
        self.model = model or getattr(settings, 'LLM_MODEL', 'gpt-4')
        self.api_key = self._get_api_key()
        self.base_url = self._get_base_url()
        self.max_retries = getattr(settings, 'LLM_MAX_RETRIES', 3)
        self.timeout = getattr(settings, 'LLM_TIMEOUT', 30)
        self.rate_limit_cache_key = f"llm_rate_limit_{self.provider.value}"
        
        # Legal-specific settings
        self.jurisdiction = getattr(settings, 'LEGAL_JURISDICTION', 'Albania')
        self.legal_language = getattr(settings, 'LEGAL_LANGUAGE', 'Albanian')
        
        logger.info(f"Initialized LegalLLMService with provider: {self.provider.value}, model: {self.model}")

    def _get_api_key(self) -> str:
        """Merr API key për providerin aktual"""
        key_mapping = {
            LLMProvider.OPENAI: 'OPENAI_API_KEY',
            LLMProvider.ANTHROPIC: 'ANTHROPIC_API_KEY',
            LLMProvider.GROQ: 'GROQ_API_KEY',
            LLMProvider.OLLAMA: 'OLLAMA_API_KEY',
            LLMProvider.CUSTOM: 'CUSTOM_LLM_API_KEY'
        }
        
        env_key = key_mapping.get(self.provider)
        if not env_key:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
        
        api_key = os.getenv(env_key) or getattr(settings, env_key, None)
        if not api_key and self.provider != LLMProvider.OLLAMA:  # Ollama nuk kërkon API key
            raise ValueError(f"API key not found for {self.provider.value}. Set {env_key} environment variable.")
        
        return api_key

    def _get_base_url(self) -> str:
        """Merr base URL për providerin aktual"""
        url_mapping = {
            LLMProvider.OPENAI: 'https://api.openai.com/v1',
            LLMProvider.ANTHROPIC: 'https://api.anthropic.com/v1',
            LLMProvider.GROQ: 'https://api.groq.com/openai/v1',
            LLMProvider.OLLAMA: getattr(settings, 'OLLAMA_BASE_URL', 'http://localhost:11434'),
            LLMProvider.CUSTOM: getattr(settings, 'CUSTOM_LLM_BASE_URL', '')
        }
        return url_mapping.get(self.provider, '')

    def _check_rate_limit(self) -> bool:
        """Kontrollon rate limits"""
        rate_limit_data = cache.get(self.rate_limit_cache_key, {'count': 0, 'reset_time': timezone.now()})
        
        if timezone.now() > rate_limit_data['reset_time']:
            # Reset counter
            rate_limit_data = {'count': 0, 'reset_time': timezone.now() + timedelta(hours=1)}
        
        max_requests_per_hour = getattr(settings, 'LLM_MAX_REQUESTS_PER_HOUR', 1000)
        
        if rate_limit_data['count'] >= max_requests_per_hour:
            logger.warning(f"Rate limit exceeded for {self.provider.value}")
            return False
        
        rate_limit_data['count'] += 1
        cache.set(self.rate_limit_cache_key, rate_limit_data, 3600)  # 1 hour
        return True

    def _create_legal_system_prompt(self, context: DocumentContext = None) -> str:
        """Krijo system prompt të specializuar për dokumente juridike"""
        base_prompt = f"""You are an expert legal assistant specialized in {self.jurisdiction} law. 
You provide accurate, professional legal document assistance in {self.legal_language}.

Key guidelines:
- Always reference relevant legal articles and statutes
- Use proper legal terminology and format
- Include appropriate disclaimers when necessary
- Maintain professional legal writing style
- Consider the jurisdiction: {self.jurisdiction}
- Respond in {self.legal_language}"""

        if context:
            base_prompt += f"""

Document Context:
- Document Type: {context.document_type}
- Case Type: {context.case_type or 'General'}
- Title: {context.title}"""
            
            if context.metadata:
                base_prompt += f"\n- Additional Context: {json.dumps(context.metadata, ensure_ascii=False)}"

        return base_prompt

    def _make_request(self, messages: List[Dict], **kwargs) -> LLMResponse:
        """Bën request të përgjithshëm për LLM"""
        if not self._check_rate_limit():
            return LLMResponse(
                text="",
                error="Rate limit exceeded. Please try again later.",
                provider=self.provider.value
            )

        start_time = time.time()
        
        try:
            if self.provider == LLMProvider.OPENAI:
                return self._make_openai_request(messages, **kwargs)
            elif self.provider == LLMProvider.ANTHROPIC:
                return self._make_anthropic_request(messages, **kwargs)
            elif self.provider == LLMProvider.GROQ:
                return self._make_groq_request(messages, **kwargs)
            elif self.provider == LLMProvider.OLLAMA:
                return self._make_ollama_request(messages, **kwargs)
            else:
                return LLMResponse(
                    text="",
                    error=f"Unsupported provider: {self.provider.value}",
                    provider=self.provider.value
                )
        
        except Exception as e:
            logger.error(f"LLM request failed: {str(e)}")
            return LLMResponse(
                text="",
                error=f"Request failed: {str(e)}",
                processing_time=time.time() - start_time,
                provider=self.provider.value
            )

    def _make_openai_request(self, messages: List[Dict], **kwargs) -> LLMResponse:
        """Bën request për OpenAI API"""
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': self.model,
            'messages': messages,
            'max_tokens': kwargs.get('max_tokens', 2000),
            'temperature': kwargs.get('temperature', 0.1),
            'top_p': kwargs.get('top_p', 0.9),
            'presence_penalty': kwargs.get('presence_penalty', 0.0),
            'frequency_penalty': kwargs.get('frequency_penalty', 0.0)
        }

        start_time = time.time()
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            choice = data['choices'][0]
            
            return LLMResponse(
                text=choice['message']['content'],
                confidence=None,  # OpenAI doesn't provide confidence scores
                token_usage=data.get('usage', {}),
                processing_time=time.time() - start_time,
                model_used=self.model,
                provider=self.provider.value,
                metadata={'finish_reason': choice.get('finish_reason')}
            )
            
        except requests.exceptions.RequestException as e:
            return LLMResponse(
                text="",
                error=f"OpenAI API error: {str(e)}",
                processing_time=time.time() - start_time,
                provider=self.provider.value
            )

    def _make_anthropic_request(self, messages: List[Dict], **kwargs) -> LLMResponse:
        """Bën request për Anthropic Claude API"""
        headers = {
            'x-api-key': self.api_key,
            'Content-Type': 'application/json',
            'anthropic-version': '2023-06-01'
        }
        
        # Convert messages format for Anthropic
        system_message = None
        anthropic_messages = []
        
        for msg in messages:
            if msg['role'] == 'system':
                system_message = msg['content']
            else:
                anthropic_messages.append(msg)
        
        payload = {
            'model': self.model,
            'max_tokens': kwargs.get('max_tokens', 2000),
            'temperature': kwargs.get('temperature', 0.1),
            'messages': anthropic_messages
        }
        
        if system_message:
            payload['system'] = system_message

        start_time = time.time()
        
        try:
            response = requests.post(
                f"{self.base_url}/messages",
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            return LLMResponse(
                text=data['content'][0]['text'],
                token_usage=data.get('usage', {}),
                processing_time=time.time() - start_time,
                model_used=self.model,
                provider=self.provider.value,
                metadata={'stop_reason': data.get('stop_reason')}
            )
            
        except requests.exceptions.RequestException as e:
            return LLMResponse(
                text="",
                error=f"Anthropic API error: {str(e)}",
                processing_time=time.time() - start_time,
                provider=self.provider.value
            )

    def _make_groq_request(self, messages: List[Dict], **kwargs) -> LLMResponse:
        """Bën request për Groq API (përdor OpenAI-compatible format)"""
        return self._make_openai_request(messages, **kwargs)  # Groq përdor format të ngjashëm

    def _make_ollama_request(self, messages: List[Dict], **kwargs) -> LLMResponse:
        """Bën request për Ollama (local/self-hosted)"""
        # Ollama API format
        prompt = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
        
        payload = {
            'model': self.model,
            'prompt': prompt,
            'stream': False,
            'options': {
                'temperature': kwargs.get('temperature', 0.1),
                'top_p': kwargs.get('top_p', 0.9),
                'num_predict': kwargs.get('max_tokens', 2000)
            }
        }

        start_time = time.time()
        
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            return LLMResponse(
                text=data.get('response', ''),
                processing_time=time.time() - start_time,
                model_used=self.model,
                provider=self.provider.value,
                metadata={
                    'eval_count': data.get('eval_count'),
                    'eval_duration': data.get('eval_duration')
                }
            )
            
        except requests.exceptions.RequestException as e:
            return LLMResponse(
                text="",
                error=f"Ollama API error: {str(e)}",
                processing_time=time.time() - start_time,
                provider=self.provider.value
            )

    def generate_document(self, 
                         document_type: str, 
                         context: DocumentContext, 
                         template_vars: Dict[str, Any] = None,
                         **kwargs) -> LLMResponse:
        """
        Gjeneron një dokument të ri bazuar në tipin dhe kontekstin e dhënë
        """
        template_vars = template_vars or {}
        
        system_prompt = self._create_legal_system_prompt(context)
        user_prompt = f"""Generate a {document_type} document in {self.legal_language} with the following specifications:

Document Type: {document_type}
Case Type: {context.case_type or 'General'}
Title: {context.title}

Template Variables: {json.dumps(template_vars, ensure_ascii=False, indent=2)}

Requirements:
- Use proper legal format and structure
- Include relevant legal references for {self.jurisdiction}
- Use formal legal language
- Include necessary disclaimers
- Structure the document with appropriate sections and numbering

Context: {context.content[:1000] if context.content else 'No additional context provided'}

Please generate a complete, professional legal document."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        return self._make_request(messages, **kwargs)

    def review_document(self, context: DocumentContext, focus_areas: List[str] = None, **kwargs) -> LLMResponse:
        """
        Rishikon një dokument dhe jep sugjerime për përmirësim
        """
        focus_areas = focus_areas or ['legal_accuracy', 'format', 'language', 'completeness']
        
        system_prompt = self._create_legal_system_prompt(context)
        user_prompt = f"""Please review the following {context.document_type} document and provide detailed feedback:

Document Title: {context.title}
Document Type: {context.document_type}
Case Type: {context.case_type or 'General'}

Focus Areas for Review: {', '.join(focus_areas)}

Document Content:
{context.content}

Please provide:
1. Overall assessment of the document
2. Specific issues or errors found
3. Suggestions for improvement
4. Legal accuracy check (references to {self.jurisdiction} law)
5. Format and structure evaluation
6. Language and terminology review

Format your response with clear sections and actionable recommendations."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        return self._make_request(messages, **kwargs)

    def suggest_improvements(self, context: DocumentContext, specific_section: str = None, **kwargs) -> LLMResponse:
        """
        Sugjeron përmirësime për një dokument ose seksion specifik
        """
        system_prompt = self._create_legal_system_prompt(context)
        
        if specific_section:
            user_prompt = f"""Please provide specific improvement suggestions for the following section of a {context.document_type}:

Section to improve: {specific_section}

Full document context:
Title: {context.title}
Type: {context.document_type}
Content: {context.content[:500]}...

Please provide:
1. Specific improvements for the mentioned section
2. Alternative phrasing suggestions
3. Legal enhancements
4. Formatting improvements"""
        else:
            user_prompt = f"""Please provide comprehensive improvement suggestions for this {context.document_type}:

Title: {context.title}
Content: {context.content}

Please provide:
1. Structure improvements
2. Content enhancements
3. Legal strengthening suggestions
4. Language and clarity improvements
5. Missing elements that should be added"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        return self._make_request(messages, **kwargs)

    def translate_document(self, context: DocumentContext, target_language: str, **kwargs) -> LLMResponse:
        """
        Përktheun një dokument juridik në gjuhën e caktuar
        """
        system_prompt = f"""You are an expert legal translator specializing in {self.jurisdiction} law.
Translate legal documents accurately while maintaining legal terminology and format.
Preserve the legal meaning and structure of the document."""
        
        user_prompt = f"""Please translate the following {context.document_type} from {self.legal_language} to {target_language}:

Document Title: {context.title}
Document Type: {context.document_type}

Content to translate:
{context.content}

Requirements:
- Maintain legal accuracy and terminology
- Preserve document structure and formatting
- Use appropriate legal language in {target_language}
- Keep legal references and citations intact
- Ensure the translation is suitable for legal use"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        return self._make_request(messages, **kwargs)

    def summarize_document(self, context: DocumentContext, summary_type: str = 'executive', **kwargs) -> LLMResponse:
        """
        Krijn një përmbledhje të dokumentit
        """
        system_prompt = self._create_legal_system_prompt(context)
        
        summary_types = {
            'executive': 'executive summary for senior management',
            'legal': 'legal summary focusing on key legal points',
            'brief': 'brief overview highlighting main points',
            'detailed': 'detailed summary with all important elements'
        }
        
        summary_description = summary_types.get(summary_type, 'general summary')
        
        user_prompt = f"""Please create a {summary_description} of the following {context.document_type}:

Document Title: {context.title}
Document Type: {context.document_type}
Case Type: {context.case_type or 'General'}

Document Content:
{context.content}

Please provide:
1. Key points and main arguments
2. Important legal references
3. Critical dates or deadlines (if any)
4. Recommended actions (if applicable)
5. Potential risks or considerations

Keep the summary professional and suitable for {summary_type} use."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        return self._make_request(messages, **kwargs)

    def analyze_legal_compliance(self, context: DocumentContext, regulations: List[str] = None, **kwargs) -> LLMResponse:
        """
        Analizon përputhshmërinë ligjore të një dokumenti
        """
        regulations = regulations or []
        
        system_prompt = self._create_legal_system_prompt(context)
        user_prompt = f"""Please analyze the legal compliance of the following {context.document_type}:

Document Title: {context.title}
Document Type: {context.document_type}
Jurisdiction: {self.jurisdiction}

Specific regulations to check: {', '.join(regulations) if regulations else 'General legal compliance'}

Document Content:
{context.content}

Please provide:
1. Compliance assessment with {self.jurisdiction} law
2. Potential legal issues or risks
3. Missing required elements
4. Recommendations for ensuring compliance
5. References to relevant legal articles or statutes
6. Risk level assessment (Low/Medium/High)"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        return self._make_request(messages, **kwargs)

    def extract_key_information(self, context: DocumentContext, info_types: List[str] = None, **kwargs) -> LLMResponse:
        """
        Ekstrakton informacion kryesor nga një dokument
        """
        info_types = info_types or ['parties', 'dates', 'obligations', 'amounts', 'deadlines']
        
        system_prompt = self._create_legal_system_prompt(context)
        user_prompt = f"""Please extract key information from the following {context.document_type}:

Document Title: {context.title}
Document Content: {context.content}

Extract the following types of information: {', '.join(info_types)}

Please provide the information in a structured format:
- Parties involved
- Important dates and deadlines
- Financial amounts or obligations
- Key terms and conditions
- Legal references
- Action items or requirements

Format the response as a structured list or table for easy reference."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        return self._make_request(messages, **kwargs)

    def get_embeddings(self, text: str) -> Dict[str, Any]:
        """
        Merr embeddings për tekst (për search dhe similarity)
        """
        if self.provider == LLMProvider.OPENAI:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'model': 'text-embedding-ada-002',
                'input': text[:8000]  # Limit text length
            }
            
            try:
                response = requests.post(
                    f"{self.base_url}/embeddings",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                data = response.json()
                return {
                    'embeddings': data['data'][0]['embedding'],
                    'token_usage': data.get('usage', {}),
                    'model': 'text-embedding-ada-002'
                }
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Embeddings request failed: {str(e)}")
                return {'error': str(e)}
        
        else:
            return {'error': f'Embeddings not supported for provider: {self.provider.value}'}

    def cache_response(self, request_hash: str, response: LLMResponse, ttl: int = 3600):
        """
        Cache-on një përgjigje LLM për optimizim
        """
        cache_key = f"llm_response_{request_hash}"
        cache.set(cache_key, {
            'text': response.text,
            'confidence': response.confidence,
            'token_usage': response.token_usage,
            'processing_time': response.processing_time,
            'model_used': response.model_used,
            'provider': response.provider,
            'metadata': response.metadata,
            'timestamp': timezone.now().isoformat()
        }, ttl)

    def get_cached_response(self, request_hash: str) -> Optional[LLMResponse]:
        """
        Merr një përgjigje të cache-uar
        """
        cache_key = f"llm_response_{request_hash}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return LLMResponse(
                text=cached_data['text'],
                confidence=cached_data.get('confidence'),
                token_usage=cached_data.get('token_usage'),
                processing_time=cached_data.get('processing_time', 0.0),
                model_used=cached_data.get('model_used', ''),
                provider=cached_data.get('provider', ''),
                metadata=cached_data.get('metadata', {})
            )
        
        return None

    def create_request_hash(self, prompt: str, **kwargs) -> str:
        """
        Krijn një hash për request për caching
        """
        request_data = {
            'prompt': prompt,
            'model': self.model,
            'provider': self.provider.value,
            **kwargs
        }
        
        request_str = json.dumps(request_data, sort_keys=True)
        return hashlib.md5(request_str.encode()).hexdigest()

# Factory function për lehtësi përdorimi
def get_llm_service(provider: str = None, model: str = None) -> LegalLLMService:
    """
    Factory function për të krijuar LegalLLMService instance
    """
    if provider:
        provider_enum = LLMProvider(provider.lower())
    else:
        provider_enum = None
        
    return LegalLLMService(provider=provider_enum, model=model)
