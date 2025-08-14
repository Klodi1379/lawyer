"""
Document Automation System - Sistem i avancuar për automatizim të dokumenteve juridike
Përdor AI për gjenerim automatik, template suggestion, dhe document intelligence
"""

import json
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging

from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings

from ..services.llm_service import LegalLLMService, DocumentContext, LLMResponse
from ..models.document_models import Document, DocumentTemplate, DocumentType
from .template_engine import LegalTemplateEngine, TemplateContext, TemplateVariable

User = get_user_model()
logger = logging.getLogger(__name__)

class AutomationType(Enum):
    """Llojet e automatizimit"""
    TEMPLATE_SUGGESTION = "template_suggestion"
    CONTENT_GENERATION = "content_generation"
    DATA_EXTRACTION = "data_extraction"
    DOCUMENT_CLASSIFICATION = "document_classification"
    CLAUSE_SUGGESTION = "clause_suggestion"
    COMPLIANCE_CHECK = "compliance_check"
    SMART_MERGE = "smart_merge"

class AutomationTrigger(Enum):
    """Triggerët për automatizim"""
    DOCUMENT_CREATION = "document_creation"
    CONTENT_CHANGE = "content_change"
    STATUS_CHANGE = "status_change"
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    API_CALL = "api_call"

@dataclass
class AutomationRule:
    """Rregull automatizimi"""
    name: str
    type: AutomationType
    trigger: AutomationTrigger
    conditions: Dict[str, Any]
    actions: List[Dict[str, Any]]
    enabled: bool = True
    priority: int = 1

@dataclass
class DocumentSuggestion:
    """Sugjerim për dokument"""
    type: str
    confidence: float
    title: str
    description: str
    template_id: Optional[int] = None
    variables: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ClauseSuggestion:
    """Sugjerim për klauzolë juridike"""
    clause_type: str
    content: str
    position: int
    confidence: float
    reasoning: str
    legal_references: List[str] = field(default_factory=list)

