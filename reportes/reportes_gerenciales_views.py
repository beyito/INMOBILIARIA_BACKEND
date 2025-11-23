# reportes/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Sum, Avg, Q, F, Max, Min, DecimalField
from django.db.models.functions import TruncMonth, TruncWeek, TruncDay, Coalesce
from datetime import datetime, timedelta
from django.utils import timezone

from usuario.models import Usuario, Grupo, SolicitudAgente
from inmueble.models import InmuebleModel, AnuncioModel, TipoInmuebleModel
from contrato.models import Contrato
from contacto.models import ChatModel, MensajeModel
from cita.models import Cita
from alertas.models import AlertaModel



def parsear_fechas(request):
    """Parsea fechas desde query params"""
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    
    if fecha_inicio:
        try:
            fecha_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
        except:
            fecha_inicio = (timezone.now() - timedelta(days=30)).date()
    else:
        fecha_inicio = (timezone.now() - timedelta(days=30)).date()
    
    if fecha_fin:
        try:
            fecha_fin = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
        except:
            fecha_fin = timezone.now().date()
    else:
        fecha_fin = timezone.now().date()
    
    return fecha_inicio, fecha_fin


# ============================================
# 1. DASHBOARD GENERAL
# ============================================

@api_view(['GET'])
# @permission_classes([IsAuthenticated])
def dashboard_general(request):
    """
    GET /api/reportes/dashboard/
    Resumen ejecutivo con KPIs principales
    """
    
    try:
        hoy = timezone.now().date()
        hace_30_dias = hoy - timedelta(days=30)
        
        # Inmuebles
        inmuebles_total = InmuebleModel.objects.filter(is_active=True).count()
        inmuebles_por_estado = list(
            InmuebleModel.objects.filter(is_active=True)
            .values('estado')
            .annotate(total=Count('id'))
        )
        
        # Anuncios
        anuncios_activos = AnuncioModel.objects.filter(
            is_active=True, 
            estado='disponible'
        ).count()
        
        # Contratos
        contratos_activos = Contrato.objects.filter(estado='activo').count()
        contratos_mes = Contrato.objects.filter(
            fecha_creacion__gte=hace_30_dias
        ).count()
        
        # Ingresos (comisiones)
        ingresos_mes = Contrato.objects.filter(
            fecha_creacion__gte=hace_30_dias,
            estado='activo'
        ).aggregate(total=Coalesce(Sum('comision_monto'), 0, output_field=DecimalField()))['total']
        
        ingresos_totales = Contrato.objects.filter(
            estado__in=['activo', 'finalizado']
        ).aggregate(total=Coalesce(Sum('comision_monto'), 0, output_field=DecimalField()))['total']
        
        # Usuarios
        agentes_activos = Usuario.objects.filter(
            grupo__nombre='Agente',
            is_active=True
        ).count()
        
        clientes_activos = Usuario.objects.filter(
            grupo__nombre='Cliente',
            is_active=True
        ).count()
        
        solicitudes_pendientes = SolicitudAgente.objects.filter(
            estado='pendiente'
        ).count()
        
        # Alertas
        alertas_pendientes = AlertaModel.objects.filter(
            estado_envio='pendiente'
        ).count()
        
        alertas_no_vistas = AlertaModel.objects.filter(
            estado_visto='no_visto'
        ).count()
        
        # Citas
        citas_hoy = Cita.objects.filter(fecha_cita=hoy).count()
        citas_semana = Cita.objects.filter(
            fecha_cita__gte=hoy,
            fecha_cita__lte=hoy + timedelta(days=7)
        ).count()
        
        # Chats activos
        chats_activos = ChatModel.objects.filter(
            mensajes__leido=False
        ).distinct().count()
        
        data = {
            'fecha_reporte': hoy.isoformat(),
            'periodo': f'{hace_30_dias.isoformat()} a {hoy.isoformat()}',
            'inmuebles': {
                'total': inmuebles_total,
                'por_estado': inmuebles_por_estado,
                'pendientes': next((i['total'] for i in inmuebles_por_estado if i['estado'] == 'pendiente'), 0),
                'aprobados': next((i['total'] for i in inmuebles_por_estado if i['estado'] == 'aprobado'), 0),
            },
            'anuncios': {
                'activos': anuncios_activos,
            },
            'contratos': {
                'activos': contratos_activos,
                'nuevos_mes': contratos_mes,
            },
            'ingresos': {
                'mes_actual': float(ingresos_mes),
                'total': float(ingresos_totales),
            },
            'usuarios': {
                'agentes_activos': agentes_activos,
                'clientes_activos': clientes_activos,
                'solicitudes_pendientes': solicitudes_pendientes,
            },
            'alertas': {
                'pendientes': alertas_pendientes,
                'no_vistas': alertas_no_vistas,
            },
            'citas': {
                'hoy': citas_hoy,
                'proxima_semana': citas_semana,
            },
            'comunicacion': {
                'chats_con_mensajes_sin_leer': chats_activos,
            }
        }
        # print("DATA", data)
        return Response({
            "status": 1,
            "error": 0,
            "message": "Dashboard obtenido correctamente",
            "values": data
        })
        
    except Exception as e:
        # print("ERROR",e)
        return Response({
            "status": 0,
            "error": 1,
            "message": f"Error al obtener dashboard: {str(e)}",
            "values": {}
        })


