"""
Legal Template Engine - Sistem i avancuar për gjenerim automatik të dokumenteve juridike
Integron me LLM për personalizim dhe adaptim inteligjent të template-ve
"""

import re
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date
from dataclasses import dataclass, field
from enum import Enum
from jinja2 import Environment, BaseLoader, meta, select_autoescape
from jinja2.exceptions import TemplateError, UndefinedError

from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from ..services.llm_service import LegalLLMService, DocumentContext
from ..models.document_models import DocumentTemplate, Document

User = get_user_model()

class TemplateVariableType(Enum):
    """Llojet e variablave në template"""
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    BOOLEAN = "boolean"
    CHOICE = "choice"
    MULTIPLE_CHOICE = "multiple_choice"
    TABLE = "table"
    NESTED_OBJECT = "nested_object"
    CALCULATED = "calculated"

@dataclass
class TemplateVariable:
    """Definicion i një variabli template"""
    name: str
    type: TemplateVariableType
    label: str
    description: str = ""
    required: bool = True
    default_value: Any = None
    validation_rules: Dict[str, Any] = field(default_factory=dict)
    choices: List[Tuple[str, str]] = field(default_factory=list)  # [(value, label)]
    depends_on: List[str] = field(default_factory=list)  # Dependencies
    ai_suggested: bool = False  # A është sugjeruar nga AI

@dataclass
class TemplateContext:
    """Konteksti për renderim të template"""
    variables: Dict[str, Any]
    case_data: Optional[Dict[str, Any]] = None
    client_data: Optional[Dict[str, Any]] = None
    legal_references: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

