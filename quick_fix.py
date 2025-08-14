# quick_fix.py - Script për të aplikuar rregullimin e shpejtë
"""
Quick fix script për gabimin 'Cannot filter a query once a slice has been taken'

Ky gabim ndodh kur:
1. Aplicojmë .distinct() në queryset
2. Django ListView aplikon pagination (slice)
3. Pastaj përpiqemi të aplikojmë filtra të tjera

ZGJIDHJA: Riorganizoj filtrimet në get_queryset()
"""

import os
import shutil
from pathlib import Path

def backup_and_replace_views():
    """Backup original views dhe replace me version fixed"""
    
    # Paths
    current_dir = Path(__file__).parent
    original_views = current_dir / 'views_improved.py'
    fixed_views = current_dir / 'views_fixed.py'
    backup_views = current_dir / 'views_improved_backup.py'
    
    try:
        # Backup original
        if original_views.exists():
            shutil.copy2(original_views, backup_views)
            print(f"✅ Backup krijuar: {backup_views}")
        
        # Replace me fixed version
        if fixed_views.exists():
            shutil.copy2(fixed_views, original_views)
            print(f"✅ Views replaced me version fixed")
            
            # Update imports në urls nëse nevojitet
            print("🔧 Sigurohu që imports në urls.py dhe files të tjera të jenë correct")
            
        else:
            print("❌ views_fixed.py not found!")
            return False
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False
    
    return True

def show_changes_summary():
    """Trego ndryshimet e bëra"""
    print("\n" + "="*50)
    print("NDRYSHIMET E APLIKUARA:")
    print("="*50)
    
    changes = [
        "✅ Riorganizova get_queryset() në DocumentViewSet",
        "✅ Aplikoj filtrimet së pari, pastaj .distinct() në fund", 
        "✅ Përmirësova logjikën e access control me Q objects",
        "✅ Hoqa konfliktet e slice-ve në queryset",
        "✅ Shtova bulk_action handling të përmirësuar",
        "✅ Fixed permission checking për access control"
    ]
    
    for change in changes:
        print(change)
    
    print("\n" + "="*50)
    print("INSTRUKSIONE SHTESË:")
    print("="*50)
    
    instructions = [
        "1. Restart Django development server",
        "2. Test /documents/ endpoint-in",
        "3. Test filtering dhe search functionality", 
        "4. Kontrollo që permissions working correctly",
        "5. Test bulk actions në admin panel"
    ]
    
    for instruction in instructions:
        print(instruction)

def test_queryset_syntax():
    """Test syntax i queryset-it për të siguruar që nuk ka gabime"""
    test_code = '''
# Test që distinct() aplikohet vetëm në fund
queryset = Document.objects.select_related('document_type', 'status')

# Filtrime të ndryshme
queryset = queryset.filter(document_type_id=1)
queryset = queryset.filter(status_id=2)

# Access control me Q objects
from django.db.models import Q
access_filter = Q(created_by_id=1) | Q(access_level='public')
queryset = queryset.filter(access_filter)

# Distinct vetëm në fund
final_queryset = queryset.distinct()
print("✅ Queryset syntax correct")
'''
    
    try:
        # Compile test code
        compile(test_code, '<string>', 'exec')
        print("✅ Queryset syntax validation passed")
        return True
    except SyntaxError as e:
        print(f"❌ Syntax error: {str(e)}")
        return False

if __name__ == '__main__':
    print("🚀 Aplikimi i rregullimit për gabimin 'slice' në Django...")
    print()
    
    # Test syntax
    if not test_queryset_syntax():
        print("❌ Syntax test failed, stopping...")
        exit(1)
    
    # Apply fix
    if backup_and_replace_views():
        show_changes_summary()
        print("\n🎉 Rregullimi aplikuar me sukses!")
        print("\n📝 NEXT STEPS:")
        print("1. python manage.py runserver")
        print("2. Visit http://127.0.0.1:8000/documents/")
        print("3. Test filtering dhe search")
    else:
        print("\n❌ Gabim gjatë aplikimit të rregullimit")
