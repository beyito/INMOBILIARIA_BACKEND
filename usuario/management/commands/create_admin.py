# usuario/management/commands/create_admin_full.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from usuario.models import Grupo, Componente, Privilegio, Usuario

class Command(BaseCommand):
    help = "Crea el usuario admin, componentes y asigna todos los privilegios"

    def handle(self, *args, **kwargs):
        User = get_user_model()

        # --------------------------
        # 1️⃣ Crear componentes base
        # --------------------------
        # usuario/management/commands/create_admin_full.py
        componentes = ["Usuario", "Grupo", "Componente", "Privilegio", "Chat", "Mensaje"]

        for c in componentes:
            Componente.objects.get_or_create(nombre=c)

        # --------------------------
        # 2️⃣ Crear grupo Administrador
        # --------------------------
        admin_group, _ = Grupo.objects.get_or_create(
            nombre="Administrador",
            defaults={"descripcion": "Grupo con todos los privilegios"}
        )

        # --------------------------
        # 3️⃣ Crear superuser admin
        # --------------------------
        if not User.objects.filter(username='admin').exists():
            admin_user = User.objects.create_superuser(
                username='admin',
                password='admin123',  # cambiar contraseña si quieres
                email='admin@example.com',
                nombre='Administrador'
            )
            admin_user.grupo = admin_group
            admin_user.save()
            self.stdout.write(self.style.SUCCESS("Admin creado correctamente"))
        else:
            admin_user = User.objects.get(username='admin')
            admin_user.grupo = admin_group
            admin_user.save()
            self.stdout.write(self.style.WARNING("Admin ya existía, se actualizó su grupo"))

        # --------------------------
        # 4️⃣ Asignar todos los privilegios
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

        self.stdout.write(self.style.SUCCESS("Privilegios asignados al grupo Administrador"))
