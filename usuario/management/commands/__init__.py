from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os

class Command(BaseCommand):
    help = 'Crea un superusuario automáticamente si no existe'

    def handle(self, *args, **options):
        User = get_user_model()
        
        # Leer variables de entorno (las pondremos en Render)
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

        if not username or not password:
            self.stdout.write(self.style.WARNING('⚠️ No se encontraron variables de entorno para Superusuario. Saltando creación.'))
            return

        if not User.objects.filter(username=username).exists():
            print(f"Creando superusuario: {username}...")
            try:
                # Como usas un modelo de Usuario personalizado, aseguramos los campos mínimos
                User.objects.create_superuser(
                    username=username, 
                    email=email, 
                    password=password,
                    nombre="Administrador Sistema" # Campo extra de tu modelo
                )
                self.stdout.write(self.style.SUCCESS(f'✅ Superusuario "{username}" creado exitosamente!'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ Error creando superusuario: {e}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'ℹ️ El superusuario "{username}" ya existe.'))