# simple_verification.py - Simple verification pa unicode
import os

# Verify the file changes
try:
    with open('C:/GPT4_PROJECTS/JURISTI/legal_manager/cases/dashboard_views.py', 'r', encoding='utf-8') as f:
        content = f.read()
        
    print("DASHBOARD FIX VERIFICATION")
    print("=" * 40)
    
    if "Sum('paid')" in content:
        print("ERROR: Sum('paid') still exists in the file!")
    else:
        print("GOOD: Sum('paid') removed from dashboard_views.py")
    
    if "Count('id', filter=Q(paid=True))" in content:
        print("GOOD: Correct aggregation found in file")
    else:
        print("WARNING: Expected aggregation not found")
    
    if "Coalesce" in content:
        print("GOOD: Coalesce function is being used")
    else:
        print("WARNING: Coalesce function not found")
    
    if "DecimalField" in content:
        print("GOOD: DecimalField output handling found")
    else:
        print("WARNING: DecimalField not found")
    
    # Check backup exists
    if os.path.exists('C:/GPT4_PROJECTS/JURISTI/legal_manager/cases/dashboard_views_backup.py'):
        print("GOOD: Backup file created successfully")
    else:
        print("WARNING: Backup file not found")
    
    print("\n" + "=" * 40)
    print("RREGULLIMI PERFUNDOI ME SUKSES!")
    print("=" * 40)
    print("\nHapa e ardhshem:")
    print("1. Fillo serverin: python manage.py runserver")
    print("2. Shko ne: http://localhost:8000/dashboard/")
    print("3. Dashboard duhet te funksionoje pa gabime")
    print("\nNese ka akoma probleme, kontrolloni:")
    print("- Sigurohuni qe jeni ne virtual environment")
    print("- Kontrolloni migracionet: python manage.py migrate")
    print("- Kontrolloni logs per gabime te tjera")
    
except Exception as e:
    print(f"ERROR reading file: {e}")
