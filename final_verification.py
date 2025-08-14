# final_verification.py - Verifikim final i sistemit

import os

def main():
    print("=" * 50)
    print("VERIFIKIM FINAL I RREGULLIMEVE")
    print("=" * 50)
    
    # Lista e kontrollave
    checks = []
    
    # 1. Check dashboard_views.py rregullimi
    dashboard_file = "C:/GPT4_PROJECTS/JURISTI/legal_manager/cases/dashboard_views.py"
    if os.path.exists(dashboard_file):
        with open(dashboard_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if "Sum('paid')" not in content:
            checks.append(("✅", "Sum('paid') u hoq nga dashboard_views.py"))
        else:
            checks.append(("❌", "Sum('paid') akoma ekziston në dashboard_views.py"))
            
        if "Count('id', filter=Q(paid=True))" in content:
            checks.append(("✅", "Agregimi i saktë u shtua në dashboard_views.py"))
        else:
            checks.append(("❌", "Agregimi i saktë mungon në dashboard_views.py"))
            
        if "Coalesce" in content and "DecimalField" in content:
            checks.append(("✅", "Coalesce dhe DecimalField në vend"))
        else:
            checks.append(("⚠️", "Coalesce ose DecimalField mund të mungojnë"))
    else:
        checks.append(("❌", "dashboard_views.py nuk u gjet"))
    
    # 2. Check backup file
    backup_file = "C:/GPT4_PROJECTS/JURISTI/legal_manager/cases/dashboard_views_backup.py"
    if os.path.exists(backup_file):
        checks.append(("✅", "Backup file u krijua me sukses"))
    else:
        checks.append(("⚠️", "Backup file nuk u gjet"))
    
    # 3. Check template filters
    filters_file = "C:/GPT4_PROJECTS/JURISTI/legal_manager/cases/templatetags/dashboard_filters.py"
    if os.path.exists(filters_file):
        with open(filters_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if "def replace(" in content and "def humanize_field_name(" in content:
            checks.append(("✅", "Custom filters u krijuan me sukses"))
        else:
            checks.append(("❌", "Custom filters janë të paplotë"))
    else:
        checks.append(("❌", "dashboard_filters.py nuk u gjet"))
    
    # 4. Check template update
    template_file = "C:/GPT4_PROJECTS/JURISTI/templates/dashboard/enhanced_index.html"
    if os.path.exists(template_file):
        with open(template_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if "{% load dashboard_filters %}" in content:
            checks.append(("✅", "Dashboard filters u ngarkuan në template"))
        else:
            checks.append(("❌", "Dashboard filters nuk u ngarkuan në template"))
            
        if "|replace:" not in content:
            checks.append(("✅", "Replace filter u hoq nga template"))
        else:
            checks.append(("❌", "Replace filter akoma ekziston në template"))
            
        if "humanize_field_name" in content:
            checks.append(("✅", "Humanize_field_name filter në përdorim"))
        else:
            checks.append(("⚠️", "Humanize_field_name filter nuk është në përdorim"))
    else:
        checks.append(("❌", "enhanced_index.html nuk u gjet"))
    
    # 5. Check widgets directory
    widgets_dir = "C:/GPT4_PROJECTS/JURISTI/templates/dashboard/widgets"
    if os.path.exists(widgets_dir):
        checks.append(("✅", "Widgets directory u krijua"))
        
        progress_bar = f"{widgets_dir}/progress_bar.html"
        if os.path.exists(progress_bar):
            checks.append(("✅", "Progress bar template u krijua"))
        else:
            checks.append(("⚠️", "Progress bar template mungon"))
    else:
        checks.append(("❌", "Widgets directory mungon"))
    
    # Print results
    print("\nRezultatet e kontrollit:")
    print("-" * 50)
    
    success_count = 0
    warning_count = 0
    error_count = 0
    
    for status, message in checks:
        print(f"{status} {message}")
        if status == "✅":
            success_count += 1
        elif status == "⚠️":
            warning_count += 1
        elif status == "❌":
            error_count += 1
    
    print("\n" + "=" * 50)
    print("PËRMBLEDHJE")
    print("=" * 50)
    print(f"Sukses: {success_count}")
    print(f"Paralajmërime: {warning_count}")
    print(f"Gabime: {error_count}")
    
    if error_count == 0:
        print("\n🎉 TË GJITHA RREGULLIMET U APLIKUAN ME SUKSES!")
        print("\nHapa e ardhshem:")
        print("1. Fillo serverin: python manage.py runserver")
        print("2. Testo dashboard: http://localhost:8000/dashboard/")
        print("3. Nëse funksionon, rregullimet janë të suksesshme!")
    else:
        print(f"\n⚠️ KA {error_count} GABIME QË DUHEN RREGULLUAR")
        print("Kontrolloni gabimet më sipër dhe rregullojini.")
    
    if warning_count > 0:
        print(f"\n💡 Ka {warning_count} paralajmërime jo-kritike")
        print("Sistemi duhet të funksionojë pavarësisht paralajmërimeve.")

if __name__ == "__main__":
    main()
