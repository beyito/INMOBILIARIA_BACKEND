from rest_framework import serializers

from .models import Usuario,Grupo, Componente, Privilegio, SolicitudAgente  

class GrupoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Grupo
        fields = ['id', 'nombre', 'descripcion']

class UsuarioSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    grupo_id = serializers.IntegerField(required=False, allow_null=True)  # 👈 se envía y también se devuelve
    grupo_nombre = serializers.CharField(source='grupo.nombre', read_only=True)

    class Meta:
        model = Usuario
        fields = [
            'id', 'nombre', 'username', 'password', 'correo',
            'grupo_id', 'grupo_nombre', 'ci', 'telefono',
            'ubicacion', 'fecha_nacimiento', 'is_active', 'is_staff'
        ]
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def create(self, validated_data):
        grupo_id = validated_data.pop('grupo_id', None)
        password = validated_data.pop('password')
        usuario = Usuario(**validated_data)

        if grupo_id:
            grupo = Grupo.objects.get(id=grupo_id)
            usuario.grupo = grupo

        usuario.set_password(password)
        usuario.save()
        return usuario

    def update(self, instance, validated_data):
        grupo_id = validated_data.pop('grupo_id', None)
        password = validated_data.pop('password', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if grupo_id:
            grupo = Grupo.objects.get(id=grupo_id)
            instance.grupo = grupo

        if password:
            instance.set_password(password)

        instance.save()
        return instance
    
class ComponenteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Componente
        fields = ['id', 'nombre']

class PrivilegioSerializer(serializers.ModelSerializer):
    grupo = GrupoSerializer(read_only=True)
    grupo_id = serializers.PrimaryKeyRelatedField(
        queryset=Grupo.objects.all(), source='grupo', write_only=True
    )
    componente = ComponenteSerializer(read_only=True)
    componente_id = serializers.PrimaryKeyRelatedField(
        queryset=Componente.objects.all(), source='componente', write_only=True
    )

    class Meta:
        model = Privilegio
        fields = [
            'id', 'grupo', 'grupo_id', 'componente', 'componente_id',
            'puede_leer', 'puede_crear', 'puede_activar', 'puede_actualizar', 'puede_eliminar'
        ]  


class PasswordResetRequestSerializer(serializers.Serializer):
    correo = serializers.EmailField()


class PasswordResetVerifyCodeSerializer(serializers.Serializer):
    correo = serializers.EmailField()
    code = serializers.CharField(max_length=6)


class SetNewPasswordSerializer(serializers.Serializer):
    correo = serializers.EmailField()
    password = serializers.CharField(min_length=6, write_only=True)

class SolicitudAgenteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SolicitudAgente
        fields = '__all__'

    def validate_correo(self, value):
        # Verifica que el correo no esté vacío
        if not value:
            raise serializers.ValidationError("El correo no puede estar vacío")
        # Verifica que no exista otra solicitud con el mismo correo
        if SolicitudAgente.objects.filter(correo=value).exists():
            raise serializers.ValidationError("Ya existe una solicitud con este correo")
        return value

    def create(self, validated_data):
        # Creamos la solicitud de agente
        solicitud = SolicitudAgente.objects.create(**validated_data)
        return solicitud

# class RolSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Rol
#         fields = ["idRol", "nombre", "created_at", "updated_at"] 

