from rest_framework import serializers
from .models import AlertConfig, Alerta

class AlertConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertConfig
        fields = ['contrato', 'dias_recordatorio', 'canal_email', 'canal_push', 'activo']
        read_only_fields = ['contrato']

class AlertaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alerta
        fields = ['id','contrato','tipo','titulo','descripcion','due_date','periodo_index','estado','creado','actualizado']
        read_only_fields = ['creado','actualizado']
