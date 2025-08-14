from django.apps import AppConfig

class CasesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'legal_manager.cases'
    label = 'cases'
    verbose_name = 'Legal Case Management'

    def ready(self):
        import legal_manager.cases.signals  # noqa