# ============================================
# 2. REPORTE DE INMUEBLES
# ============================================

@api_view(['GET'])
# @permission_classes([IsAuthenticated])
def reporte_inmuebles(request):
    """
    GET /api/reportes/inmuebles/
    Query params: tipo_operacion, estado, fecha_inicio, fecha_fin, agente_id, tipo_inmueble_id, ciudad
    """
    try:
        # Filtros
        queryset = InmuebleModel.objects.filter(is_active=True)
        
        tipo_operacion = request.GET.get('tipo_operacion')
        estado = request.GET.get('estado')
        agente_id = request.GET.get('agente_id')
        tipo_inmueble_id = request.GET.get('tipo_inmueble_id')
        ciudad = request.GET.get('ciudad')
        
        if tipo_operacion:
            queryset = queryset.filter(tipo_operacion=tipo_operacion)
        if estado:
            queryset = queryset.filter(estado=estado)
        if agente_id:
            queryset = queryset.filter(agente_id=agente_id)
        if tipo_inmueble_id:
            queryset = queryset.filter(tipo_inmueble_id=tipo_inmueble_id)
        if ciudad:
            queryset = queryset.filter(ciudad__icontains=ciudad)
        
        # Totales generales
        total_inmuebles = queryset.count()
        
        # Por tipo de operación
        por_operacion = list(
            queryset.values('tipo_operacion')
            .annotate(total=Count('id'))
        )
        
        # Por estado
        por_estado = list(
            queryset.values('estado')
            .annotate(total=Count('id'))
        )
        
        # Por ciudad
        por_ciudad = list(
            queryset.values('ciudad')
            .annotate(total=Count('id'))
            .order_by('-total')[:10]
        )
        
        # Por zona
        por_zona = list(
            queryset.values('zona')
            .annotate(total=Count('id'))
            .order_by('-total')[:10]
        )
        
        # Por tipo de inmueble
        por_tipo = list(
            queryset.values('tipo_inmueble__nombre')
            .annotate(total=Count('id'))
            .order_by('-total')
        )
        
        # Precios
        stats_precio = queryset.aggregate(
            promedio=Avg('precio'),
            minimo=Min('precio'),
            maximo=Max('precio')
        )
        
        # Precio promedio por tipo de operación
        precio_por_operacion = list(
            queryset.values('tipo_operacion')
            .annotate(
                promedio=Avg('precio'),
                minimo=Min('precio'),
                maximo=Max('precio')
            )
        )
        
        # Top 10 agentes con más inmuebles
        top_agentes = list(
            queryset.values('agente__nombre', 'agente__id')
            .annotate(total=Count('id'))
            .order_by('-total')[:10]
        )
        
        # Superficie promedio
        superficie_promedio = queryset.aggregate(
            promedio=Avg('superficie')
        )['promedio'] or 0
        
        data = {
            'total_inmuebles': total_inmuebles,
            'por_tipo_operacion': por_operacion,
            'por_estado': por_estado,
            'por_ciudad': por_ciudad,
            'por_zona': por_zona,
            'por_tipo_inmueble': por_tipo,
            'estadisticas_precio': {
                'promedio': float(stats_precio['promedio'] or 0),
                'minimo': float(stats_precio['minimo'] or 0),
                'maximo': float(stats_precio['maximo'] or 0),
            },
            'precio_por_operacion': [
                {
                    'tipo_operacion': item['tipo_operacion'],
                    'promedio': float(item['promedio'] or 0),
                    'minimo': float(item['minimo'] or 0),
                    'maximo': float(item['maximo'] or 0),
                }
                for item in precio_por_operacion
            ],
            'top_agentes': top_agentes,
            'superficie_promedio': float(superficie_promedio),
        }
        
        return Response({
            "status": 1,
            "error": 0,
            "message": "Reporte de inmuebles obtenido correctamente",
            "values": data
        })
        
    except Exception as e:
        return Response({
            "status": 0,
            "error": 1,
            "message": f"Error al generar reporte: {str(e)}",
            "values": {}
        })


# ============================================
# 3. REPORTE DE CONTRATOS
# ============================================

