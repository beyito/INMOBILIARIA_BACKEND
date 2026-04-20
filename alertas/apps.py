# alertas/apps.py

from django.apps import AppConfig


class AlertasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'alertas'
    
    # 🟢 CONECTOR: Este método carga las señales
    def ready(self):
        import alertas.signals