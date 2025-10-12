# serializers.py
from rest_framework import serializers
from .models import InmuebleModel, TipoInmuebleModel, CambioInmuebleModel, FotoModel, AnuncioModel
from usuario.models import Usuario
from usuario.serializers import UsuarioSerializer
class TipoInmuebleSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoInmuebleModel
        fields = '__all__'

class FotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = FotoModel
        fields = ['id', 'url', 'descripcion', 'fecha_creacion', 'is_active']
        
class InmuebleSerializer(serializers.ModelSerializer):
    fotos = FotoSerializer(many=True, read_only=True)  # related_name='fotos'
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

# serializers.py
class AnuncioSerializer(serializers.ModelSerializer):
    inmueble_info = serializers.SerializerMethodField(read_only=True)
    agente_info = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = AnuncioModel
        fields = [
            'id',
            'inmueble',
            'inmueble_info',
            'agente_info',
            'fecha_publicacion', 
            'estado',
            'prioridad', 
            'is_active'
        ]
        read_only_fields = ['fecha_publicacion']

    def get_inmueble_info(self, obj):
        return {
            'id': obj.inmueble.id,
            'titulo': obj.inmueble.titulo,
            'precio': obj.inmueble.precio,
            'tipo_operacion': obj.inmueble.tipo_operacion,
            'ciudad': obj.inmueble.ciudad,
            'zona': obj.inmueble.zona,
            'fotos': [foto.url for foto in obj.inmueble.fotos.filter(is_active=True)]
        }

    def get_agente_info(self, obj):
        return {
            'id': obj.inmueble.agente.id,
            'nombre': f"{obj.inmueble.agente.nombre}",
        }