# inmobiliaria/urls.py
"""
URL configuration for inmobiliaria project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('usuario/', include('usuario.urls')),
    path('inmueble/', include('inmueble.urls')),
    path('contacto/', include('contacto.urls')),
    path('cita/'    , include('cita.urls')),
    path('api/desempeno/', include('desempeno.urls')),
    path('contrato/', include('contrato.urls')),
    path('alertas/', include('alertas.urls')),  # para CU30
    path('reportes/', include('reportes.urls')),
    path('ventas/', include('ventas.urls')),  # Nueva línea para ventas
]
urlpatterns += static(settings.CONTRATOS_URL, document_root=settings.CONTRATOS_ROOT)