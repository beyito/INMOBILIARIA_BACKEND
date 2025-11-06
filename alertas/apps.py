# alerta/apps.py

from django.apps import AppConfig

class AlertaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'alertas'

    def ready(self):
        # Cargar el archivo de señales al iniciar la aplicación
        import alertas.signals # Asume que tu archivo de señales se llama signals.py