@api_view(['GET'])
# @permission_classes([IsAuthenticated])
def reporte_contratos(request):
    """
    GET /api/reportes/contratos/
    Query params: tipo_contrato, estado, fecha_inicio, fecha_fin, agente_id
    """
    
    try:
        fecha_inicio, fecha_fin = parsear_fechas(request)
        
        # Filtros
        queryset = Contrato.objects.all()
        
        tipo_contrato = request.GET.get('tipo_contrato')
        estado = request.GET.get('estado')
        agente_id = request.GET.get('agente_id')
        
        if tipo_contrato:
            queryset = queryset.filter(tipo_contrato=tipo_contrato)
        if estado:
            queryset = queryset.filter(estado=estado)
        if agente_id:
            queryset = queryset.filter(agente_id=agente_id)
        
        queryset = queryset.filter(
            fecha_creacion__date__gte=fecha_inicio,
            fecha_creacion__date__lte=fecha_fin
        )
        
        # Totales
        total_contratos = queryset.count()
        
        # Por tipo
        por_tipo = list(
            queryset.values('tipo_contrato')
            .annotate(total=Count('id'))
        )
        
        # Por estado
        por_estado = list(
            queryset.values('estado')
            .annotate(total=Count('id'))
        )
        
        # Ingresos por comisiones
        ingresos_totales = queryset.aggregate(
            total=Coalesce(Sum('comision_monto'), 0, output_field=DecimalField())
        )['total']
        
        comision_promedio = queryset.aggregate(
            promedio=Avg('comision_monto')
        )['promedio'] or 0
        
        # Comisiones por tipo de contrato
        comisiones_por_tipo = list(
            queryset.values('tipo_contrato')
            .annotate(
                total=Coalesce(Sum('comision_monto'), 0, output_field=DecimalField()),
                promedio=Avg('comision_monto'),
                cantidad=Count('id')
            )
        )
        
        # Top agentes por comisiones
        top_agentes_comisiones = list(
            queryset.values('agente__nombre', 'agente__id')
            .annotate(
                total_comisiones=Coalesce(Sum('comision_monto'), 0, output_field=DecimalField()),
                cantidad_contratos=Count('id')
            )
            .order_by('-total_comisiones')[:10]
        )
        
        # Contratos por mes
        contratos_por_mes = list(
            queryset.annotate(mes=TruncMonth('fecha_creacion'))
            .values('mes')
            .annotate(
                total=Count('id'),
                ingresos=Coalesce(Sum('comision_monto'), 0, output_field=DecimalField())
            )
            .order_by('mes')
        )
        
        # Contratos próximos a vencer (30 días)
        hoy = timezone.now().date()
        proximos_vencer = Contrato.objects.filter(
            estado='activo',
            fecha_fin__gte=hoy,
            fecha_fin__lte=hoy + timedelta(days=30)
        ).count()
        
        # Tasa de conversión (inmuebles aprobados vs contratos)
        inmuebles_aprobados = InmuebleModel.objects.filter(
            estado='aprobado',
            is_active=True
        ).count()
        
        tasa_conversion = (total_contratos / inmuebles_aprobados * 100) if inmuebles_aprobados > 0 else 0
        
        data = {
            'periodo': f'{fecha_inicio.isoformat()} a {fecha_fin.isoformat()}',
            'total_contratos': total_contratos,
            'por_tipo_contrato': por_tipo,
            'por_estado': por_estado,
            'ingresos': {
                'total': float(ingresos_totales),
                'promedio_por_contrato': float(comision_promedio),
            },
            'comisiones_por_tipo': [
                {
                    'tipo_contrato': item['tipo_contrato'],
                    'total': float(item['total']),
                    'promedio': float(item['promedio'] or 0),
                    'cantidad': item['cantidad'],
                }
                for item in comisiones_por_tipo
            ],
            'top_agentes': [
                {
                    'agente': item['agente__nombre'],
                    'agente_id': item['agente__id'],
                    'total_comisiones': float(item['total_comisiones']),
                    'cantidad_contratos': item['cantidad_contratos'],
                }
                for item in top_agentes_comisiones
            ],
            'contratos_por_mes': [
                {
                    'mes': item['mes'].strftime('%Y-%m'),
                    'total': item['total'],
                    'ingresos': float(item['ingresos']),
                }
                for item in contratos_por_mes
            ],
            'proximos_a_vencer': proximos_vencer,
            'tasa_conversion': round(tasa_conversion, 2),
        }
        
        return Response({
            "status": 1,
            "error": 0,
            "message": "Reporte de contratos obtenido correctamente",
            "values": data
        })
        
    except Exception as e:
        return Response({
            "status": 0,
            "error": 1,
            "message": f"Error al generar reporte: {str(e)}",
            "values": {}
        })


# ============================================
# 4. REPORTE DE DESEMPEÑO DE AGENTES
# ============================================

