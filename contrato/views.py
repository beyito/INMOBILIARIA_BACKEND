# views.py
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Contrato
from usuario.models import Usuario
from django.db.models import Avg
@api_view(['GET'])
# @requiere_permiso("Comision", "leer")
def dashboard_comisiones(request):
    """
    Dashboard de control de comisiones para administradores
    """
    try:
        # Filtros por fecha (opcionales)
        fecha_inicio = request.GET.get('fecha_inicio')
        fecha_fin = request.GET.get('fecha_fin')
        incluir_servicios = request.GET.get('incluir_servicios', 'false').lower() == 'true'
        
        # Base queryset
        if incluir_servicios:
            contratos = Contrato.objects.filter(estado='activo')
        else:
            contratos = Contrato.objects.filter(estado='activo').exclude(tipo_contrato='servicios')
        
        # Aplicar filtros de fecha si existen
        if fecha_inicio:
            contratos = contratos.filter(fecha_contrato__gte=fecha_inicio)
        if fecha_fin:
            contratos = contratos.filter(fecha_contrato__lte=fecha_fin)
            incluir_servicios = request.GET.get('incluir_servicios', 'false').lower() == 'true'

        hay_contratos_servicios = Contrato.objects.filter(
            tipo_contrato='servicios', 
            estado='activo'
        ).exists()
        
        # Base queryset - excluir servicios por defecto
        if incluir_servicios:
            contratos = Contrato.objects.filter(estado='activo')
        else:
            contratos = Contrato.objects.filter(estado='activo').exclude(tipo_contrato='servicios')
        
        # Estadísticas generales
        stats_generales = {
            'total_contratos': contratos.count(),
            'total_comisiones': float(contratos.aggregate(Sum('comision_monto'))['comision_monto__sum'] or 0),
            'comision_promedio': float(contratos.aggregate(avg=Avg('comision_porcentaje'))['avg'] or 0),
        }
        
        # Comisiones por agente
        comisiones_agente = contratos.values(
            'agente__id', 
            'agente__nombre', 
            'agente__username'
        ).annotate(
            total_contratos=Count('id'),
            total_comision=Sum('comision_monto'),
            comision_promedio=Avg('comision_porcentaje')
        ).order_by('-total_comision')
        
        # Comisiones por tipo de contrato
        comisiones_tipo = contratos.values('tipo_contrato').annotate(
            total_contratos=Count('id'),
            total_comision=Sum('comision_monto')
        ).order_by('-total_comision')
        
        # Comisiones mensuales (últimos 6 meses)
        seis_meses_atras = timezone.now().date() - timedelta(days=180)
        comisiones_mensuales = contratos.filter(
            fecha_contrato__gte=seis_meses_atras
        ).extra({
            'mes': "EXTRACT(month FROM fecha_contrato)",
            'ano': "EXTRACT(year FROM fecha_contrato)"
        }).values('mes', 'ano').annotate(
            total_comision=Sum('comision_monto'),
            total_contratos=Count('id')
        ).order_by('-ano', '-mes')[:6]
        
        # Top 5 contratos con mayor comisión
        top_contratos = contratos.select_related('agente', 'inmueble').order_by('-comision_monto')[:5]
        top_contratos = contratos.select_related('agente', 'inmueble').order_by('-comision_monto')[:5]
        top_contratos_data = []
        for contrato in top_contratos:
            top_contratos_data.append({
            'id': contrato.id,
            'cliente': contrato.parte_contratante_nombre,
            'agente': contrato.agente.nombre,
            'inmueble': contrato.inmueble.titulo if contrato.inmueble else 'N/A',
            'tipo_contrato': contrato.get_tipo_contrato_display(),
            'monto_contrato': float(contrato.monto or 0),  # ✅ NUEVO
            'comision_monto': float(contrato.comision_monto or 0),
            'comision_porcentaje': float(contrato.comision_porcentaje or 0),
            'fecha': contrato.fecha_contrato
            })
        if incluir_servicios:
            stats_generales['contratos_servicios'] = contratos.filter(tipo_contrato='servicios').count()
        
        return Response({
            "status": 1,
            "error": 0,
            "message": "DASHBOARD DE CONTROL DE COMISIONES",
            "values": {
                "stats_generales": stats_generales,
                "comisiones_agente": comisiones_agente,
                "comisiones_tipo": comisiones_tipo,
                "comisiones_mensuales": comisiones_mensuales,
                "top_contratos": top_contratos_data,
                "hay_contratos_servicios": hay_contratos_servicios
            }
        })
        
    except Exception as e:
        return Response({
            "status": 0,
            "error": 1,
            "message": f"Error al generar dashboard: {str(e)}",
            "values": {}
        }, status=500)

