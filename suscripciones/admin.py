# suscripciones/admin.py
from django.contrib import admin
from .models import Plan, Suscripcion

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'precio', 'limite_inmuebles', 'is_active')
    search_fields = ('nombre',)

@admin.register(Suscripcion)
class SuscripcionAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'plan', 'estado', 'fecha_fin')
    list_filter = ('estado', 'plan')
    search_fields = ('usuario__username', 'usuario__email')