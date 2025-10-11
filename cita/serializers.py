from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Q
from .models import Cita

User = get_user_model()


class CitaSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.SerializerMethodField(read_only=True)
    agente_nombre = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Cita
        fields = [
            "id",
            "titulo",
            "descripcion",
            "fecha_cita",
            "hora_inicio",
            "hora_fin",
            "estado",
            "cliente",
            "agente",
            "creado_por",
            "cliente_nombre",
            "agente_nombre",
            "creado_en",
            "actualizado_en",
        ]
        read_only_fields = ["agente", "creado_por", "creado_en", "actualizado_en"]

    def get_cliente_nombre(self, obj):
        return getattr(obj.cliente, "get_full_name", lambda: "")() or getattr(obj.cliente, "username", "")

    def get_agente_nombre(self, obj):
        return getattr(obj.agente, "get_full_name", lambda: "")() or getattr(obj.agente, "username", "")

    # ✅ Se asignan automáticamente agente y creado_por desde request.user
    def create(self, validated_data):
        user = self.context["request"].user
        validated_data.setdefault("agente", user)
        validated_data.setdefault("creado_por", user)
        return super().create(validated_data)

    def validate(self, data):
        # valores efectivos (soporta create y update parcial)
        user = self.context.get("request").user if self.context.get("request") else None
        agente = data.get("agente") or getattr(self.instance, "agente", None) or user
        cliente = data.get("cliente") or getattr(self.instance, "cliente", None)
        fecha = data.get("fecha_cita") or getattr(self.instance, "fecha_cita", None)
        h_ini = data.get("hora_inicio") or getattr(self.instance, "hora_inicio", None)
        h_fin = data.get("hora_fin") or getattr(self.instance, "hora_fin", None)

        if h_ini and h_fin and h_ini >= h_fin:
            raise serializers.ValidationError("La hora de inicio debe ser menor que la hora fin.")

        # si faltan datos (en update parcial) salimos y dejamos que los required hagan su trabajo
        if not all([agente, cliente, fecha, h_ini, h_fin]):
            return data

        # excluir canceladas y a sí misma
        qs = Cita.objects.exclude(estado="CANCELADA")
        if self.instance:
            qs = qs.exclude(id=self.instance.id)

        # condición de solape: ini_nuevo < fin_existente && fin_nuevo > ini_existente
        overlap = Q(fecha_cita=fecha, hora_inicio__lt=h_fin, hora_fin__gt=h_ini)

        # evitar doble booking para el agente
        if qs.filter(overlap, agente=agente).exists():
            raise serializers.ValidationError(
                {"hora_inicio": "El AGENTE tiene otra cita que se solapa en ese horario."}
            )

        # (opcional) evitar solape para el cliente
        if qs.filter(overlap, cliente=cliente).exists():
            raise serializers.ValidationError(
                {"hora_inicio": "El CLIENTE tiene otra cita que se solapa en ese horario."}
            )

        return data