class LegalTemplateEngine:
    """
    Engine kryesor për template-t juridikë me integrim LLM
    """
    
    def __init__(self):
        self.jinja_env = Environment(
            loader=BaseLoader(),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Regjistro custom filters dhe functions
        self._register_custom_filters()
        self._register_custom_functions()
        
        self.llm_service = LegalLLMService()
        
        # Legal-specific configurations
        self.jurisdiction = getattr(settings, 'LEGAL_JURISDICTION', 'Albania')
        self.date_format = getattr(settings, 'LEGAL_DATE_FORMAT', '%d.%m.%Y')
        self.number_format = getattr(settings, 'LEGAL_NUMBER_FORMAT', '{:,.2f}')

    def _register_custom_filters(self):
        """Regjistron filter të personalizuar për dokumente juridike"""
        
        @self.jinja_env.filter()
        def legal_date(value, format_type='long'):
            """Formatim i datës për dokumente juridike"""
            if not value:
                return ""
            
            if isinstance(value, str):
                # Provo të parsosh string
                try:
                    if 'T' in value:  # ISO format
                        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    else:
                        value = datetime.strptime(value, '%Y-%m-%d')
                except:
                    return value  # Kthe origjinalin nëse nuk mund ta parsojë
            
            if isinstance(value, datetime):
                value = value.date()
            
            if format_type == 'short':
                return value.strftime(self.date_format)
            elif format_type == 'long':
                months = [
                    '', 'janar', 'shkurt', 'mars', 'prill', 'maj', 'qershor',
                    'korrik', 'gusht', 'shtator', 'tetor', 'nëntor', 'dhjetor'
                ]
                return f"{value.day} {months[value.month]} {value.year}"
            elif format_type == 'legal':
                return f"më {value.strftime(self.date_format)}"
            
            return value.strftime(self.date_format)

        @self.jinja_env.filter()
        def legal_amount(value, currency='EUR'):
            """Formatim i shumave monetare për dokumente juridike"""
            if value is None:
                return ""
            
            try:
                amount = float(value)
                formatted = self.number_format.format(amount)
                return f"{formatted} {currency}"
            except (ValueError, TypeError):
                return str(value)

        @self.jinja_env.filter()
        def capitalize_legal(value):
            """Kapitalizim i përshtatshëm për dokumente juridike"""
            if not value:
                return ""
            return value[0].upper() + value[1:].lower() if len(value) > 1 else value.upper()

        @self.jinja_env.filter()
        def legal_reference(article_number, law_name=""):
            """Formatim i referencave ligjore"""
            if not article_number:
                return ""
            
            if law_name:
                return f"neni {article_number} të {law_name}"
            return f"neni {article_number}"

        @self.jinja_env.filter()
        def ordinal_number(value):
            """Konverton numrat në forma ordinale (1-ri, 2-ri, etj.)"""
            if not value:
                return ""
            
            try:
                num = int(value)
                if num == 1:
                    return "i parë"
                elif num == 2:
                    return "i dytë"
                elif num == 3:
                    return "i tretë"
                else:
                    return f"i {num}-të"
            except (ValueError, TypeError):
                return str(value)

    def _register_custom_functions(self):
        """Regjistron funksione globale për template"""
        
        def current_date(format_type='legal'):
            """Data aktuale në format juridik"""
            today = timezone.now().date()
            return self.jinja_env.filters['legal_date'](today, format_type)
        
        def case_reference(case_uid, year=None):
            """Referencë e rastit juridik"""
            if year:
                return f"Rasti nr. {case_uid}/{year}"
            return f"Rasti nr. {case_uid}"
        
        def legal_citation(article, law, paragraph=None):
            """Citim ligjor"""
            citation = f"neni {article} të {law}"
            if paragraph:
                citation += f", paragrafi {paragraph}"
            return citation

        # Shto funksionet në environment
        self.jinja_env.globals.update({
            'current_date': current_date,
            'case_reference': case_reference,
            'legal_citation': legal_citation,
            'today': datetime.now().date()
        })

    def parse_template_variables(self, template_content: str) -> List[TemplateVariable]:
        """
        Analizon template dhe ekstrakton variablat e nevojshme
        """
        try:
            # Përdor Jinja2 meta për të gjetur variablat
            parsed = self.jinja_env.parse(template_content)
            variables = meta.find_undeclared_variables(parsed)
            
            template_vars = []
            
            for var_name in variables:
                # Skip variablat globale
                if var_name in self.jinja_env.globals:
                    continue
                
                # Analizimi i tipit dhe karakteristikave të variablit
                var_info = self._analyze_variable_usage(template_content, var_name)
                
                template_var = TemplateVariable(
                    name=var_name,
                    type=var_info['type'],
                    label=var_info['label'],
                    description=var_info['description'],
                    required=var_info['required'],
                    validation_rules=var_info['validation_rules']
                )
                
                template_vars.append(template_var)
            
            return template_vars
            
        except TemplateError as e:
            raise ValidationError(f"Gabim në template: {str(e)}")

    def _analyze_variable_usage(self, template_content: str, var_name: str) -> Dict[str, Any]:
        """
        Analizon përdorimin e një variabli në template për të caktuar tipin
        """
        # Patterns për të identifikuar llojet
        patterns = {
            'date': [
                rf'{var_name}\s*\|\s*legal_date',
                rf'{var_name}_date',
                rf'date.*{var_name}',
            ],
            'amount': [
                rf'{var_name}\s*\|\s*legal_amount',
                rf'{var_name}_amount',
                rf'amount.*{var_name}',
                rf'sum.*{var_name}',
            ],
            'boolean': [
                rf'if\s+{var_name}',
                rf'{var_name}\s*and\s+',
                rf'{var_name}\s*or\s+',
            ]
        }
        
        detected_type = TemplateVariableType.TEXT  # Default
        
        for var_type, type_patterns in patterns.items():
            for pattern in type_patterns:
                if re.search(pattern, template_content, re.IGNORECASE):
                    detected_type = TemplateVariableType(var_type)
                    break
            if detected_type != TemplateVariableType.TEXT:
                break
        
        # Gjeneroj label dhe description nga emri i variablit
        label = var_name.replace('_', ' ').title()
        description = f"Vendosni vlerën për {label}"
        
        # Vendos required bazuar në përdorimin në template
        required = not bool(re.search(rf'{var_name}\s*\|\s*default\(', template_content))
        
        return {
            'type': detected_type,
            'label': label,
            'description': description,
            'required': required,
            'validation_rules': {}
        }

    def suggest_template_variables_with_ai(self, 
                                         template_content: str, 
                                         document_type: str) -> List[TemplateVariable]:
        """
        Përdor AI për të sugjeruar variablat për një template
        """
        context = DocumentContext(
            title=f"Template Analysis - {document_type}",
            content=template_content,
            document_type=document_type
        )
        
        prompt = f"""Analyze this legal document template and suggest appropriate variables with their types and descriptions:

Document Type: {document_type}
Template Content: {template_content}

Please identify variables that should be:
1. Required vs Optional
2. Their data types (text, number, date, boolean, choice)
3. Validation rules
4. Default values if applicable
5. Dependencies between variables

Respond in JSON format with structure:
{{
  "variables": [
    {{
      "name": "variable_name",
      "type": "text|number|date|boolean|choice",
      "label": "Human readable label",
      "description": "Detailed description",
      "required": true|false,
      "validation_rules": {{}},
      "choices": [["value", "label"]],
      "depends_on": ["other_variable"],
      "default_value": "default if any"
    }}
  ]
}}"""
        
        response = self.llm_service._make_request([
            {"role": "system", "content": self.llm_service._create_legal_system_prompt(context)},
            {"role": "user", "content": prompt}
        ])
        
        if response.error:
            # Fallback to manual parsing
            return self.parse_template_variables(template_content)
        
        try:
            ai_suggestion = json.loads(response.text)
            variables = []
            
            for var_data in ai_suggestion.get('variables', []):
                var = TemplateVariable(
                    name=var_data['name'],
                    type=TemplateVariableType(var_data['type']),
                    label=var_data['label'],
                    description=var_data['description'],
                    required=var_data.get('required', True),
                    validation_rules=var_data.get('validation_rules', {}),
                    choices=[(choice[0], choice[1]) for choice in var_data.get('choices', [])],
                    depends_on=var_data.get('depends_on', []),
                    default_value=var_data.get('default_value'),
                    ai_suggested=True
                )
                variables.append(var)
            
            return variables
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Fallback në rast gabimi
            return self.parse_template_variables(template_content)

    def render_template(self, 
                       template: DocumentTemplate, 
                       context: TemplateContext,
                       validate_variables: bool = True) -> str:
        """
        Renderon një template me kontekstin e dhënë
        """
        if validate_variables:
            # Valido variablat e nevojshëm
            required_vars = self.parse_template_variables(template.content)
            missing_vars = [
                var.name for var in required_vars 
                if var.required and var.name not in context.variables
            ]
            
            if missing_vars:
                raise ValidationError(f"Variablat e nevojshëm mungojnë: {', '.join(missing_vars)}")

        try:
            # Krijo template Jinja2
            jinja_template = self.jinja_env.from_string(template.content)
            
            # Përgatit kontekstin për renderim
            render_context = {
                **context.variables,
                'case': context.case_data or {},
                'client': context.client_data or {},
                'legal_refs': context.legal_references,
                'metadata': context.metadata,
                'template_name': template.name,
                'template_category': template.category
            }
            
            # Rendero template
            rendered_content = jinja_template.render(**render_context)
            
            return rendered_content
            
        except (TemplateError, UndefinedError) as e:
            raise ValidationError(f"Gabim në renderim: {str(e)}")

    def enhance_template_with_ai(self, 
                               template: DocumentTemplate,
                               enhancement_type: str = "improve") -> str:
        """
        Përmirëson një template duke përdorur AI
        """
        context = DocumentContext(
            title=template.name,
            content=template.content,
            document_type=template.category
        )
        
        enhancement_prompts = {
            "improve": "Improve this legal document template by making it more comprehensive, legally accurate, and professionally formatted.",
            "modernize": "Modernize this legal document template with current legal language and best practices.",
            "simplify": "Simplify this legal document template while maintaining legal accuracy and completeness.",
            "expand": "Expand this legal document template with additional relevant sections and details."
        }
        
        prompt = f"""{enhancement_prompts.get(enhancement_type, enhancement_prompts['improve'])}

Current Template:
Name: {template.name}
Category: {template.category}
Content: {template.content}

Please provide:
1. Enhanced template content
2. Explanation of improvements made
3. Suggested variable definitions
4. Legal considerations

Maintain the Jinja2 template syntax and ensure compatibility with the existing variable structure."""

        response = self.llm_service._make_request([
            {"role": "system", "content": self.llm_service._create_legal_system_prompt(context)},
            {"role": "user", "content": prompt}
        ])
        
        if response.error:
            raise ValidationError(f"AI enhancement failed: {response.error}")
        
        return response.text

    def validate_template_syntax(self, template_content: str) -> Tuple[bool, List[str]]:
        """
        Valido sintaksën e template
        """
        errors = []
        
        try:
            # Testo parsing Jinja2
            self.jinja_env.parse(template_content)
            
            # Kontrollo për probleme të zakonshme
            if not template_content.strip():
                errors.append("Template është bosh")
            
            # Kontrollo për variablat e pa-definuar
            try:
                parsed = self.jinja_env.parse(template_content)
                variables = meta.find_undeclared_variables(parsed)
                
                # Paralajmëro për variablat që mund të jenë problematikë
                problematic_vars = [var for var in variables if not var.replace('_', '').replace('-', '').isalnum()]
                if problematic_vars:
                    errors.append(f"Variablat me emra të dyshimtë: {', '.join(problematic_vars)}")
                    
            except Exception:
                pass  # Gabime të tjera do të kapen nga parsing kryesor
        
        except TemplateError as e:
            errors.append(f"Gabim sintakse: {str(e)}")
        except Exception as e:
            errors.append(f"Gabim i papritur: {str(e)}")
        
        return len(errors) == 0, errors

    def create_template_from_document(self, 
                                    document: Document,
                                    template_name: str,
                                    extract_variables: bool = True) -> DocumentTemplate:
        """
        Krijn një template nga një dokument ekzistues
        """
        # Përdor AI për të identifikuar dhe zëvendësuar vlerat me variabla
        if extract_variables:
            template_content = self._extract_variables_from_content(document.content, document.document_type.name)
        else:
            template_content = document.content
        
        # Krijo template
        template = DocumentTemplate.objects.create(
            name=template_name,
            description=f"Template i gjeneruar nga dokumenti: {document.title}",
            category=document.document_type.name,
            content=template_content,
            variables={},  # Do të plotësohet më vonë
            created_by=document.created_by
        )
        
        # Analizoj dhe ruaj informacionin e variablave
        template_vars = self.parse_template_variables(template_content)
        template.variables = {
            'parsed_variables': [
                {
                    'name': var.name,
                    'type': var.type.value,
                    'label': var.label,
                    'description': var.description,
                    'required': var.required
                }
                for var in template_vars
            ]
        }
        template.save()
        
        return template

    def _extract_variables_from_content(self, content: str, document_type: str) -> str:
        """
        Përdor AI për të ekstraktuar variablat nga përmbajtja e dokumentit
        """
        context = DocumentContext(
            title=f"Variable Extraction - {document_type}",
            content=content,
            document_type=document_type
        )
        
        prompt = f"""Convert this legal document into a Jinja2 template by replacing specific values with appropriate variables:

Document Type: {document_type}
Content: {content}

Guidelines:
1. Replace names, dates, amounts, addresses with variables like {{{{ client_name }}}}, {{{{ contract_date }}}}, {{{{ amount }}}}
2. Keep legal language and structure intact
3. Use meaningful variable names
4. Add Jinja2 filters where appropriate (e.g., {{{{ date_field | legal_date }}}})
5. Preserve legal references and standard clauses
6. Use conditional blocks for optional sections

Return only the template content with Jinja2 syntax."""
        
        response = self.llm_service._make_request([
            {"role": "system", "content": self.llm_service._create_legal_system_prompt(context)},
            {"role": "user", "content": prompt}
        ])
        
        if response.error:
            # Fallback - kthe përmbajtjen origjinale
            return content
        
        return response.text

    def preview_template(self, 
                        template: DocumentTemplate, 
                        sample_data: Dict[str, Any] = None) -> str:
        """
        Gjeneron një preview të template me të dhëna shembull
        """
        if not sample_data:
            # Gjenero të dhëna shembull
            template_vars = self.parse_template_variables(template.content)
            sample_data = self._generate_sample_data(template_vars)
        
        context = TemplateContext(
            variables=sample_data,
            case_data={'uid': 'SAMPLE-001', 'type': 'Sample Case'},
            client_data={'name': 'Sample Client', 'address': 'Sample Address'}
        )
        
        try:
            return self.render_template(template, context, validate_variables=False)
        except ValidationError as e:
            return f"GABIM NË PREVIEW: {str(e)}\n\nTemplate origjinal:\n{template.content}"

    def _generate_sample_data(self, template_vars: List[TemplateVariable]) -> Dict[str, Any]:
        """
        Gjeneron të dhëna shembull për preview
        """
        sample_data = {}
        
        for var in template_vars:
            if var.type == TemplateVariableType.TEXT:
                sample_data[var.name] = f"[{var.label}]"
            elif var.type == TemplateVariableType.NUMBER:
                sample_data[var.name] = 1000.00
            elif var.type == TemplateVariableType.DATE:
                sample_data[var.name] = datetime.now().date()
            elif var.type == TemplateVariableType.BOOLEAN:
                sample_data[var.name] = True
            elif var.type == TemplateVariableType.CHOICE and var.choices:
                sample_data[var.name] = var.choices[0][0]
            else:
                sample_data[var.name] = f"[{var.name}]"
        
        return sample_data

# Factory functions për lehtësi përdorimi

def get_template_engine() -> LegalTemplateEngine:
    """Merr instance të template engine"""
    return LegalTemplateEngine()

def render_legal_template(template_id: int, 
                         variables: Dict[str, Any], 
                         case=None, 
                         client=None) -> str:
    """Funksion i shkurtër për renderim template"""
    try:
        template = DocumentTemplate.objects.get(id=template_id)
    except DocumentTemplate.DoesNotExist:
        raise ValidationError("Template nuk u gjet")
    
    engine = get_template_engine()
    
    context = TemplateContext(
        variables=variables,
        case_data=case.__dict__ if case else None,
        client_data=client.__dict__ if client else None
    )
    
    return engine.render_template(template, context)
