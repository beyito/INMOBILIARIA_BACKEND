# usuario/management/commands/seed.py
from django.core.management.base import BaseCommand
from usuario.models import Usuario, Grupo, Componente, Privilegio

class Command(BaseCommand):
    help = "Crea usuarios de prueba (agente y cliente) y les asigna permisos sobre Chat y Mensaje"

    def handle(self, *args, **kwargs):
        # --------------------------
        # 1️⃣ Crear grupos base (en minúsculas)
        # --------------------------
        grupo_agente, _ = Grupo.objects.get_or_create(
            nombre="agente",
            defaults={"descripcion": "Grupo de agentes"}
        )
        grupo_cliente, _ = Grupo.objects.get_or_create(
            nombre="cliente",
            defaults={"descripcion": "Grupo de clientes"}
        )

        # --------------------------
        # 2️⃣ Crear usuarios base
        # --------------------------
        agente, creado_agente = Usuario.objects.get_or_create(
            username="juan_agente",
            defaults={
                "nombre": "Juan Agente",
                "correo": "juan@inmobiliaria.com",
                "grupo": grupo_agente,
                "is_staff": True
            }
        )
        if creado_agente:
            agente.set_password("123456")
            agente.save()
            self.stdout.write(self.style.SUCCESS("✅ Usuario agente creado correctamente"))
        else:
            agente.grupo = grupo_agente
            agente.save()
            self.stdout.write(self.style.WARNING("⚠️ Usuario agente ya existía, se actualizó su grupo"))

        cliente, creado_cliente = Usuario.objects.get_or_create(
            username="maria_cliente",
            defaults={
                "nombre": "Maria Cliente",
                "correo": "maria@cliente.com",
                "grupo": grupo_cliente
            }
        )
        if creado_cliente:
            cliente.set_password("123456")
            cliente.save()
            self.stdout.write(self.style.SUCCESS("✅ Usuario cliente creado correctamente"))
        else:
            cliente.grupo = grupo_cliente
            cliente.save()
            self.stdout.write(self.style.WARNING("⚠️ Usuario cliente ya existía, se actualizó su grupo"))

        # --------------------------
        # 3️⃣ Crear componentes base
        # --------------------------
        componentes = ["chat", "mensaje"]
        for c in componentes:
            Componente.objects.get_or_create(nombre=c.lower())

        # --------------------------
        # 4️⃣ Asignar privilegios
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

        self.stdout.write(self.style.SUCCESS("🚀 Seed completado: Agente y Cliente creados con privilegios básicos"))