@api_view(['GET'])
# @permission_classes([IsAuthenticated])
def reporte_agentes(request):
    """
    GET /api/reportes/agentes/
    Query params: agente_id, fecha_inicio, fecha_fin
    """
    
    try:
        fecha_inicio, fecha_fin = parsear_fechas(request)
        agente_id = request.GET.get('agente_id')
        
        # Obtener todos los agentes activos
        agentes_queryset = Usuario.objects.filter(
            grupo__nombre='Agente',
            is_active=True
        )
        
        if agente_id:
            agentes_queryset = agentes_queryset.filter(id=agente_id)
        
        agentes_data = []
        
        for agente in agentes_queryset:
            # Inmuebles publicados
            inmuebles_publicados = InmuebleModel.objects.filter(
                agente=agente,
                is_active=True
            ).count()
            
            inmuebles_aprobados = InmuebleModel.objects.filter(
                agente=agente,
                estado='aprobado',
                is_active=True
            ).count()
            
            # Contratos cerrados
            contratos = Contrato.objects.filter(
                agente=agente,
                fecha_creacion__date__gte=fecha_inicio,
                fecha_creacion__date__lte=fecha_fin
            )
            
            contratos_cerrados = contratos.count()
            contratos_activos = contratos.filter(estado='activo').count()
            
            # Comisiones generadas
            comisiones = contratos.aggregate(
                total=Coalesce(Sum('comision_monto'), 0, output_field=DecimalField())
            )['total']
            
            # Tasa de conversión
            tasa_conversion = (contratos_cerrados / inmuebles_aprobados * 100) if inmuebles_aprobados > 0 else 0
            
            # Citas
            citas_totales = Cita.objects.filter(
                agente=agente,
                fecha_cita__gte=fecha_inicio,
                fecha_cita__lte=fecha_fin
            ).count()
            
            citas_realizadas = Cita.objects.filter(
                agente=agente,
                estado='REALIZADA',
                fecha_cita__gte=fecha_inicio,
                fecha_cita__lte=fecha_fin
            ).count()
            
            citas_canceladas = Cita.objects.filter(
                agente=agente,
                estado='CANCELADA',
                fecha_cita__gte=fecha_inicio,
                fecha_cita__lte=fecha_fin
            ).count()
            
            # Chats
            chats_atendidos = ChatModel.objects.filter(agente=agente).count()
            
            agentes_data.append({
                'agente_id': agente.id,
                'nombre': agente.nombre,
                'correo': agente.correo,
                'telefono': agente.telefono,
                'inmuebles': {
                    'publicados': inmuebles_publicados,
                    'aprobados': inmuebles_aprobados,
                },
                'contratos': {
                    'cerrados': contratos_cerrados,
                    'activos': contratos_activos,
                },
                'comisiones_generadas': float(comisiones),
                'tasa_conversion': round(tasa_conversion, 2),
                'citas': {
                    'totales': citas_totales,
                    'realizadas': citas_realizadas,
                    'canceladas': citas_canceladas,
                },
                'chats_atendidos': chats_atendidos,
            })
        
        # Ordenar por comisiones generadas
        agentes_data = sorted(agentes_data, key=lambda x: x['comisiones_generadas'], reverse=True)
        
        # Totales generales
        totales = {
            'total_agentes': len(agentes_data),
            'total_inmuebles': sum(a['inmuebles']['publicados'] for a in agentes_data),
            'total_contratos': sum(a['contratos']['cerrados'] for a in agentes_data),
            'total_comisiones': sum(a['comisiones_generadas'] for a in agentes_data),
        }
        
        return Response({
            "status": 1,
            "error": 0,
            "message": "Reporte de agentes obtenido correctamente",
            "values": {
                'periodo': f'{fecha_inicio.isoformat()} a {fecha_fin.isoformat()}',
                'totales': totales,
                'agentes': agentes_data,
            }
        })
        
    except Exception as e:
        return Response({
            "status": 0,
            "error": 1,
            "message": f"Error al generar reporte: {str(e)}",
            "values": {}
        })


# ============================================
# 5. REPORTE FINANCIERO
# ============================================

@api_view(['GET'])
# @permission_classes([IsAuthenticated])
def reporte_financiero(request):
    """
    GET /api/reportes/financiero/
    Query params: fecha_inicio, fecha_fin, tipo_contrato, agrupacion (mes/semana/dia)
    """
    
    try:
        fecha_inicio, fecha_fin = parsear_fechas(request)
        tipo_contrato = request.GET.get('tipo_contrato')
        agrupacion = request.GET.get('agrupacion', 'mes')  # mes, semana, dia
        
        queryset = Contrato.objects.filter(
            fecha_creacion__date__gte=fecha_inicio,
            fecha_creacion__date__lte=fecha_fin,
            estado__in=['activo', 'finalizado']
        )
        
        if tipo_contrato:
            queryset = queryset.filter(tipo_contrato=tipo_contrato)
        
        # Total de comisiones
        total_comisiones = queryset.aggregate(
            total=Coalesce(Sum('comision_monto'), 0, output_field=DecimalField())
        )['total']
        
        # Comisiones por tipo de contrato
        comisiones_por_tipo = list(
            queryset.values('tipo_contrato')
            .annotate(
                total=Coalesce(Sum('comision_monto'), 0, output_field=DecimalField()),
                cantidad=Count('id')
            )
        )
        
        # Comisiones por agente
        comisiones_por_agente = list(
            queryset.values('agente__nombre', 'agente__id')
            .annotate(
                total=Coalesce(Sum('comision_monto'), 0, output_field=DecimalField()),
                cantidad=Count('id')
            )
            .order_by('-total')[:10]
        )
        
        # Evolución temporal
        if agrupacion == 'mes':
            trunc_function = TruncMonth
            date_format = '%Y-%m'
        elif agrupacion == 'semana':
            trunc_function = TruncWeek
            date_format = '%Y-W%W'
        else:  # dia
            trunc_function = TruncDay
            date_format = '%Y-%m-%d'
        
        evolucion = list(
            queryset.annotate(periodo=trunc_function('fecha_creacion'))
            .values('periodo')
            .annotate(
                total_comisiones=Coalesce(Sum('comision_monto'), 0, output_field=DecimalField()),
                cantidad_contratos=Count('id')
            )
            .order_by('periodo')
        )
        
        # Proyección de ingresos (contratos activos)
        contratos_activos = Contrato.objects.filter(estado='activo')
        proyeccion_ingresos = contratos_activos.aggregate(
            total=Coalesce(Sum('comision_monto'), 0, output_field=DecimalField())
        )['total']
        
        # Comisiones por ciudad
        comisiones_por_ciudad = list(
            queryset.values('ciudad')
            .annotate(
                total=Coalesce(Sum('comision_monto'), 0, output_field=DecimalField()),
                cantidad=Count('id')
            )
            .order_by('-total')[:10]
        )
        
        data = {
            'periodo': f'{fecha_inicio.isoformat()} a {fecha_fin.isoformat()}',
            'total_comisiones': float(total_comisiones),
            'comisiones_por_tipo': [
                {
                    'tipo': item['tipo_contrato'],
                    'total': float(item['total']),
                    'cantidad': item['cantidad'],
                }
                for item in comisiones_por_tipo
            ],
            'top_10_agentes': [
                {
                    'agente': item['agente__nombre'],
                    'agente_id': item['agente__id'],
                    'total': float(item['total']),
                    'cantidad': item['cantidad'],
                }
                for item in comisiones_por_agente
            ],
            'evolucion_temporal': [
                {
                    'periodo': item['periodo'].strftime(date_format),
                    'total_comisiones': float(item['total_comisiones']),
                    'cantidad_contratos': item['cantidad_contratos'],
                }
                for item in evolucion
            ],
            'proyeccion_ingresos_activos': float(proyeccion_ingresos),
            'comisiones_por_ciudad': [
                {
                    'ciudad': item['ciudad'],
                    'total': float(item['total']),
                    'cantidad': item['cantidad'],
                }
                for item in comisiones_por_ciudad
            ],
        }
        
        return Response({
            "status": 1,
            "error": 0,
            "message": "Reporte financiero obtenido correctamente",
            "values": data
        })
        
    except Exception as e:
        return Response({
            "status": 0,
            "error": 1,
            "message": f"Error al generar reporte: {str(e)}",
            "values": {}
        })


