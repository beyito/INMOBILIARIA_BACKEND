# usuario/management/commands/create_agente_cliente_full.py
from django.core.management.base import BaseCommand
from usuario.models import Usuario, Grupo, Componente, Privilegio

class Command(BaseCommand):
    help = "Seed inicial: 1 cliente y 1 agente con permisos sobre Chat y Mensaje"

    def handle(self, *args, **kwargs):
        # --------------------------
        # 1️⃣ Crear grupos
        # --------------------------
        grupo_agente, _ = Grupo.objects.get_or_create(nombre="agente", defaults={"descripcion": "Grupo de agentes"})
        grupo_cliente, _ = Grupo.objects.get_or_create(nombre="Cliente", defaults={"descripcion": "Grupo de clientes"})

        # --------------------------
        # 2️⃣ Crear usuarios
        # --------------------------
        agente, created = Usuario.objects.get_or_create(
            username="juan_agente",
            defaults={"nombre": "Juan Agente", "correo": "juan@inmobiliaria.com", "grupo": grupo_agente, "is_staff": True}
        )
        if created:
            agente.set_password("123456")
            agente.save()

        cliente, created = Usuario.objects.get_or_create(
            username="maria_cliente",
            defaults={"nombre": "Maria Cliente", "correo": "maria@cliente.com", "grupo": grupo_cliente}
        )
        if created:
            cliente.set_password("123456")
            cliente.save()

        # --------------------------
        # 3️⃣ Crear componentes Chat y Mensaje
        # --------------------------
        componentes = ["Chat", "Mensaje"]
        for c in componentes:
            Componente.objects.get_or_create(nombre=c)

        # --------------------------
        # 4️⃣ Asignar privilegios a cada grupo
        # --------------------------
        for grupo in [grupo_agente, grupo_cliente]:
            for componente in Componente.objects.filter(nombre__in=componentes):
                Privilegio.objects.update_or_create(
                    grupo=grupo,
                    componente=componente,
                    defaults={
                        "puede_leer": True,
                        "puede_crear": True,
                        "puede_actualizar": False,
                        "puede_eliminar": False,
                        "puede_activar": False
                    }
                )

        self.stdout.write(self.style.SUCCESS("Seed completado: 1 Agente y 1 Cliente con permisos sobre Chat y Mensaje"))
