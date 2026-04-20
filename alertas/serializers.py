# alertas/serializers.py

from rest_framework import serializers
from .models import AlertaModel

class AlertaSerializer(serializers.ModelSerializer):
    # Incluimos información de solo lectura del contrato asociado
    contrato_tipo = serializers.CharField(source='contrato.get_tipo_contrato_display', read_only=True)
    contrato_agente = serializers.CharField(source='contrato.agente.nombre', read_only=True)
    
    class Meta:
        model = AlertaModel
        fields = '__all__'