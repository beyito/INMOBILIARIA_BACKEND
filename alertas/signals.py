# alertas/signals.py (CÓDIGO CORREGIDO PARA ROMPER LA DEPENDENCIA)

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.apps import apps # Necesario para get_model
# Importación de la vista movida dentro del handler para evitar circular imports

@receiver(post_save)
def crear_alertas_post_contrato_guardado(sender, instance, created, **kwargs):
    
    # 🟢 OBTENER EL MODELO CONTRATO DE FORMA SEGURA DENTRO DEL HANDLER
    try:
        # Esto es seguro porque las apps ya habrán terminado de cargar.
        ContratoModel = apps.get_model('contrato', 'Contrato')
    except LookupError:
        return # Salir si el modelo Contrato aún no está cargado.
        
    # 🟢 VERIFICAR SI EL OBJETO QUE SE HA GUARDADO ES EL MODELO CONTRATO
    if sender is ContratoModel:
        
        # 3. Lógica de la señal (instance es el Contrato recién guardado)
        if instance.tipo_contrato in ['alquiler', 'anticretico'] and instance.estado == 'activo':
            
            print(f"🔔 Señal POST_SAVE detectada para Contrato ID: {instance.id}. Disparando lógica de alertas...")

            # Simulamos un objeto request para la vista del cron job
            from rest_framework.test import APIRequestFactory
            rf = APIRequestFactory()
            fake_request = rf.post('/alertas/ejecutar-generacion/')
            
            try:
                # Importar localmente para evitar circular imports al cargar la app
                from .views import cron_generar_alertas
                # Llamamos a la función del cron job (que ya está en views.py)
                cron_generar_alertas(fake_request)
                print("✅ Generación de alertas completada por SIGNAL.")
            except Exception as e:
                 print(f"❌ Error al ejecutar cron_generar_alertas desde la señal: {e}")