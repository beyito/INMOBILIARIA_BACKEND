# ventas/serializers.py
from rest_framework import serializers
from .models import VentaInmueble
from inmueble.models import InmuebleModel
from usuario.serializers import UsuarioSerializer


class InmuebleMiniSerializer(serializers.ModelSerializer):
    foto_portada = serializers.SerializerMethodField()

    class Meta:
        model = InmuebleModel
        fields = [
            "id",
            "titulo",
            "precio",
            "direccion",
            "foto_portada",
        ]

    def get_foto_portada(self, obj):
        primera_foto = obj.fotos.first()
        return primera_foto.url if primera_foto else None



class VentaInmuebleSerializer(serializers.ModelSerializer):
    comprador = UsuarioSerializer(read_only=True)
    inmueble = InmuebleMiniSerializer(read_only=True)

    class Meta:
        model = VentaInmueble
        fields = [
            "id",
            "comprador",
            "inmueble",
            "monto",
            "metodo_pago",
            "estado_pago",
            "transaccion_id",
            "fecha",
        ]
