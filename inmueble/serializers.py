# serializers.py
from rest_framework import serializers
from .models import InmuebleModel, TipoInmuebleModel, CambioInmuebleModel
from usuario.models import Usuario
from usuario.serializers import UsuarioSerializer
class TipoInmuebleSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoInmuebleModel
        fields = '__all__'

class InmuebleSerializer(serializers.ModelSerializer):
    tipo_inmueble = TipoInmuebleSerializer(read_only=True)
    tipo_inmueble_id = serializers.PrimaryKeyRelatedField(
        queryset=TipoInmuebleModel.objects.all(),
        source='tipo_inmueble',
        write_only=True
    )

    class Meta:
        model = InmuebleModel
        fields = '__all__'

class CambioInmuebleSerializer(serializers.ModelSerializer):
    inmueble = serializers.StringRelatedField(read_only=True)  # mostrar info del inmueble
    estado = serializers.CharField(read_only=True)
    fecha_solicitud = serializers.DateField(read_only=True)
    fecha_revision = serializers.DateField(read_only=True, allow_null=True)
    class Meta:
        model = CambioInmuebleModel
        fields = [
            "id",
            "inmueble",
            "agente",
            "titulo",
            "descripcion",
            "direccion",
            "ciudad",
            "zona",
            "superficie",
            "dormitorios",
            "baños",
            "precio",
            "tipo_operacion",
            "estado",
            "latitud",
            "longitud",
            "fecha_solicitud",
            "fecha_revision"
        ]