# ============================================
# 6. REPORTE DE ALERTAS Y PAGOS
# ============================================

@api_view(['GET'])
# @permission_classes([IsAuthenticated])
def reporte_alertas(request):
    """
    GET /api/reportes/alertas/
    Query params: tipo_alerta, estado_envio, dias_vencimiento (7, 15, 30)
    """
    
    try:
        hoy = timezone.now()
        
        # Filtros
        tipo_alerta = request.GET.get('tipo_alerta')
        estado_envio = request.GET.get('estado_envio')
        dias_vencimiento = int(request.GET.get('dias_vencimiento', 30))
        
        queryset = AlertaModel.objects.all()
        
        if tipo_alerta:
            queryset = queryset.filter(tipo_alerta=tipo_alerta)
        if estado_envio:
            queryset = queryset.filter(estado_envio=estado_envio)
        
        # Alertas por tipo
        por_tipo = list(
            queryset.values('tipo_alerta')
            .annotate(total=Count('id'))
        )
        
        # Alertas por estado de envío
        por_estado_envio = list(
            queryset.values('estado_envio')
            .annotate(total=Count('id'))
        )
        
        # Alertas por estado visto
        por_estado_visto = list(
            queryset.values('estado_visto')
            .annotate(total=Count('id'))
        )
        
        # Alertas pendientes
        alertas_pendientes = queryset.filter(estado_envio='pendiente').count()
        
        # Alertas no vistas
        alertas_no_vistas = queryset.filter(estado_visto='no_visto').count()
        
        # Alertas de mora (pago_vencido)
        alertas_mora = queryset.filter(tipo_alerta='pago_vencido').count()
        
        # Pagos próximos a vencer
        fecha_limite = hoy + timedelta(days=dias_vencimiento)
        pagos_proximos = AlertaModel.objects.filter(
            tipo_alerta='pago_alquiler',
            fecha_programada__gte=hoy,
            fecha_programada__lte=fecha_limite
        ).count()
        
        # Contratos próximos a vencer (anticrético)
        contratos_vencer = AlertaModel.objects.filter(
            tipo_alerta='vencimiento_anticretico',
            fecha_programada__gte=hoy,
            fecha_programada__lte=fecha_limite
        ).count()
        
        # Alertas por mes (últimos 6 meses)
        hace_6_meses = hoy - timedelta(days=180)
        alertas_por_mes = list(
            AlertaModel.objects.filter(fecha_programada__gte=hace_6_meses)
            .annotate(mes=TruncMonth('fecha_programada'))
            .values('mes', 'tipo_alerta')
            .annotate(total=Count('id'))
            .order_by('mes', 'tipo_alerta')
        )
        
        data = {
            'alertas_por_tipo': por_tipo,
            'alertas_por_estado_envio': por_estado_envio,
            'alertas_por_estado_visto': por_estado_visto,
            'resumen': {
                'pendientes': alertas_pendientes,
                'no_vistas': alertas_no_vistas,
                'mora': alertas_mora,
            },
            'proximos_vencimientos': {
                'dias_parametro': dias_vencimiento,
                'pagos_alquiler': pagos_proximos,
                'contratos_anticretico': contratos_vencer,
            },
            'historial_mensual': [
                {
                    'mes': item['mes'].strftime('%Y-%m'),
                    'tipo': item['tipo_alerta'],
                    'total': item['total'],
                }
                for item in alertas_por_mes
            ],
        }
        
        return Response({
            "status": 1,
            "error": 0,
            "message": "Reporte de alertas obtenido correctamente",
            "values": data
        })
        
    except Exception as e:
        return Response({
            "status": 0,
            "error": 1,
            "message": f"Error al generar reporte: {str(e)}",
            "values": {}
        })


# ============================================
# 7. REPORTE DE USUARIOS
# ============================================

