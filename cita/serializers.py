from datetime import date
from django.utils import timezone
from django.db import models
from rest_framework import serializers
from .models import Cita, DisponibilidadAgente, TipoTramite
from datetime import date

# Serializer simple para el catálogo "TipoTramite"
class TipoTramiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoTramite 
        fields = ["id", "nombre", "descripcion", "is_activo", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

# Serializer para Disponibilidad del Agente
class DisponibilidadAgenteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DisponibilidadAgente 
        fields = [
            "id", "agente", "dia_semana", "hora_inicio", "hora_fin",
            "valido_desde", "valido_hasta", "is_activo",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        hi = attrs.get("hora_inicio", getattr(self.instance, "hora_inicio", None))
        hf = attrs.get("hora_fin",    getattr(self.instance, "hora_fin", None))
        if hi and hf and not (hf > hi):
            raise serializers.ValidationError("hora_fin debe ser mayor que hora_inicio.")
        return attrs

#función utilitaria para detectar solapamientos de horarios
def _overlaps(h1_start, h1_end, h2_start, h2_end) -> bool:
    """
    Regla clásica de solapamiento con intervalos [inicio, fin):
    Se solapan si: (start1 < end2) AND (end1 > start2)
    """
    return (h1_start < h2_end) and (h1_end > h2_start)


# Serializer principal para Cita
class CitaSerializer(serializers.ModelSerializer):
    tramite = serializers.PrimaryKeyRelatedField(queryset=TipoTramite.objects.filter(is_activo=True))

    class Meta:
        model = Cita  
        fields = [
            "id",
            "titulo", "descripcion",
            "fecha_cita", "hora_inicio", "hora_fin",
            "estado",
            "cliente", "agente", "creado_por",
            "tramite",
            "created_at", "updated_at",
        ]
        # El cliente NO puede setear estos: los define el backend
        read_only_fields = ["id", "agente", "creado_por", "created_at", "updated_at"]

    # -------------------- VALIDACIONES DE NEGOCIO --------------------
    def validate(self, attrs):
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            raise serializers.ValidationError("Autenticación requerida.")
        # En create: usa request.user; en update: valida contra el agente de la cita ya existente
        agente = getattr(self.instance, "agente", request.user)

        fecha_cita = attrs.get("fecha_cita", getattr(self.instance, "fecha_cita", None))
        hi = attrs.get("hora_inicio", getattr(self.instance, "hora_inicio", None))
        hf = attrs.get("hora_fin",    getattr(self.instance, "hora_fin", None))
        cliente = attrs.get("cliente", getattr(self.instance, "cliente", None))
        tramite = attrs.get("tramite", getattr(self.instance, "tramite", None))

        if fecha_cita < date.today():
         raise serializers.ValidationError("No se pueden crear citas en fechas pasadas.")

        if not (fecha_cita and hi and hf and cliente and tramite):
            raise serializers.ValidationError("fecha_cita, hora_inicio, hora_fin, cliente y tramite son requeridos.")

        if not (hf > hi):
            raise serializers.ValidationError("hora_fin debe ser mayor que hora_inicio.")

        dow = fecha_cita.weekday()
        # Buscamos disponibilidades del MISMO agente, ese día de semana, activas
        disp_qs = DisponibilidadAgente.objects.filter(
            agente=agente,
            dia_semana=dow,
            is_activo=True,
        )
        disp_qs = disp_qs.filter(
            models.Q(valido_desde__isnull=True) | models.Q(valido_desde__lte=fecha_cita),
            models.Q(valido_hasta__isnull=True) | models.Q(valido_hasta__gte=fecha_cita),
        )

        contiene = False
        for d in disp_qs:
            if (d.hora_inicio <= hi) and (hf <= d.hora_fin):
                contiene = True
                break
        if not contiene:
            raise serializers.ValidationError(
                "La cita no cae dentro de una franja de disponibilidad activa del agente para ese día."
            )
        qs = Cita.objects.filter(
            agente=agente,           
            fecha_cita=fecha_cita,  
        ).exclude(estado=Cita.ESTADO_CANCELADA)  

        instance = getattr(self, "instance", None)
        if instance and instance.pk:
            qs = qs.exclude(pk=instance.pk)
        for other in qs.only("hora_inicio", "hora_fin"):
            if _overlaps(hi, hf, other.hora_inicio, other.hora_fin):
                raise serializers.ValidationError("El horario se solapa con otra cita del agente en ese día.")

        return attrs

    def create(self, validated_data):
        """
        Forzamos la regla: el agente que crea es el request.user.
        """
        user = self.context["request"].user 
        validated_data["agente"] = user   
        validated_data["creado_por"] = user 
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """
        Evitar que se reasigne el agente/creado_por por API.
        """
        validated_data.pop("agente", None)     
        validated_data.pop("creado_por", None) 
        return super().update(instance, validated_data)
