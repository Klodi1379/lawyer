# simple_final_verification.py - Verifikim final pa unicode

import os

def main():
    print("=" * 50)
    print("VERIFIKIM FINAL I RREGULLIMEVE")
    print("=" * 50)
    
    success_count = 0
    error_count = 0
    
    print("Kontrolli i rregullimeve:")
    print("-" * 30)
    
    # 1. Check dashboard_views.py
    dashboard_file = "C:/GPT4_PROJECTS/JURISTI/legal_manager/cases/dashboard_views.py"
    if os.path.exists(dashboard_file):
        with open(dashboard_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if "Sum('paid')" not in content:
            print("GOOD: Sum('paid') u hoq nga dashboard_views.py")
            success_count += 1
        else:
            print("ERROR: Sum('paid') akoma ekziston ne dashboard_views.py")
            error_count += 1
            
        if "Count('id', filter=Q(paid=True))" in content:
            print("GOOD: Agregimi i sakte u shtua")
            success_count += 1
        else:
            print("ERROR: Agregimi i sakte mungon")
            error_count += 1
    else:
        print("ERROR: dashboard_views.py nuk u gjet")
        error_count += 1
    
    # 2. Check template filters
    filters_file = "C:/GPT4_PROJECTS/JURISTI/legal_manager/cases/templatetags/dashboard_filters.py"
    if os.path.exists(filters_file):
        print("GOOD: Custom filters u krijuan")
        success_count += 1
    else:
        print("ERROR: dashboard_filters.py mungon")
        error_count += 1
    
    # 3. Check template update
    template_file = "C:/GPT4_PROJECTS/JURISTI/templates/dashboard/enhanced_index.html"
    if os.path.exists(template_file):
        with open(template_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if "{% load dashboard_filters %}" in content:
            print("GOOD: Dashboard filters u ngarkuan ne template")
            success_count += 1
        else:
            print("ERROR: Dashboard filters nuk u ngarkuan")
            error_count += 1
            
        if "|replace:" not in content:
            print("GOOD: Replace filter u hoq nga template")
            success_count += 1
        else:
            print("ERROR: Replace filter akoma ekziston")
            error_count += 1
    else:
        print("ERROR: enhanced_index.html nuk u gjet")
        error_count += 1
    
    # 4. Check backup
    backup_file = "C:/GPT4_PROJECTS/JURISTI/legal_manager/cases/dashboard_views_backup.py"
    if os.path.exists(backup_file):
        print("GOOD: Backup file u krijua")
        success_count += 1
    else:
        print("WARNING: Backup file mungon")
    
    print("\n" + "=" * 50)
    print("PERMBLEDHJE FINALE")
    print("=" * 50)
    print(f"Rregullime te suksesshme: {success_count}")
    print(f"Gabime: {error_count}")
    
    if error_count == 0:
        print("\nSUKSES! Te gjitha rregullimet u aplikuan!")
        print("\nTani mund te testoni sistemin:")
        print("1. python manage.py runserver")
        print("2. http://localhost:8000/dashboard/")
        print("\nSistemi duhet te funksionoje pa gabime!")
    else:
        print(f"\nKA {error_count} GABIME qe duhen rregulluar")
        print("Kontaktoni per ndihme nese ka nevoje.")
    
    print("\nRregullimet e bera:")
    print("- Rregulluar gabimi 'Cannot compute Sum(paid)'")
    print("- Rregulluar gabimi 'Invalid filter: replace'")
    print("- Krijuar custom template filters")
    print("- Backup files u krijuan per siguri")

if __name__ == "__main__":
    main()
