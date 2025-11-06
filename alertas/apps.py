from django.apps import AppConfig

class AlertaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'alertas'

    def ready(self):
        # Importación diferida para evitar problemas de importación circular
        # Solo importar señales cuando Django esté completamente cargado
        try:
            import alertas.signals
        except ImportError as e:
            # Si hay un error de importación, lo ignoramos temporalmente para las migraciones
            print(f"⚠️ No se pudieron cargar las señales: {e}")
            pass