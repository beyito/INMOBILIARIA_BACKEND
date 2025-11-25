# suscripciones/serializers.py

from rest_framework import serializers
from django.utils import timezone  # 👈 ESTA ES LA LÍNEA IMPORTANTE (CORREGIDA)
from .models import Plan, Suscripcion

class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = '__all__'

class SuscripcionSerializer(serializers.ModelSerializer):
    # Mostramos los detalles del plan dentro de la suscripción para que el frontend sepa qué mostrar
    plan_detalle = PlanSerializer(source='plan', read_only=True)
    
    # Campo calculado para saber cuánto le queda
    dias_restantes = serializers.SerializerMethodField()

    class Meta:
        model = Suscripcion
        fields = ['id', 'plan', 'plan_detalle', 'fecha_inicio', 'fecha_fin', 'estado', 'dias_restantes']
        read_only_fields = ['fecha_fin', 'fecha_inicio']

    def get_dias_restantes(self, obj):
        # Verificamos si está activa y si tiene fecha fin válida
        if not obj.esta_activa or not obj.fecha_fin:
            return 0
        
        # Aquí estaba fallando: timezone.now() requiere el import correcto
        delta = obj.fecha_fin - timezone.now()
        return max(delta.days, 0)