class DocumentAutomationEngine:
    """
    Engine kryesor për automatizimin e dokumenteve juridike
    """
    
    def __init__(self):
        self.llm_service = LegalLLMService()
        self.template_engine = LegalTemplateEngine()
        self.automation_rules = []
        
        # Load automation rules from settings or database
        self._load_automation_rules()
        
        # Legal knowledge base
        self.legal_patterns = self._load_legal_patterns()
        self.standard_clauses = self._load_standard_clauses()
        
    def _load_automation_rules(self):
        """Ngarkon rregullat e automatizimit"""
        # Implemento ngarkimin e rregullave nga konfigurimi
        default_rules = [
            AutomationRule(
                name="Contract Template Suggestion",
                type=AutomationType.TEMPLATE_SUGGESTION,
                trigger=AutomationTrigger.DOCUMENT_CREATION,
                conditions={"document_type": "contract"},
                actions=[{"action": "suggest_templates", "parameters": {"limit": 5}}]
            ),
            AutomationRule(
                name="Legal Compliance Check",
                type=AutomationType.COMPLIANCE_CHECK,
                trigger=AutomationTrigger.CONTENT_CHANGE,
                conditions={"content_length_min": 100},
                actions=[{"action": "check_compliance", "parameters": {"regulations": ["general"]}}]
            )
        ]
        
        self.automation_rules = default_rules
        
    def _load_legal_patterns(self) -> Dict[str, List[str]]:
        """Ngarkon pattern-at juridikë"""
        return {
            "contract_elements": [
                r"palët\s+(?:kontraktuese|nënshkruese)",
                r"objekti\s+i\s+kontratës",
                r"afatet\s+dhe\s+kohëzgjatja",
                r"obligimet\s+e\s+palëve"
            ],
            "legal_dates": [
                r"\d{1,2}[\.\/\-]\d{1,2}[\.\/\-]\d{4}",
                r"më\s+\d{1,2}\s+\w+\s+\d{4}"
            ],
            "monetary_amounts": [
                r"\d+(?:\.\d+)?\s*(?:EUR|euro|lek|ALL)",
                r"(?:EUR|euro|lek|ALL)\s*\d+(?:\.\d+)?"
            ]
        }
    
    def _load_standard_clauses(self) -> Dict[str, Dict[str, str]]:
        """Ngarkon klauzola standarde juridike"""
        return {
            "contract": {
                "force_majeure": "Asnjëra nga palët nuk do të konsiderohet përgjegjëse për moszbatimin e detyrimeve të saj kontraktuale në rast të forcës madhore...",
                "confidentiality": "Palët angazhohen të mbajnë konfidenciale të gjitha informacionet që marrin gjatë zbatimit të këtij kontrati...",
                "jurisdiction": "Për të gjitha mosmarrëveshjet që mund të lindin nga ky kontrakt, palët i nënshtrohen juridiksionit të gjykatave të Republikës së Shqipërisë..."
            },
            "complaint": {
                "legal_basis": "Bazuar në dispozitat e nenit... të Kodit Civil të Republikës së Shqipërisë...",
                "request": "Për sa më sipër, lutem respektivisht që gjykata...",
                "evidence": "Në mbështetje të pretendimit, bashkëlidhim në padi..."
            }
        }

    def suggest_document_template(self, 
                                case_info: Dict[str, Any],
                                user_preferences: Dict[str, Any] = None) -> List[DocumentSuggestion]:
        """
        Sugjeron template-t më të përshtatshme për një rast
        """
        user_preferences = user_preferences or {}
        
        # Analizon informacionin e rastit
        context = DocumentContext(
            title=case_info.get('title', ''),
            content=case_info.get('description', ''),
            document_type='general',
            case_type=case_info.get('case_type', 'civil'),
            metadata=case_info
        )
        
        # Përdor AI për të analizuar dhe sugjeruar
        ai_suggestions = self._get_ai_template_suggestions(context)
        
        # Përdor rule-based matching
        rule_based_suggestions = self._get_rule_based_suggestions(case_info)
        
        # Kombino dhe ranko sugjerimet
        all_suggestions = ai_suggestions + rule_based_suggestions
        ranked_suggestions = self._rank_suggestions(all_suggestions, user_preferences)
        
        return ranked_suggestions[:10]  # Kthe top 10 sugjerimet

    def _get_ai_template_suggestions(self, context: DocumentContext) -> List[DocumentSuggestion]:
        """
        Merr sugjerime template nga AI
        """
        prompt = f"""Based on this legal case information, suggest the most appropriate document templates:

Case Title: {context.title}
Case Type: {context.case_type}
Description: {context.content}

Please analyze and suggest:
1. Document types that would be needed for this case
2. Specific templates that would be most suitable
3. Priority/importance of each document
4. Key variables that would need to be filled

Respond in JSON format:
{{
  "suggestions": [
    {{
      "document_type": "type",
      "template_name": "name", 
      "confidence": 0.95,
      "priority": "high|medium|low",
      "description": "why this template is suitable",
      "key_variables": ["var1", "var2"]
    }}
  ]
}}"""
        
        response = self.llm_service._make_request([
            {"role": "system", "content": self.llm_service._create_legal_system_prompt(context)},
            {"role": "user", "content": prompt}
        ])
        
        suggestions = []
        
        if not response.error:
            try:
                ai_data = json.loads(response.text)
                for suggestion in ai_data.get('suggestions', []):
                    # Gjej template aktual në bazën e të dhënave
                    template = self._find_template_by_name(suggestion.get('template_name', ''))
                    
                    suggestions.append(DocumentSuggestion(
                        type=suggestion.get('document_type', 'general'),
                        confidence=suggestion.get('confidence', 0.5),
                        title=suggestion.get('template_name', ''),
                        description=suggestion.get('description', ''),
                        template_id=template.id if template else None,
                        variables={var: "" for var in suggestion.get('key_variables', [])},
                        metadata={
                            'priority': suggestion.get('priority', 'medium'),
                            'ai_generated': True
                        }
                    ))
                    
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Error parsing AI template suggestions: {e}")
        
        return suggestions

    def _get_rule_based_suggestions(self, case_info: Dict[str, Any]) -> List[DocumentSuggestion]:
        """
        Merr sugjerime bazuar në rregulla
        """
        suggestions = []
        case_type = case_info.get('case_type', 'civil').lower()
        
        # Template mapping rules
        template_rules = {
            'civil': ['padi_civile', 'ankese', 'pergjigje_padie'],
            'penal': ['ankese_penale', 'kerkese_hetim', 'mbrojtje_penale'],
            'tregtar': ['kontrate_tregtare', 'padi_tregtare', 'marreveshje_tregti'],
            'familjar': ['divorc', 'kujdestari', 'alimentacion'],
            'administrative': ['ankese_administrative', 'kerkese_administrative']
        }
        
        # Gjej template-t për case type
        relevant_templates = DocumentTemplate.objects.filter(
            category__icontains=case_type,
            is_active=True
        )
        
        for template in relevant_templates:
            suggestions.append(DocumentSuggestion(
                type=template.category,
                confidence=0.8,  # Rule-based ka confidence të lartë
                title=template.name,
                description=template.description,
                template_id=template.id,
                metadata={'rule_based': True}
            ))
        
        return suggestions

    def _rank_suggestions(self, 
                         suggestions: List[DocumentSuggestion], 
                         user_preferences: Dict[str, Any]) -> List[DocumentSuggestion]:
        """
        Rankon sugjerimet bazuar në confidence dhe preferences
        """
        def calculate_score(suggestion: DocumentSuggestion) -> float:
            score = suggestion.confidence
            
            # Boost për preferenca të user-it
            if user_preferences:
                preferred_types = user_preferences.get('preferred_document_types', [])
                if suggestion.type in preferred_types:
                    score += 0.2
            
            # Boost për template-t me AI generated content
            if suggestion.metadata.get('ai_generated'):
                score += 0.1
            
            # Penalizim për template-t pa template_id (nuk ekzistojnë)
            if not suggestion.template_id:
                score -= 0.3
            
            return score
        
        # Ranko dhe kthe
        return sorted(suggestions, key=calculate_score, reverse=True)

    def generate_document_content(self, 
                                template_id: int,
                                variables: Dict[str, Any],
                                case_info: Dict[str, Any] = None,
                                enhancement_level: str = "standard") -> Dict[str, Any]:
        """
        Gjeneron përmbajtjen e dokumentit duke kombinuar template dhe AI
        """
        try:
            template = DocumentTemplate.objects.get(id=template_id)
        except DocumentTemplate.DoesNotExist:
            return {"success": False, "error": "Template not found"}
        
        case_info = case_info or {}
        
        # Render template me variablat bazë
        context = TemplateContext(
            variables=variables,
            case_data=case_info,
            metadata={'enhancement_level': enhancement_level}
        )
        
        try:
            base_content = self.template_engine.render_template(template, context)
        except ValidationError as e:
            return {"success": False, "error": f"Template rendering error: {str(e)}"}
        
        # Enhance me AI nëse kërkohet
        if enhancement_level in ["enhanced", "premium"]:
            enhanced_content = self._enhance_content_with_ai(
                base_content, 
                template.category, 
                case_info,
                enhancement_level
            )
            
            if enhanced_content:
                base_content = enhanced_content
        
        # Suggest additional clauses
        suggested_clauses = []
        if enhancement_level == "premium":
            suggested_clauses = self._suggest_additional_clauses(
                base_content, 
                template.category,
                case_info
            )
        
        return {
            "success": True,
            "content": base_content,
            "template_used": template.name,
            "variables_used": variables,
            "suggested_clauses": suggested_clauses,
            "enhancement_level": enhancement_level
        }

    def _enhance_content_with_ai(self, 
                               content: str, 
                               document_type: str,
                               case_info: Dict[str, Any],
                               level: str) -> Optional[str]:
        """
        Përmirëson përmbajtjen e dokumentit me AI
        """
        context = DocumentContext(
            title=case_info.get('title', 'Document'),
            content=content,
            document_type=document_type,
            case_type=case_info.get('case_type'),
            metadata=case_info
        )
        
        enhancement_prompts = {
            "enhanced": "Improve and expand this legal document by adding relevant details, proper legal language, and ensuring completeness while maintaining the original structure.",
            "premium": "Provide comprehensive legal analysis and expansion of this document. Add sophisticated legal arguments, relevant case law references, detailed clauses, and professional legal language. Ensure the document is thorough and legally robust."
        }
        
        prompt = f"""{enhancement_prompts.get(level, enhancement_prompts['enhanced'])}

Original Document:
{content}

Case Context: {json.dumps(case_info, ensure_ascii=False)}

Please provide the enhanced version maintaining the original format and structure."""
        
        response = self.llm_service._make_request([
            {"role": "system", "content": self.llm_service._create_legal_system_prompt(context)},
            {"role": "user", "content": prompt}
        ])
        
        if response.error:
            logger.error(f"AI enhancement failed: {response.error}")
            return None
        
        return response.text

    def _suggest_additional_clauses(self, 
                                  content: str, 
                                  document_type: str,
                                  case_info: Dict[str, Any]) -> List[ClauseSuggestion]:
        """
        Sugjeron klauzola shtesë për dokumentin
        """
        context = DocumentContext(
            title=case_info.get('title', 'Document'),
            content=content,
            document_type=document_type,
            metadata=case_info
        )
        
        prompt = f"""Analyze this {document_type} document and suggest additional clauses that would strengthen it legally:

Document Content:
{content}

Case Information: {json.dumps(case_info, ensure_ascii=False)}

Please suggest:
1. Missing clauses that are commonly needed
2. Specific clauses for this type of case
3. Protective clauses for the client
4. Standard legal clauses for completeness

Format as JSON:
{{
  "suggestions": [
    {{
      "clause_type": "type_name",
      "content": "actual clause text",
      "position": "where to insert (beginning|middle|end)",
      "confidence": 0.95,
      "reasoning": "why this clause is important",
      "legal_references": ["relevant law articles"]
    }}
  ]
}}"""
        
        response = self.llm_service._make_request([
            {"role": "system", "content": self.llm_service._create_legal_system_prompt(context)},
            {"role": "user", "content": prompt}
        ])
        
        suggestions = []
        
        if not response.error:
            try:
                ai_data = json.loads(response.text)
                for suggestion in ai_data.get('suggestions', []):
                    # Map position to numeric value
                    position_map = {"beginning": 0, "middle": 50, "end": 100}
                    position = position_map.get(suggestion.get('position', 'end'), 100)
                    
                    suggestions.append(ClauseSuggestion(
                        clause_type=suggestion.get('clause_type', 'general'),
                        content=suggestion.get('content', ''),
                        position=position,
                        confidence=suggestion.get('confidence', 0.5),
                        reasoning=suggestion.get('reasoning', ''),
                        legal_references=suggestion.get('legal_references', [])
                    ))
                    
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Error parsing clause suggestions: {e}")
        
        return suggestions

    def extract_document_data(self, content: str, document_type: str = None) -> Dict[str, Any]:
        """
        Ekstrakton të dhëna strukturore nga përmbajtja e dokumentit
        """
        context = DocumentContext(
            title="Data Extraction",
            content=content,
            document_type=document_type or "general"
        )
        
        # Përdor pattern matching për ekstraktim bazë
        extracted_data = {}
        
        # Extract dates
        date_patterns = self.legal_patterns.get("legal_dates", [])
        dates = []
        for pattern in date_patterns:
            dates.extend(re.findall(pattern, content))
        
        if dates:
            extracted_data["dates"] = list(set(dates))
        
        # Extract monetary amounts
        amount_patterns = self.legal_patterns.get("monetary_amounts", [])
        amounts = []
        for pattern in amount_patterns:
            amounts.extend(re.findall(pattern, content))
        
        if amounts:
            extracted_data["amounts"] = list(set(amounts))
        
        # Use AI for more sophisticated extraction
        ai_extracted = self._ai_extract_document_data(context)
        
        # Merge results
        extracted_data.update(ai_extracted)
        
        return extracted_data

    def _ai_extract_document_data(self, context: DocumentContext) -> Dict[str, Any]:
        """
        Përdor AI për ekstraktim të avancuar të të dhënave
        """
        response = self.llm_service.extract_key_information(
            context, 
            info_types=['parties', 'dates', 'obligations', 'amounts', 'deadlines']
        )
        
        if response.error:
            return {}
        
        # Parse AI response to structured data
        # Implemento parsing të detajuar bazuar në response format
        return {"ai_extracted": response.text}

    def classify_document(self, content: str) -> Dict[str, Any]:
        """
        Klasifikon dokumentin në kategori
        """
        context = DocumentContext(
            title="Document Classification",
            content=content,
            document_type="unknown"
        )
        
        prompt = """Classify this legal document into appropriate categories:

Document Content:
{content}

Please identify:
1. Primary document type (contract, complaint, motion, etc.)
2. Legal area (civil, criminal, commercial, family, etc.)
3. Specific sub-type if applicable
4. Confidence level (0-1)
5. Key characteristics that led to this classification

Respond in JSON format:
{{
  "primary_type": "document_type",
  "legal_area": "area",
  "sub_type": "specific_type",
  "confidence": 0.95,
  "characteristics": ["characteristic1", "characteristic2"],
  "suggested_templates": ["template_name1", "template_name2"]
}}"""
        
        response = self.llm_service._make_request([
            {"role": "system", "content": self.llm_service._create_legal_system_prompt(context)},
            {"role": "user", "content": prompt.format(content=content[:1000])}  # Limit content
        ])
        
        if response.error:
            return {"success": False, "error": response.error}
        
        try:
            classification = json.loads(response.text)
            classification["success"] = True
            return classification
        except json.JSONDecodeError:
            return {"success": False, "error": "Failed to parse classification response"}

    def smart_document_merge(self, documents: List[Document], merge_strategy: str = "intelligent") -> Dict[str, Any]:
        """
        Kombinon dokumente të shumëfishta në mënyrë inteligjente
        """
        if len(documents) < 2:
            return {"success": False, "error": "Need at least 2 documents to merge"}
        
        # Analyze documents for merge compatibility
        compatibility_analysis = self._analyze_merge_compatibility(documents)
        
        if not compatibility_analysis["compatible"]:
            return {
                "success": False, 
                "error": "Documents are not compatible for merging",
                "analysis": compatibility_analysis
            }
        
        # Perform merge based on strategy
        if merge_strategy == "intelligent":
            merged_content = self._intelligent_merge(documents)
        elif merge_strategy == "sequential":
            merged_content = self._sequential_merge(documents)
        elif merge_strategy == "sectional":
            merged_content = self._sectional_merge(documents)
        else:
            return {"success": False, "error": f"Unknown merge strategy: {merge_strategy}"}
        
        return {
            "success": True,
            "merged_content": merged_content,
            "source_documents": [doc.id for doc in documents],
            "merge_strategy": merge_strategy,
            "compatibility_analysis": compatibility_analysis
        }

    def _analyze_merge_compatibility(self, documents: List[Document]) -> Dict[str, Any]:
        """
        Analizon kompatibilitetin e dokumenteve për merge
        """
        # Analyze document types, formats, and content structure
        doc_types = [doc.document_type.name for doc in documents]
        unique_types = set(doc_types)
        
        # Check if all documents are of compatible types
        compatible_type_groups = [
            {"contracts", "agreements", "amendments"},
            {"complaints", "motions", "responses"},
            {"reports", "summaries", "analyses"}
        ]
        
        is_compatible = False
        for group in compatible_type_groups:
            if all(doc_type.lower() in group for doc_type in unique_types):
                is_compatible = True
                break
        
        return {
            "compatible": is_compatible,
            "document_types": doc_types,
            "unique_types": list(unique_types),
            "total_documents": len(documents),
            "average_length": sum(len(doc.content) for doc in documents) / len(documents)
        }

    def _intelligent_merge(self, documents: List[Document]) -> str:
        """
        Merge inteligjent duke përdorur AI
        """
        # Prepare content for AI analysis
        contents = []
        for i, doc in enumerate(documents):
            contents.append(f"=== Document {i+1}: {doc.title} ===\n{doc.content}\n")
        
        combined_content = "\n".join(contents)
        
        context = DocumentContext(
            title="Document Merge",
            content=combined_content,
            document_type=documents[0].document_type.name
        )
        
        prompt = f"""Intelligently merge these {len(documents)} legal documents into a single, coherent document:

{combined_content}

Requirements:
1. Eliminate redundancies and contradictions
2. Maintain legal coherence and structure
3. Preserve important information from all documents
4. Create smooth transitions between sections
5. Ensure the merged document is legally sound

Please provide the merged document with clear sections and proper legal formatting."""
        
        response = self.llm_service._make_request([
            {"role": "system", "content": self.llm_service._create_legal_system_prompt(context)},
            {"role": "user", "content": prompt}
        ])
        
        if response.error:
            # Fallback to sequential merge
            return self._sequential_merge(documents)
        
        return response.text

    def _sequential_merge(self, documents: List[Document]) -> str:
        """
        Merge sekuencial të dokumenteve
        """
        merged_parts = []
        
        for i, doc in enumerate(documents):
            merged_parts.append(f"<!-- Përfshirë nga: {doc.title} -->")
            merged_parts.append(doc.content)
            
            if i < len(documents) - 1:
                merged_parts.append("\n---\n")
        
        return "\n\n".join(merged_parts)

    def _find_template_by_name(self, name: str) -> Optional[DocumentTemplate]:
        """
        Gjej template bazuar në emër
        """
        # Fuzzy matching për template names
        templates = DocumentTemplate.objects.filter(is_active=True)
        
        for template in templates:
            if name.lower() in template.name.lower() or template.name.lower() in name.lower():
                return template
        
        return None

# Factory function
def get_automation_engine() -> DocumentAutomationEngine:
    """Factory function për DocumentAutomationEngine"""
    return DocumentAutomationEngine()
