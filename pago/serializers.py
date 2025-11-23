# pago/serializers.py

from rest_framework import serializers
from .models import Pago, ComprobantePago 

# -------------------------------------------------------------
# Serializador de Comprobante (Anidado)
# -------------------------------------------------------------
class ComprobantePagoSerializer(serializers.ModelSerializer):
    # Asumo que existe un método o campo 'nombre' en Usuario
    usuario_registro_nombre = serializers.ReadOnlyField(source='usuario_registro.nombre') 
    
    class Meta:
        model = ComprobantePago
        fields = ('archivo_comprobante', 'fecha_registro', 'usuario_registro_nombre', 'observaciones')
        read_only_fields = fields

# -------------------------------------------------------------
# Serializador de Pago (Principal)
# -------------------------------------------------------------
class PagoSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.ReadOnlyField(source='cliente.nombre')
    comprobante = ComprobantePagoSerializer(read_only=True)

    class Meta:
        model = Pago
        fields = (
            'id', 'contrato', 'cliente', 'cliente_nombre', 'monto_pagado',
            'fecha_pago', 'metodo', 'estado', 'referencia_transaccion',
            'comprobante'
        )
        read_only_fields = ('id', 'contrato', 'cliente', 'cliente_nombre', 'fecha_pago', 'referencia_transaccion', 'comprobante')

# -------------------------------------------------------------
# Serializador de Gestión (Para confirmar/rechazar)
# -------------------------------------------------------------
class PagoGestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pago
        fields = ('id', 'estado', 'referencia_transaccion', 'monto_pagado', 'metodo')
        read_only_fields = ('id', 'monto_pagado', 'metodo')