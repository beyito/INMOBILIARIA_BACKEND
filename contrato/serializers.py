# serializers.py
from rest_framework import serializers
from .models import Contrato

class ContratoSerializer(serializers.ModelSerializer):
    agente_nombre = serializers.CharField(source='agente.nombre', read_only=True)
    inmueble_direccion = serializers.CharField(source='inmueble.direccion', read_only=True)
    tipo_contrato_display = serializers.CharField(source='get_tipo_contrato_display', read_only=True)
    
    class Meta:
        model = Contrato
        fields = '__all__'