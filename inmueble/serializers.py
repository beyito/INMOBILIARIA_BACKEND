# inmueble/serializers.py
from rest_framework import serializers
from .models import InmuebleModel, TipoInmuebleModel, CambioInmuebleModel, FotoModel,AnuncioModel
from usuario.models import Usuario
from usuario.serializers import UsuarioSerializer


class TipoInmuebleSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoInmuebleModel
        fields = "__all__"


class FotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = FotoModel
        fields = ["id", "url", "descripcion", "fecha_creacion", "is_active"]

class AnuncioLiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnuncioModel
        fields = ("id", "estado", "is_active", "fecha_publicacion")

class InmuebleSerializer(serializers.ModelSerializer):
    fotos = FotoSerializer(many=True, read_only=True)  # related_name='fotos'
    tipo_inmueble = TipoInmuebleSerializer(read_only=True)
    anuncio = AnuncioLiteSerializer(read_only=True)
    tipo_inmueble_id = serializers.PrimaryKeyRelatedField(
        queryset=TipoInmuebleModel.objects.all(),
        source="tipo_inmueble",
        write_only=True,
    )

    class Meta:
        model = InmuebleModel
        fields = "__all__"


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
            "fecha_revision",
        ]


class FotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = FotoModel
        fields = ("id", "url", "descripcion")

class InmuebleListSerializer(serializers.ModelSerializer):
    anuncio = AnuncioLiteSerializer(read_only=True)
    fotos = FotoSerializer(many=True, read_only=True)

    class Meta:
        model = InmuebleModel
        fields = (
            "id", "titulo", "descripcion", "direccion", "ciudad", "zona",
            "precio", "tipo_operacion", "estado", "anuncio", "fotos"
        )

class AnuncioUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnuncioModel
        fields = ("id", "estado", "is_active")
        extra_kwargs = {
            "estado": {"required": False},
            "is_active": {"required": False},
        }

# En tu serializers.py
class AnuncioSerializer(serializers.ModelSerializer):
    inmueble_info = serializers.SerializerMethodField()
    agente_info = serializers.SerializerMethodField()
    
    class Meta:
        model = AnuncioModel
        fields = [
            'id', 'inmueble', 'inmueble_info', 'estado', 'prioridad', 
            'is_active', 'fecha_publicacion', 'agente_info'
        ]
    
    def get_inmueble_info(self, obj):
        """Devuelve toda la información del inmueble"""
        inmueble = obj.inmueble
        if not inmueble:
            return None
            
        return {
            'id': inmueble.id,
            'titulo': inmueble.titulo,
            'descripcion': inmueble.descripcion,
            'direccion': inmueble.direccion,
            'ciudad': inmueble.ciudad,
            'zona': inmueble.zona,
            'superficie': str(inmueble.superficie),
            'dormitorios': inmueble.dormitorios,
            'baños': inmueble.baños,
            'precio': str(inmueble.precio),
            'tipo_operacion': inmueble.tipo_operacion,
            'latitud': str(inmueble.latitud) if inmueble.latitud else None,
            'longitud': str(inmueble.longitud) if inmueble.longitud else None,
            'tipo_inmueble': {
                'id': inmueble.tipo_inmueble.id,
                'nombre': inmueble.tipo_inmueble.nombre,
                'descripcion': inmueble.tipo_inmueble.descripcion
            } if inmueble.tipo_inmueble else None,
            'fotos': [
                {
                    'id': foto.id,
                    'url': foto.url if foto.url else None,
                    'descripcion': foto.descripcion
                } for foto in inmueble.fotos.all()
            ] if hasattr(inmueble, 'fotos') else []
        }
        
    def get_agente_info(self, obj):
            """Información del agente"""
            if obj.inmueble and obj.inmueble.agente:
                agente = obj.inmueble.agente
                return {
                    'id': agente.id,
                    'nombre': agente.nombre,    
                    'email': agente.correo,       
                    'telefono': agente.telefono   
                }
            return None
