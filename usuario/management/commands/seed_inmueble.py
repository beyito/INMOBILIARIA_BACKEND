from django.core.management.base import BaseCommand
from inmueble.models import TipoInmuebleModel, InmuebleModel
from usuario.models import Usuario


class Command(BaseCommand):
    help = "Crea tipos de inmueble y algunos inmuebles de prueba"

    def handle(self, *args, **kwargs):
        # --------------------------
        # 1️⃣ Verificar usuarios base
        # --------------------------
        try:
            agente = Usuario.objects.get(username="juan_agente")
            cliente = Usuario.objects.get(username="maria_cliente")
        except Usuario.DoesNotExist:
            self.stdout.write(self.style.ERROR("❌ Primero ejecuta: python manage.py seed"))
            return

        # --------------------------
        # 2️⃣ Crear tipos de inmueble
        # --------------------------
        tipos = [
            ("Casa", "Vivienda familiar con patio o jardín"),
            ("Departamento", "Unidad habitacional en edificio"),
            ("Terreno", "Lote urbano o rural disponible"),
        ]

        tipo_objs = []
        for nombre, descripcion in tipos:
            tipo, _ = TipoInmuebleModel.objects.get_or_create(
                nombre=nombre,
                defaults={"descripcion": descripcion}
            )
            tipo_objs.append(tipo)
        self.stdout.write(self.style.SUCCESS("🏠 Tipos de inmueble creados o actualizados"))

        # --------------------------
        # 3️⃣ Crear inmuebles de prueba
        # --------------------------
        data_inmuebles = [
            {
                "titulo": "Casa con jardín y garaje",
                "descripcion": "Hermosa casa familiar en zona norte con 3 dormitorios, patio y garaje techado.",
                "direccion": "Av. Banzer 5to anillo",
                "ciudad": "Santa Cruz de la Sierra",
                "zona": "Zona Norte",
                "superficie": 250.5,
                "dormitorios": 3,
                "baños": 2,
                "precio": 95000,
                "tipo_operacion": "venta",
                "estado": "pendiente",
                "latitud": -17.7555,
                "longitud": -63.1962,
                "tipo_inmueble": tipo_objs[0],
            },
            {
                "titulo": "Departamento céntrico",
                "descripcion": "Ideal para oficina o vivienda, cerca de la plaza principal.",
                "direccion": "Calle Aroma #123",
                "ciudad": "Cochabamba",
                "zona": "Centro",
                "superficie": 120.0,
                "dormitorios": 2,
                "baños": 1,
                "precio": 45000,
                "tipo_operacion": "venta",
                "estado": "pendiente",
                "latitud": -17.3935,
                "longitud": -66.1570,
                "tipo_inmueble": tipo_objs[1],
            },
            {
                "titulo": "Terreno en zona industrial",
                "descripcion": "Terreno plano con acceso pavimentado y todos los servicios básicos.",
                "direccion": "Carretera al Norte, km 12",
                "ciudad": "Santa Cruz de la Sierra",
                "zona": "Parque Industrial",
                "superficie": 800.0,
                "dormitorios": 0,
                "baños": 0,
                "precio": 120000,
                "tipo_operacion": "venta",
                "estado": "aprobado",
                "latitud": -17.7500,
                "longitud": -63.1500,
                "tipo_inmueble": tipo_objs[2],
            },
            {
                "titulo": "Casa de campo",
                "descripcion": "Propiedad rústica rodeada de naturaleza, ideal para descanso.",
                "direccion": "Camino a Samaipata",
                "ciudad": "Santa Cruz de la Sierra",
                "zona": "Samaipata",
                "superficie": 500.0,
                "dormitorios": 4,
                "baños": 3,
                "precio": 180000,
                "tipo_operacion": "venta",
                "estado": "rechazado",
                "latitud": -18.1020,
                "longitud": -63.5000,
                "tipo_inmueble": tipo_objs[0],
            },
        ]

        for data in data_inmuebles:
            InmuebleModel.objects.get_or_create(
                agente=agente,
                cliente=cliente,
                titulo=data["titulo"],
                defaults=data
            )

        self.stdout.write(self.style.SUCCESS("✅ Inmuebles de prueba creados correctamente"))
        self.stdout.write(self.style.SUCCESS("🚀 Seed de inmuebles completado"))
