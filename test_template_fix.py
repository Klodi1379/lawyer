# test_template_fix.py - Test për template fix

# Verify files exist and check content
import os

print("TEMPLATE FIX VERIFICATION")
print("=" * 40)

# Check if templatetags directory exists
templatetags_dir = "C:/GPT4_PROJECTS/JURISTI/legal_manager/cases/templatetags"
if os.path.exists(templatetags_dir):
    print("GOOD: templatetags directory created")
else:
    print("ERROR: templatetags directory missing")

# Check if dashboard_filters.py exists
filters_file = f"{templatetags_dir}/dashboard_filters.py"
if os.path.exists(filters_file):
    print("GOOD: dashboard_filters.py created")
    
    # Check if it contains the replace filter
    with open(filters_file, 'r', encoding='utf-8') as f:
        content = f.read()
        if "def replace(" in content:
            print("GOOD: replace filter defined")
        if "def humanize_field_name(" in content:
            print("GOOD: humanize_field_name filter defined")
else:
    print("ERROR: dashboard_filters.py missing")

# Check if template was updated
template_file = "C:/GPT4_PROJECTS/JURISTI/templates/dashboard/enhanced_index.html"
if os.path.exists(template_file):
    print("GOOD: enhanced_index.html exists")
    
    with open(template_file, 'r', encoding='utf-8') as f:
        content = f.read()
        if "{% load dashboard_filters %}" in content:
            print("GOOD: dashboard_filters loaded in template")
        else:
            print("ERROR: dashboard_filters not loaded")
            
        if "humanize_field_name" in content:
            print("GOOD: humanize_field_name used in template")
        else:
            print("WARNING: humanize_field_name not found")
            
        if '|replace:' in content:
            print("ERROR: replace filter still used in template")
        else:
            print("GOOD: replace filter removed from template")
else:
    print("ERROR: enhanced_index.html missing")

# Check widgets directory
widgets_dir = "C:/GPT4_PROJECTS/JURISTI/templates/dashboard/widgets"
if os.path.exists(widgets_dir):
    print("GOOD: widgets directory created")
else:
    print("ERROR: widgets directory missing")

print("\n" + "=" * 40)
print("TEMPLATE FIX SUMMARY")
print("=" * 40)
print("\nChanges made:")
print("1. Created custom templatetags/dashboard_filters.py")
print("2. Added {% load dashboard_filters %} to template")
print("3. Replaced |replace filter with |humanize_field_name")
print("4. Created widgets directory and progress_bar.html")
print("\nNext step: Test the dashboard again!")
print("python manage.py runserver")
print("http://localhost:8000/dashboard/")