@api_view(['GET'])
# @requiere_permiso("Comision", "leer")
def detalle_comisiones_agente(request, agente_id):
    """
    Detalle de comisiones de un agente específico
    """
    try:
        agente = Usuario.objects.get(id=agente_id, grupo__nombre='agente')
        
        # Filtros
        fecha_inicio = request.GET.get('fecha_inicio')
        fecha_fin = request.GET.get('fecha_fin')
        incluir_servicios = request.GET.get('incluir_servicios', 'false').lower() == 'true'
        
        # Base queryset - aplicar filtro de servicios
        if incluir_servicios:
            contratos_agente = Contrato.objects.filter(agente=agente, estado='activo')
        else:
            contratos_agente = Contrato.objects.filter(agente=agente, estado='activo').exclude(tipo_contrato='servicios')
        
        if fecha_inicio:
            contratos_agente = contratos_agente.filter(fecha_contrato__gte=fecha_inicio)
        if fecha_fin:
            contratos_agente = contratos_agente.filter(fecha_contrato__lte=fecha_fin)
        
        # Estadísticas del agente
        stats_agente = {
            'agente_nombre': agente.nombre,
            'agente_username': agente.username,
            'total_contratos': contratos_agente.count(),
            'total_comision': float(contratos_agente.aggregate(Sum('comision_monto'))['comision_monto__sum'] or 0),
            'comision_promedio': float(contratos_agente.aggregate(avg=Avg('comision_porcentaje'))['avg'] or 0),
            'monto_total_contratos': float(contratos_agente.aggregate(Sum('monto'))['monto__sum'] or 0),
        }
        
        # Contratos del agente
        contratos_data = []
        for contrato in contratos_agente.select_related('inmueble').order_by('-fecha_contrato'):
            contratos_data.append({
                'id': contrato.id,
                'cliente': contrato.parte_contratante_nombre,
                'inmueble': contrato.inmueble.titulo if contrato.inmueble else 'N/A',
                'tipo_contrato': contrato.get_tipo_contrato_display(),
                'monto_contrato': float(contrato.monto or 0),
                'comision_monto': float(contrato.comision_monto or 0),
                'comision_porcentaje': float(contrato.comision_porcentaje or 0),
                'fecha_contrato': contrato.fecha_contrato,
                'vigencia_dias': contrato.vigencia_dias,
                'estado': contrato.estado
            })
        
        # Comisiones por tipo de contrato
        comisiones_tipo = contratos_agente.values('tipo_contrato').annotate(
            total_contratos=Count('id'),
            total_comision=Sum('comision_monto'),
            monto_total=Sum('monto')
        ).order_by('-total_comision')
        
        return Response({
            "status": 1,
            "error": 0,
            "message": f"DETALLE DE COMISIONES - {agente.nombre}",
            "values": {
                "stats_agente": stats_agente,
                "contratos": contratos_data,
                "comisiones_tipo": comisiones_tipo
            }
        })
        
    except Usuario.DoesNotExist:
        return Response({
            "status": 0,
            "error": 1,
            "message": "Agente no encontrado",
            "values": {}
        }, status=404)
    except Exception as e:
        return Response({
            "status": 0,
            "error": 1,
            "message": f"Error al cargar detalle: {str(e)}",
            "values": {}
        }, status=500)