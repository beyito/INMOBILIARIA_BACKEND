# views.py
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Contrato
from usuario.models import Usuario
from django.db.models import Avg
from .serializers import ContratoSerializer
from inmueble.models import InmuebleModel

from django.http import HttpResponse
from fpdf import FPDF
import os
from django.conf import settings
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
#CONTRATO ANTICRETICO DUEÑO - AGENTE
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
        
@api_view(['POST'])
# @requiere_permiso("Contrato", "crear")
def crear_contrato_anticretico(request):
    """
    Crea un nuevo contrato de anticrético (Dueño-Cliente).
    YA NO GENERA EL PDF, solo crea el registro.
    """
    try:
        data = request.data
        
        # 1. Obtener los objetos principales
        try:
            inmueble_id = data.get('inmueble_id')
            agente_id = data.get('agente_id')

            inmueble = InmuebleModel.objects.get(id=inmueble_id)
            agente = Usuario.objects.get(id=agente_id)
            propietario = inmueble.cliente 
            
            if not propietario:
                return Response({"error": f"El inmueble (ID: {inmueble.id}) no tiene un 'Cliente' (Dueño) asignado. Edita el inmueble y asígnale uno."}, status=status.HTTP_400_BAD_REQUEST)

            if inmueble.tipo_operacion != 'anticretico':
                return Response(
                    {"error": f"El inmueble '{inmueble.titulo}' (ID: {inmueble.id}) está listado para '{inmueble.tipo_operacion}', no para 'anticretico'."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
        except InmuebleModel.DoesNotExist:
            return Response({"error": f"Inmueble con id={inmueble_id} no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except Usuario.DoesNotExist:
            return Response({"error": f"Agente con id={agente_id} o Propietario no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        # 2. Preparar los datos para guardar en el modelo Contrato
        datos_contrato = {
            'agente': agente.id,
            'inmueble': inmueble.id,
            'tipo_contrato': 'anticretico',
            'estado': 'pendiente',
            'ciudad': data.get('ciudad'),
            'fecha_contrato': data.get('fecha_contrato'),
            
            'parte_contratante_nombre': propietario.nombre, 
            'parte_contratante_ci': propietario.ci,
            'parte_contratante_domicilio': propietario.ubicacion,
            
            'parte_contratada_nombre': data.get('cliente_nombre'),
            'parte_contratada_ci': data.get('cliente_ci'),
            'parte_contratada_domicilio': data.get('cliente_domicilio'),
            
            'monto': data.get('monto'),
            'comision_porcentaje': data.get('comision_porcentaje'),
            'vigencia_meses': data.get('vigencia_meses'),
            
            'creado_por': request.user.id if request.user.is_authenticated else agente.id
        }

        # 3. Validar y Guardar (Paso Inicial)
        serializer = ContratoSerializer(data=datos_contrato, context={'request': request})
        if serializer.is_valid():
            # Guardamos el contrato en la BD
            serializer.save()

            # --- ❌ BLOQUE DE PDF (WEASYPRINT) ELIMINADO ---
            
            # Devolver los datos del contrato
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response({
            "status": 0, "error": 1,
            "message": f"Error inesperado al crear contrato: {str(e)}",
            "values": {}
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
@api_view(['GET'])
# @requiere_permiso("Contrato", "leer")
def descargar_contrato_pdf(request, contrato_id):
    """
    Genera un PDF profesional usando un .txt y fpdf.
    """
    try:
        # 1. Buscar el contrato y sus relaciones
        # Usamos 'select_related' para cargar los datos del inmueble y agente
        # en una sola consulta a la BD (más eficiente).
        contrato = Contrato.objects.select_related('inmueble', 'agente').get(id=contrato_id)
        
        # 2. Cargar la plantilla .txt
        # (Usamos la ruta corregida que apunta a la carpeta 'templates')
        template_path = os.path.join(settings.BASE_DIR, 'contrato', 'templates', 'plantilla_anticretico.txt')
        
        with open(template_path, 'r', encoding='utf-8') as f:
            template_string = f.read()

        # 3. Preparar los datos y rellenar la plantilla
        # (Añadimos más datos de los modelos relacionados)
        contexto = {
            "ciudad": contrato.ciudad,
            "fecha": contrato.fecha_contrato.strftime("%d de %B de %Y"),
            
            "propietario_nombre": contrato.parte_contratante_nombre,
            "propietario_ci": contrato.parte_contratante_ci,
            "propietario_domicilio": contrato.parte_contratante_domicilio,
            
            "anticresista_nombre": contrato.parte_contratada_nombre,
            "anticresista_ci": contrato.parte_contratada_ci,
            "anticresista_domicilio": contrato.parte_contratada_domicilio,
            
            "inmueble_direccion": contrato.inmueble.direccion,
            "inmueble_superficie": str(contrato.inmueble.superficie),
            
            "monto": str(contrato.monto),
            # (Opcional: puedes instalar 'num2words' para convertir el monto a texto)
            "monto_literal": f"{contrato.monto:,.2f}", # De momento usamos el número
            
            "meses": str(contrato.vigencia_meses),
            
            "agente_nombre": contrato.agente.nombre,
            "agente_ci": contrato.agente.ci,
        }
        
        # Llenamos los {placeholders} en el texto
        texto_final = template_string.format(**contexto)

        # 4. Generar el PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=11)
        
        # Añadimos un margen
        pdf.set_left_margin(20)
        pdf.set_right_margin(20)
        pdf.set_top_margin(20)
        
        # Usar multi_cell para que el texto se ajuste
        pdf.multi_cell(0, 5, texto_final.encode('latin-1', 'replace').decode('latin-1'))
        
        # Convertir el PDF a bytes
        pdf_output = pdf.output(dest='S').encode('latin-1')

        # 5. Crear la respuesta HTTP
        nombre_archivo = f"contrato_anticretico_{contrato.id}.pdf"
        response = HttpResponse(pdf_output, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
        
        return response

    except Contrato.DoesNotExist:
        return Response({"error": "Contrato no encontrado"}, status=status.HTTP_404_NOT_FOUND)
    except FileNotFoundError:
        return Response({
            "status": 0, "error": 1,
            "message": "Error: No se encontró el archivo 'plantilla_anticretico.txt'. Asegúrate de que esté en 'contrato/templates/'.",
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        return Response({
            "status": 0, "error": 1,
            "message": f"Error al generar PDF: {str(e)}",
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
@api_view(['GET'])
# @requiere_permiso("Contrato", "leer")
def detalle_contrato(request, contrato_id):
    """
    (AC 1 y 2) Busca un contrato por ID y muestra todos sus detalles.
    """
    try:
        contrato = Contrato.objects.select_related('inmueble', 'agente').get(id=contrato_id)
        serializer = ContratoSerializer(contrato, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Contrato.DoesNotExist:
        return Response({"error": "Contrato no encontrado"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": f"Error inesperado: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PATCH'])
# @requiere_permiso("Contrato", "actualizar")
def aprobar_contrato(request, contrato_id):
    """
    (Lógica de AC 3) Aprueba un contrato que está 'pendiente'.
    Lo pasa de 'pendiente' a 'activo' (vigente).
    """
    try:
        contrato = Contrato.objects.get(id=contrato_id)
        
        if contrato.estado != 'pendiente':
            return Response(
                {"error": f"El contrato no se puede aprobar, su estado actual es '{contrato.estado}'."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        contrato.estado = 'activo'
        contrato.save()
        
        serializer = ContratoSerializer(contrato, context={'request': request})
        return Response({
            "message": "Contrato aprobado y vigente.",
            "contrato": serializer.data
        }, status=status.HTTP_200_OK)

    except Contrato.DoesNotExist:
        return Response({"error": "Contrato no encontrado"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": f"Error inesperado: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PATCH'])
# @requiere_permiso("Contrato", "actualizar")
def finalizar_contrato(request, contrato_id):
    """
    (AC 4 y 5) Finaliza un contrato que está 'activo' (vigente).
    Lo pasa de 'activo' a 'finalizado'.
    """
    try:
        contrato = Contrato.objects.get(id=contrato_id)
        
        if contrato.estado != 'activo':
            return Response(
                {"error": f"El contrato no se puede finalizar, su estado actual es '{contrato.estado}' (debe estar 'activo')."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        contrato.estado = 'finalizado'
        # (Aquí podrías añadir lógica para la garantía si la tuvieras en el modelo)
        # ej: contrato.garantia_devuelta = True
        contrato.save()
        
        # (AC 5) Mensaje de éxito
        return Response({
            "message": "Contrato finalizado y garantía actualizada."
        }, status=status.HTTP_200_OK)

    except Contrato.DoesNotExist:
        return Response({"error": "Contrato no encontrado"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": f"Error inesperado: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)