@api_view(['GET'])
# @permission_classes([IsAuthenticated])
def reporte_usuarios(request):
    """
    GET /api/reportes/usuarios/
    Query params: fecha_inicio, fecha_fin, grupo
    """

    try:
        fecha_inicio, fecha_fin = parsear_fechas(request)
        grupo = request.GET.get('grupo')
        
        # Usuarios totales
        usuarios_queryset = Usuario.objects.all()
        
        if grupo:
            usuarios_queryset = usuarios_queryset.filter(grupo__nombre=grupo)
        
        total_usuarios = usuarios_queryset.count()
        usuarios_activos = usuarios_queryset.filter(is_active=True).count()
        usuarios_inactivos = usuarios_queryset.filter(is_active=False).count()
        
        # Usuarios por grupo
        por_grupo = list(
            Usuario.objects.values('grupo__nombre')
            .annotate(
                total=Count('id'),
                activos=Count('id', filter=Q(is_active=True))
            )
        )
        
        # Nuevos registros en el período
        nuevos_registros = Usuario.objects.filter(
            date_joined__date__gte=fecha_inicio,
            date_joined__date__lte=fecha_fin
        ).count()
        
        # Registros por mes (últimos 12 meses)
        hace_12_meses = timezone.now() - timedelta(days=365)
        registros_por_mes = list(
            Usuario.objects.filter(date_joined__gte=hace_12_meses)
            .annotate(mes=TruncMonth('date_joined'))
            .values('mes')
            .annotate(total=Count('id'))
            .order_by('mes')
        )
        
        # Solicitudes de agentes
        solicitudes_totales = SolicitudAgente.objects.count()
        solicitudes_por_estado = list(
            SolicitudAgente.objects.values('estado')
            .annotate(total=Count('id'))
        )
        
        # Solicitudes recientes
        solicitudes_recientes = SolicitudAgente.objects.filter(
            fecha_solicitud__date__gte=fecha_inicio,
            fecha_solicitud__date__lte=fecha_fin
        ).count()
        
        # Distribución geográfica (top 10 ubicaciones)
        distribucion_geografica = list(
            Usuario.objects.exclude(ubicacion__isnull=True)
            .exclude(ubicacion='')
            .values('ubicacion')
            .annotate(total=Count('id'))
            .order_by('-total')[:10]
        )
        
        data = {
            'periodo': f'{fecha_inicio.isoformat()} a {fecha_fin.isoformat()}',
            'total_usuarios': total_usuarios,
            'usuarios_activos': usuarios_activos,
            'usuarios_inactivos': usuarios_inactivos,
            'por_grupo': por_grupo,
            'nuevos_registros': nuevos_registros,
            'registros_por_mes': [
                {
                    'mes': item['mes'].strftime('%Y-%m'),
                    'total': item['total'],
                }
                for item in registros_por_mes
            ],
            'solicitudes_agentes': {
                'total': solicitudes_totales,
                'por_estado': solicitudes_por_estado,
                'recientes': solicitudes_recientes,
            },
            'distribucion_geografica': distribucion_geografica,
        }
        
        return Response({
            "status": 1,
            "error": 0,
            "message": "Reporte de usuarios obtenido correctamente",
            "values": data
        })
        
    except Exception as e:
        return Response({
            "status": 0,
            "error": 1,
            "message": f"Error al generar reporte: {str(e)}",
            "values": {}
        })


# ============================================
# 8. REPORTE DE ANUNCIOS
# ============================================

@api_view(['GET'])
# @permission_classes([IsAuthenticated])
def reporte_anuncios(request):
    """
    GET /api/reportes/anuncios/
    Query params: estado, prioridad, fecha_inicio, fecha_fin
    """
    
    try:
        fecha_inicio, fecha_fin = parsear_fechas(request)
        
        queryset = AnuncioModel.objects.filter(is_active=True)
        
        estado = request.GET.get('estado')
        prioridad = request.GET.get('prioridad')
        
        if estado:
            queryset = queryset.filter(estado=estado)
        if prioridad:
            queryset = queryset.filter(prioridad=prioridad)
        
        # Totales
        total_anuncios = queryset.count()
        
        # Por estado
        por_estado = list(
            queryset.values('estado')
            .annotate(total=Count('id'))
        )
        
        # Por prioridad
        por_prioridad = list(
            queryset.values('prioridad')
            .annotate(total=Count('id'))
        )
        
        # Anuncios disponibles vs cerrados
        disponibles = queryset.filter(estado='disponible').count()
        vendidos = queryset.filter(estado='vendido').count()
        alquilados = queryset.filter(estado='alquilado').count()
        
        # Anuncios por tipo de operación
        por_operacion = list(
            queryset.values('inmueble__tipo_operacion')
            .annotate(total=Count('id'))
        )
        
        # Anuncios más antiguos sin vender/alquilar
        hoy = timezone.now()
        dias_antiguedad = 90
        
        anuncios_antiguos = list(
            queryset.filter(
                estado='disponible',
                fecha_publicacion__lte=hoy - timedelta(days=dias_antiguedad)
            )
            .values(
                'id',
                'inmueble__titulo',
                'inmueble__precio',
                'inmueble__tipo_operacion',
                'fecha_publicacion'
            )
            .order_by('fecha_publicacion')[:10]
        )
        
        # Tiempo promedio en el mercado (vendidos/alquilados en el período)
        anuncios_cerrados = AnuncioModel.objects.filter(
            estado__in=['vendido', 'alquilado', 'anticretico'],
            fecha_publicacion__date__gte=fecha_inicio,
            fecha_publicacion__date__lte=fecha_fin
        )
        
        # Si tienes un campo de fecha de cierre, úsalo. Si no, esto es aproximado
        # tiempo_promedio_mercado = calcular diferencia entre publicación y cierre
        
        # Anuncios por ciudad
        por_ciudad = list(
            queryset.values('inmueble__ciudad')
            .annotate(total=Count('id'))
            .order_by('-total')[:10]
        )
        
        # Anuncios premium vs normales - efectividad
        efectividad_premium = {
            'premium': queryset.filter(prioridad='premium').count(),
            'destacado': queryset.filter(prioridad='destacado').count(),
            'normal': queryset.filter(prioridad='normal').count(),
        }
        
        data = {
            'total_anuncios': total_anuncios,
            'por_estado': por_estado,
            'por_prioridad': por_prioridad,
            'resumen': {
                'disponibles': disponibles,
                'vendidos': vendidos,
                'alquilados': alquilados,
            },
            'por_tipo_operacion': por_operacion,
            'anuncios_antiguos': [
                {
                    'id': item['id'],
                    'titulo': item['inmueble__titulo'],
                    'precio': float(item['inmueble__precio']),
                    'tipo_operacion': item['inmueble__tipo_operacion'],
                    'fecha_publicacion': item['fecha_publicacion'].strftime('%Y-%m-%d'),
                    'dias_mercado': (hoy.date() - item['fecha_publicacion'].date()).days,
                }
                for item in anuncios_antiguos
            ],
            'por_ciudad': por_ciudad,
            'efectividad_prioridad': efectividad_premium,
        }
        
        return Response({
            "status": 1,
            "error": 0,
            "message": "Reporte de anuncios obtenido correctamente",
            "values": data
        })
        
    except Exception as e:
        return Response({
            "status": 0,
            "error": 1,
            "message": f"Error al generar reporte: {str(e)}",
            "values": {}
        })


