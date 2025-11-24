# contrato/serializers.py
from rest_framework import serializers
from .models import Contrato

class ContratoSerializer(serializers.ModelSerializer):
    agente_nombre = serializers.CharField(source='agente.nombre', read_only=True)
    inmueble_direccion = serializers.CharField(source='inmueble.direccion', read_only=True)
    tipo_contrato_display = serializers.CharField(source='get_tipo_contrato_display', read_only=True)
    
    class Meta:
        model = Contrato
        fields = '__all__'

class ContratoAlquilerSerializer(serializers.ModelSerializer):
    inmueble_direccion = serializers.CharField(source='inmueble.direccion', read_only=True)
    inmueble_ciudad = serializers.CharField(source='inmueble.ciudad', read_only=True)
    
    class Meta:
        model = Contrato
        fields = [
            'id',
            'tipo_contrato',
            'estado',
            'ciudad',
            'fecha_contrato',
            'fecha_inicio',
            'fecha_fin',
            'monto',
            'vigencia_meses',
            'inmueble_direccion',
            'inmueble_ciudad',
            'parte_contratante_nombre',
            'parte_contratada_nombre',
            'archivo_pdf'
        ]