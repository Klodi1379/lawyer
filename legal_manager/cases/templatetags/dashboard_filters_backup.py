# templatetags/dashboard_filters.py
# Custom template filters për dashboard

from django import template
import re

register = template.Library()

@register.filter
def replace(value, args):
    """
    Replaces all occurrences of the search string with the replacement string.
    Usage: {{ "hello_world"|replace:"_,|" }}
    """
    if not args:
        return value
    
    try:
        if ',' in args:
            search, replacement = args.split(',', 1)
        else:
            # Default replacement për underscore me space
            search = args
            replacement = ' '
        
        return str(value).replace(search, replacement)
    except ValueError:
        return value

@register.filter
def underscore_to_space(value):
    """
    Converts underscores to spaces
    Usage: {{ "hello_world"|underscore_to_space }}
    """
    return str(value).replace('_', ' ')

@register.filter
def title_case(value):
    """
    Converts text to title case, handling underscores
    Usage: {{ "hello_world"|title_case }}
    """
    return str(value).replace('_', ' ').title()

@register.filter
def humanize_field_name(value):
    """
    Converts field names to human readable format
    Usage: {{ "total_cases"|humanize_field_name }}
    """
    # Convert underscore to space and title case
    humanized = str(value).replace('_', ' ').title()
    
    # Special cases for better readability
    replacements = {
        'Id': 'ID',
        'Url': 'URL',
        'Api': 'API',
        'Html': 'HTML',
        'Json': 'JSON',
        'Xml': 'XML',
        'Pdf': 'PDF',
        'Csv': 'CSV',
    }
    
    for old, new in replacements.items():
        humanized = humanized.replace(old, new)
    
    return humanized

@register.filter
def format_currency(value):
    """
    Formats a number as currency
    Usage: {{ 1234.56|format_currency }}
    """
    try:
        return f"${float(value):,.2f}"
    except (ValueError, TypeError):
        return value

@register.filter
def percentage(value, decimals=1):
    """
    Formats a number as percentage
    Usage: {{ 0.75|percentage }} or {{ 75|percentage:0 }}
    """
    try:
        num = float(value)
        # If value is between 0 and 1, assume it's already a decimal
        if 0 <= num <= 1:
            num = num * 100
        return f"{num:.{decimals}f}%"
    except (ValueError, TypeError):
        return value

@register.filter
def truncate_smart(value, length=50):
    """
    Smart truncation that tries to break at word boundaries
    Usage: {{ "Long text here"|truncate_smart:30 }}
    """
    if len(str(value)) <= length:
        return value
    
    truncated = str(value)[:length]
    # Try to break at the last space
    last_space = truncated.rfind(' ')
    if last_space > length * 0.8:  # Only if the space is near the end
        truncated = truncated[:last_space]
    
    return truncated + '...'

@register.filter
def dict_get(dictionary, key):
    """
    Gets a value from a dictionary by key
    Usage: {{ my_dict|dict_get:"key_name" }}
    """
    if hasattr(dictionary, 'get'):
        return dictionary.get(key)
    return None

@register.filter
def add_class(field, css_class):
    """
    Adds a CSS class to a form field
    Usage: {{ form.field|add_class:"form-control" }}
    """
    return field.as_widget(attrs={'class': css_class})

@register.filter
def multiply(value, multiplier):
    """
    Multiplies two numbers
    Usage: {{ hours|multiply:60 }}
    """
    try:
        return float(value) * float(multiplier)
    except (ValueError, TypeError):
        return 0

@register.filter
def divide(value, divisor):
    """
    Divides two numbers
    Usage: {{ minutes|divide:60 }}
    """
    try:
        return float(value) / float(divisor)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.simple_tag
def dashboard_badge_class(status):
    """
    Returns appropriate badge class for different statuses
    Usage: {% dashboard_badge_class "open" %}
    """
    badge_classes = {
        'open': 'badge-primary',
        'closed': 'badge-success', 
        'in_court': 'badge-warning',
        'appeal': 'badge-info',
        'draft': 'badge-secondary',
        'final': 'badge-success',
        'pending': 'badge-warning',
        'paid': 'badge-success',
        'unpaid': 'badge-danger',
        'active': 'badge-success',
        'inactive': 'badge-secondary',
    }
    return badge_classes.get(str(status).lower(), 'badge-secondary')

@register.inclusion_tag('dashboard/widgets/progress_bar.html')
def progress_bar(value, max_value=100, label="", color="primary"):
    """
    Renders a progress bar
    Usage: {% progress_bar 75 100 "Completion" "success" %}
    """
    try:
        percentage = (float(value) / float(max_value)) * 100
    except (ValueError, TypeError, ZeroDivisionError):
        percentage = 0
    
    return {
        'percentage': min(percentage, 100),
        'value': value,
        'max_value': max_value,
        'label': label,
        'color': color
    }