# ============================================
# 9. REPORTE DE COMUNICACIÓN
# ============================================

@api_view(['GET'])
# @permission_classes([IsAuthenticated])
def reporte_comunicacion(request):
    """
    GET /api/reportes/comunicacion/
    Query params: fecha_inicio, fecha_fin, agente_id
    """
    
    try:
        fecha_inicio, fecha_fin = parsear_fechas(request)
        agente_id = request.GET.get('agente_id')
        
        # Chats
        chats_queryset = ChatModel.objects.filter(
            fecha_creacion__date__gte=fecha_inicio,
            fecha_creacion__date__lte=fecha_fin
        )
        
        if agente_id:
            chats_queryset = chats_queryset.filter(agente_id=agente_id)
        
        total_chats = chats_queryset.count()
        chats_activos = chats_queryset.filter(
            mensajes__leido=False
        ).distinct().count()
        
        # Mensajes
        mensajes_queryset = MensajeModel.objects.filter(
            fecha_envio__date__gte=fecha_inicio,
            fecha_envio__date__lte=fecha_fin
        )
        
        if agente_id:
            mensajes_queryset = mensajes_queryset.filter(chat__agente_id=agente_id)
        
        total_mensajes = mensajes_queryset.count()
        mensajes_sin_leer = mensajes_queryset.filter(leido=False).count()
        
        # Mensajes por día
        mensajes_por_dia = list(
            mensajes_queryset.annotate(dia=TruncDay('fecha_envio'))
            .values('dia')
            .annotate(total=Count('id'))
            .order_by('dia')
        )
        
        # Tiempo promedio de respuesta de agentes (aproximado)
        # Esto requeriría lógica más compleja para calcular exactamente
        
        # Top agentes por mensajes
        top_agentes_mensajes = list(
            MensajeModel.objects.filter(
                fecha_envio__date__gte=fecha_inicio,
                fecha_envio__date__lte=fecha_fin,
                usuario__grupo__nombre='Agente'
            )
            .values('usuario__nombre', 'usuario__id')
            .annotate(total=Count('id'))
            .order_by('-total')[:10]
        )
        
        # Citas
        citas_queryset = Cita.objects.filter(
            fecha_cita__gte=fecha_inicio,
            fecha_cita__lte=fecha_fin
        )
        
        if agente_id:
            citas_queryset = citas_queryset.filter(agente_id=agente_id)
        
        total_citas = citas_queryset.count()
        
        citas_por_estado = list(
            citas_queryset.values('estado')
            .annotate(total=Count('id'))
        )
        
        citas_realizadas = citas_queryset.filter(estado='REALIZADA').count()
        citas_canceladas = citas_queryset.filter(estado='CANCELADA').count()
        citas_pendientes = citas_queryset.filter(estado='PENDIENTE').count()
        
        # Tasa de efectividad de citas
        tasa_efectividad = (citas_realizadas / total_citas * 100) if total_citas > 0 else 0
        
        data = {
            'periodo': f'{fecha_inicio.isoformat()} a {fecha_fin.isoformat()}',
            'chats': {
                'total': total_chats,
                'activos': chats_activos,
            },
            'mensajes': {
                'total': total_mensajes,
                'sin_leer': mensajes_sin_leer,
                'por_dia': [
                    {
                        'dia': item['dia'].strftime('%Y-%m-%d'),
                        'total': item['total'],
                    }
                    for item in mensajes_por_dia
                ],
            },
            'top_agentes_mensajes': top_agentes_mensajes,
            'citas': {
                'total': total_citas,
                'por_estado': citas_por_estado,
                'realizadas': citas_realizadas,
                'canceladas': citas_canceladas,
                'pendientes': citas_pendientes,
                'tasa_efectividad': round(tasa_efectividad, 2),
            },
        }
        
        return Response({
            "status": 1,
            "error": 0,
            "message": "Reporte de comunicación obtenido correctamente",
            "values": data
        })
        
    except Exception as e:
        return Response({
            "status": 0,
            "error": 1,
            "message": f"Error al generar reporte: {str(e)}",
            "values": {}
        })


