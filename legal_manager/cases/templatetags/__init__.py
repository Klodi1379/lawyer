# templatetags/__init__.py
# Required për Django templatetags

# Explicitly import the template tag modules to ensure they're discoverable
try:
    from . import dashboard_filters
    from . import replace_filter
except ImportError as e:
    # Gracefully handle import errors during Django startup
    pass
