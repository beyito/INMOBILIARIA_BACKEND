# usuario/management/commands/create_admin.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from usuario.models import Grupo, Componente, Privilegio

class Command(BaseCommand):
    help = "Crea el usuario admin, los componentes base y asigna todos los privilegios al grupo administrador"

    def handle(self, *args, **kwargs):
        User = get_user_model()

        # --------------------------
        # 1️⃣ Crear componentes base
        # --------------------------
        componentes = ["usuario", "grupo", "componente", "privilegio", "chat", "mensaje"]
        for c in componentes:
            Componente.objects.get_or_create(nombre=c.lower())

        # --------------------------
        # 2️⃣ Crear grupo administrador (en minúsculas)
        # --------------------------
        admin_group, _ = Grupo.objects.get_or_create(
            nombre="administrador",
            defaults={"descripcion": "Grupo con todos los privilegios"}
        )

        # --------------------------
        # 3️⃣ Crear o actualizar usuario admin
        # --------------------------
        admin_user, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@example.com",
                "nombre": "Administrador",
                "is_staff": True,
                "is_superuser": True,
                "grupo": admin_group
            }
        )

        if created:
            admin_user.set_password("admin123")
            admin_user.save()
            self.stdout.write(self.style.SUCCESS("✅ Usuario admin creado correctamente"))
        else:
            admin_user.grupo = admin_group
            admin_user.is_superuser = True
            admin_user.is_staff = True
            admin_user.save()
            self.stdout.write(self.style.WARNING("⚠️ Usuario admin ya existía, se actualizó su grupo y permisos"))

        # --------------------------
        # 4️⃣ Asignar privilegios completos al grupo administrador
        # --------------------------
        for componente in Componente.objects.all():
            Privilegio.objects.update_or_create(
                grupo=admin_group,
                componente=componente,
                defaults={
                    "puede_leer": True,
                    "puede_crear": True,
                    "puede_actualizar": True,
                    "puede_eliminar": True,
                    "puede_activar": True
                }
            )

        self.stdout.write(self.style.SUCCESS("🚀 Privilegios asignados al grupo 'administrador'"))