# ============================================
# 10. REPORTE COMPARATIVO (PERÍODO vs PERÍODO)
# ============================================

@api_view(['GET'])
# @permission_classes([IsAuthenticated])
def reporte_comparativo(request):
    """
    GET /api/reportes/comparativo/
    Query params: fecha_inicio_1, fecha_fin_1, fecha_inicio_2, fecha_fin_2
    Compara dos períodos de tiempo
    """
    
    try:
        # Período 1
        fecha_inicio_1 = request.GET.get('fecha_inicio_1')
        fecha_fin_1 = request.GET.get('fecha_fin_1')
        
        # Período 2
        fecha_inicio_2 = request.GET.get('fecha_inicio_2')
        fecha_fin_2 = request.GET.get('fecha_fin_2')
        
        # Validar fechas
        if not all([fecha_inicio_1, fecha_fin_1, fecha_inicio_2, fecha_fin_2]):
            return Response({
                "status": 0,
                "error": 1,
                "message": "Debe proporcionar ambos períodos completos",
                "values": {}
            })
        
        fecha_inicio_1 = datetime.strptime(fecha_inicio_1, '%Y-%m-%d').date()
        fecha_fin_1 = datetime.strptime(fecha_fin_1, '%Y-%m-%d').date()
        fecha_inicio_2 = datetime.strptime(fecha_inicio_2, '%Y-%m-%d').date()
        fecha_fin_2 = datetime.strptime(fecha_fin_2, '%Y-%m-%d').date()
        
        def obtener_metricas_periodo(inicio, fin):
            """Calcula métricas para un período específico"""
            # Inmuebles
            inmuebles = InmuebleModel.objects.filter(
                fecha_creacion__date__gte=inicio,
                fecha_creacion__date__lte=fin
            ).count()
            
            # Contratos
            contratos = Contrato.objects.filter(
                fecha_creacion__date__gte=inicio,
                fecha_creacion__date__lte=fin
            )
            total_contratos = contratos.count()
            
            # Ingresos
            ingresos = contratos.aggregate(
                total=Coalesce(Sum('comision_monto'), 0, output_field=DecimalField())
            )['total']
            
            # Usuarios nuevos
            usuarios_nuevos = Usuario.objects.filter(
                date_joined__date__gte=inicio,
                date_joined__date__lte=fin
            ).count()
            
            # Anuncios
            anuncios = AnuncioModel.objects.filter(
                fecha_publicacion__date__gte=inicio,
                fecha_publicacion__date__lte=fin
            ).count()
            
            # Citas
            citas = Cita.objects.filter(
                fecha_cita__gte=inicio,
                fecha_cita__lte=fin
            ).count()
            
            return {
                'inmuebles': inmuebles,
                'contratos': total_contratos,
                'ingresos': float(ingresos),
                'usuarios_nuevos': usuarios_nuevos,
                'anuncios': anuncios,
                'citas': citas,
            }
        
        metricas_1 = obtener_metricas_periodo(fecha_inicio_1, fecha_fin_1)
        metricas_2 = obtener_metricas_periodo(fecha_inicio_2, fecha_fin_2)
        
        # Calcular variaciones porcentuales
        def calcular_variacion(valor1, valor2):
            if valor2 == 0:
                return 0 if valor1 == 0 else 100
            return ((valor1 - valor2) / valor2) * 100
        
        variaciones = {
            'inmuebles': round(calcular_variacion(metricas_1['inmuebles'], metricas_2['inmuebles']), 2),
            'contratos': round(calcular_variacion(metricas_1['contratos'], metricas_2['contratos']), 2),
            'ingresos': round(calcular_variacion(metricas_1['ingresos'], metricas_2['ingresos']), 2),
            'usuarios_nuevos': round(calcular_variacion(metricas_1['usuarios_nuevos'], metricas_2['usuarios_nuevos']), 2),
            'anuncios': round(calcular_variacion(metricas_1['anuncios'], metricas_2['anuncios']), 2),
            'citas': round(calcular_variacion(metricas_1['citas'], metricas_2['citas']), 2),
        }
        
        data = {
            'periodo_1': {
                'inicio': fecha_inicio_1.isoformat(),
                'fin': fecha_fin_1.isoformat(),
                'metricas': metricas_1,
            },
            'periodo_2': {
                'inicio': fecha_inicio_2.isoformat(),
                'fin': fecha_fin_2.isoformat(),
                'metricas': metricas_2,
            },
            'variaciones_porcentuales': variaciones,
        }
        
        return Response({
            "status": 1,
            "error": 0,
            "message": "Reporte comparativo obtenido correctamente",
            "values": data
        })
        
    except Exception as e:
        return Response({
            "status": 0,
            "error": 1,
            "message": f"Error al generar reporte: {str(e)}",
            "values": {}
        })