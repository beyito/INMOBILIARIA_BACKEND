# views.py
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Contrato
from usuario.models import Usuario
from django.db.models import Avg
from django.contrib.auth.models import User
from inmueble.models import InmuebleModel as Inmueble
from contrato.models import Contrato
from rest_framework.views import APIView 
from django.conf import settings
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT, TA_RIGHT  # Agregar TA_LEFT y TA_RIGHT aquí
from reportlab.lib import colors
from django.http import HttpResponse
from decimal import Decimal, InvalidOperation
from inmobiliaria.permissions import requiere_actualizacion,requiere_creacion, requiere_eliminacion, requiere_lectura, requiere_permiso
from utils.encrypted_logger import registrar_accion, leer_logs
import os
import io
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
    

class ContratoServiciosAnticreticoView(APIView):
    def post(self, request):
        data = request.data
        print("DATA CONTRATO SERVICIOS ANTICRETICO INMOBILIARIOS", data)
        
        try:
            agente = Usuario.objects.get(id=data.get('agente_id'))
            print(agente)
            inmueble = Inmueble.objects.get(id=data.get('inmueble_id'))
            
            # ✅ BUSCAR contrato existente para el mismo agente e inmueble
            contrato_existente = Contrato.objects.filter(
                agente=agente,
                inmueble=inmueble,
                tipo_contrato='servicios'
            ).first()
            
            # Función helper para convertir a Decimal seguro
            def safe_decimal(value, default=0):
                if value is None or value == '':
                    return default
                try:
                    # Remover posibles comas y convertir a Decimal
                    if isinstance(value, str):
                        value = value.replace(',', '')
                    return Decimal(str(value))
                except (ValueError, TypeError, InvalidOperation):
                    return default
            
            if contrato_existente:
                # ✅ ACTUALIZAR contrato existente
                print(f"🔄 Actualizando contrato existente ID: {contrato_existente.id}")
                
                contrato_existente.ciudad = data.get('ciudad', contrato_existente.ciudad)
                contrato_existente.fecha_contrato = data.get('fecha', contrato_existente.fecha_contrato)
                
                # Partes del contrato
                contrato_existente.parte_contratante_nombre = data.get('cliente_nombre', contrato_existente.parte_contratante_nombre)
                contrato_existente.parte_contratante_ci = data.get('cliente_ci', contrato_existente.parte_contratante_ci)
                contrato_existente.parte_contratante_domicilio = data.get('cliente_domicilio', contrato_existente.parte_contratante_domicilio)
                
                contrato_existente.parte_contratada_nombre = data.get('empresa_nombre', contrato_existente.parte_contratada_nombre)
                contrato_existente.parte_contratada_ci = data.get('empresa_ci', contrato_existente.parte_contratada_ci)
                contrato_existente.parte_contratada_domicilio = data.get('empresa_domicilio', contrato_existente.parte_contratada_domicilio)
                
                # Términos económicos - CONVERSIÓN SEGURA A DECIMAL
                contrato_existente.comision_porcentaje = safe_decimal(data.get('comision'), contrato_existente.comision_porcentaje)
                contrato_existente.vigencia_dias = data.get('vigencia_dias', contrato_existente.vigencia_dias)
                contrato_existente.monto = safe_decimal(data.get('precio_inmueble'), contrato_existente.monto)
                
                # Calcular comisión_monto automáticamente si es necesario
                if contrato_existente.monto and contrato_existente.comision_porcentaje:
                    contrato_existente.comision_monto = (contrato_existente.monto * contrato_existente.comision_porcentaje) / 100
                
                # Actualizar detalles adicionales (merge con existentes)
                detalles_actuales = contrato_existente.detalles_adicionales or {}
                nuevos_detalles = {
                    'empresa_representante': data.get('empresa_representante', detalles_actuales.get('empresa_representante')),
                    'cliente_estado_civil': data.get('cliente_estado_civil', detalles_actuales.get('cliente_estado_civil')),
                    'cliente_profesion': data.get('cliente_profesion', detalles_actuales.get('cliente_profesion')),
                    'agente_nombre': data.get('agente_nombre', detalles_actuales.get('agente_nombre')),
                    'agente_ci': data.get('agente_ci', detalles_actuales.get('agente_ci')),
                    'agente_estado_civil': data.get('agente_estado_civil', detalles_actuales.get('agente_estado_civil')),
                    'agente_domicilio': data.get('agente_domicilio', detalles_actuales.get('agente_domicilio')),
                    'inmueble_direccion': data.get('inmueble_direccion', detalles_actuales.get('inmueble_direccion')),
                    'inmueble_superficie': data.get('inmueble_superficie', detalles_actuales.get('inmueble_superficie')),
                    'inmueble_distrito': data.get('inmueble_distrito', detalles_actuales.get('inmueble_distrito')),
                    'inmueble_manzana': data.get('inmueble_manzana', detalles_actuales.get('inmueble_manzana')),
                    'inmueble_lote': data.get('inmueble_lote', detalles_actuales.get('inmueble_lote')),
                    'inmueble_zona': data.get('inmueble_zona', detalles_actuales.get('inmueble_zona')),
                    'inmueble_matricula': data.get('inmueble_matricula', detalles_actuales.get('inmueble_matricula')),
                    'precio_inmueble': data.get('precio_inmueble', detalles_actuales.get('precio_inmueble')),
                    'direccion_oficina': data.get('direccion_oficina', detalles_actuales.get('direccion_oficina')),
                    'telefono_oficina': data.get('telefono_oficina', detalles_actuales.get('telefono_oficina')),
                    'email_oficina': data.get('email_oficina', detalles_actuales.get('email_oficina')),
                }
                contrato_existente.detalles_adicionales = nuevos_detalles
                
                contrato_existente.save()
                contrato = contrato_existente
                print(f"✅ Contrato actualizado - ID: {contrato.id}")
                print(f"💰 Monto guardado: {contrato.monto}")
                print(f"📊 Comisión %: {contrato.comision_porcentaje}")
                print(f"💵 Comisión monto: {contrato.comision_monto}")
                
            else:
                # ✅ CREAR nuevo contrato si no existe
                # Convertir valores a Decimal de forma segura
                precio_inmueble = safe_decimal(data.get('precio_inmueble'))
                comision_porcentaje = safe_decimal(data.get('comision'))
                
                # Calcular comisión_monto
                comision_monto = None
                if precio_inmueble and comision_porcentaje:
                    comision_monto = (precio_inmueble * comision_porcentaje) / 100
                
                contrato = Contrato.objects.create(
                    agente=agente,
                    inmueble=inmueble,
                    creado_por=request.user,
                    
                    tipo_contrato='servicios',
                    ciudad=data.get('ciudad', ''),
                    fecha_contrato=data.get('fecha', ''),
                    
                    parte_contratante_nombre=data.get('cliente_nombre', ''),
                    parte_contratante_ci=data.get('cliente_ci', ''),
                    parte_contratante_domicilio=data.get('cliente_domicilio', ''),
                    
                    parte_contratada_nombre=data.get('empresa_nombre', ''),
                    parte_contratada_ci=data.get('empresa_ci', ''),
                    parte_contratada_domicilio=data.get('empresa_domicilio', ''),
                    
                    monto=precio_inmueble,
                    comision_porcentaje=comision_porcentaje,
                    comision_monto=comision_monto,
                    vigencia_dias=data.get('vigencia_dias', 0),
                    
                    detalles_adicionales={
                        'empresa_representante': data.get('empresa_representante', ''),
                        'cliente_estado_civil': data.get('cliente_estado_civil', ''),
                        'cliente_profesion': data.get('cliente_profesion', ''),
                        'agente_nombre': data.get('agente_nombre', ''),
                        'agente_ci': data.get('agente_ci', ''),
                        'agente_estado_civil': data.get('agente_estado_civil', ''),
                        'agente_domicilio': data.get('agente_domicilio', ''),
                        'inmueble_direccion': data.get('inmueble_direccion', ''),
                        'inmueble_superficie': data.get('inmueble_superficie', ''),
                        'inmueble_distrito': data.get('inmueble_distrito', ''),
                        'inmueble_manzana': data.get('inmueble_manzana', ''),
                        'inmueble_lote': data.get('inmueble_lote', ''),
                        'inmueble_zona': data.get('inmueble_zona', ''),
                        'inmueble_matricula': data.get('inmueble_matricula', ''),
                        'precio_inmueble': data.get('precio_inmueble', ''),
                        'direccion_oficina': data.get('direccion_oficina', ''),
                        'telefono_oficina': data.get('telefono_oficina', ''),
                        'email_oficina': data.get('email_oficina', ''),
                    }
                )
                print(f"✅ Nuevo contrato creado - ID: {contrato.id}")
                print(f"💰 Monto guardado: {contrato.monto}")
                print(f"📊 Comisión %: {contrato.comision_porcentaje}")
                print(f"💵 Comisión monto: {contrato.comision_monto}")
            
        except Usuario.DoesNotExist:
            return Response({"error": "Agente no encontrado"}, status=400)
        except Inmueble.DoesNotExist:
            return Response({"error": "Inmueble no encontrado"}, status=400)
        except Exception as e:
            print(f"❌ Error al guardar/actualizar contrato: {e}")
            print(f"🔍 Tipo de error: {type(e)}")
            import traceback
            print(f"🔍 Traceback: {traceback.format_exc()}")
            return Response({"error": f"Error al procesar contrato: {str(e)}"}, status=500)
        
        # Ruta del archivo de plantilla
        plantilla_path = os.path.join(settings.BASE_DIR, "usuario/contratoServicioAnticreticoPDF/contrato_servicios_anticretico.txt")
        with open(plantilla_path, "r", encoding="utf-8") as f:
            contrato_text = f.read()

        # Reemplazar variables
        contrato_text = contrato_text.format(
            ciudad=data.get("ciudad", "________________"),
            fecha=data.get("fecha", "____/____/______"),
            empresa_nombre=data.get("empresa_nombre", "________________"),
            empresa_representante=data.get("empresa_representante", "________________"),
            empresa_ci=data.get("empresa_ci", "________________"),
            empresa_domicilio=data.get("empresa_domicilio", "________________"),
            
            cliente_nombre=data.get("cliente_nombre", "________________"),
            cliente_ci=data.get("cliente_ci", "________________"),
            cliente_estado_civil=data.get("cliente_estado_civil", "________________"),
            cliente_profesion=data.get("cliente_profesion", "________________"),
            cliente_domicilio=data.get("cliente_domicilio", "________________"),
            
            agente_nombre=data.get("agente_nombre", "________________"),
            agente_ci=data.get("agente_ci", "________________"),
            agente_estado_civil=data.get("agente_estado_civil", "________________"),
            agente_domicilio=data.get("agente_domicilio", "________________"),
            
            inmueble_direccion=data.get("inmueble_direccion", "________________"),
            inmueble_superficie=data.get("inmueble_superficie", "________________"),
            inmueble_distrito=data.get("inmueble_distrito", "________________"),
            inmueble_manzana=data.get("inmueble_manzana", "________________"),
            inmueble_lote=data.get("inmueble_lote", "________________"),
            inmueble_zona=data.get("inmueble_zona", "________________"),
            inmueble_matricula=data.get("inmueble_matricula", "________________"),
            precio_inmueble=data.get("precio_inmueble", "________________"),
            comision=data.get("comision", "____"),
            vigencia_dias=data.get("vigencia_dias", "____"),
            direccion_oficina=data.get("direccion_oficina", "________________"),
            telefono_oficina=data.get("telefono_oficina", "________________"),
            email_oficina=data.get("email_oficina", "________________"),
        )

        # Crear buffer en memoria
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=LETTER,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40
        )

        # Estilos
        styles = getSampleStyleSheet()
        titulo_style = ParagraphStyle(
            'Titulo',
            parent=styles['Heading1'],
            fontSize=14,
            leading=18,
            alignment=TA_CENTER,
            spaceAfter=20,
            textColor=colors.black,
            fontName='Helvetica-Bold'
        )
        clausula_titulo_style = ParagraphStyle(
            'ClausulaTitulo',
            parent=styles['Normal'],
            fontSize=11,
            leading=14,
            alignment=TA_LEFT,
            spaceAfter=6,
            textColor=colors.black,
            fontName='Helvetica-Bold'
        )
        clausula_style = ParagraphStyle(
            'Clausula',
            fontSize=10,
            leading=13,
            alignment=TA_JUSTIFY,
            spaceAfter=8,
        )
        firma_style = ParagraphStyle(
            'Firma',
            fontSize=10,
            leading=12,
            alignment=TA_CENTER,
        )
        footer_style = ParagraphStyle(
            'Footer',
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
            textColor=colors.grey,
        )

        story = []

        # Título
        story.append(Paragraph("CONTRATO PRIVADO DE PRESTACIÓN DE SERVICIOS INMOBILIARIOS", titulo_style))
        story.append(Spacer(1, 10))

        # Introducción
        intro_text = f"""Conste por el presente Contrato Privado de Servicios Inmobiliarios, que con el sólo reconocimiento de firmas surtirá los efectos de documento público, conforme al tenor de las siguientes cláusulas y condiciones:"""
        story.append(Paragraph(intro_text, clausula_style))
        story.append(Spacer(1, 15))

        # Separar por párrafos usando doble salto de línea
        lineas = contrato_text.strip().split("\n\n")

        # Agregar cláusulas
        for i, p in enumerate(lineas):
            if p.strip().startswith("PRIMERA:") or p.strip().startswith("SEGUNDA:") or p.strip().startswith("TERCERA:") or p.strip().startswith("CUARTA:") or p.strip().startswith("QUINTA:") or p.strip().startswith("SEXTA:") or p.strip().startswith("SÉPTIMA:") or p.strip().startswith("OCTAVA:") or p.strip().startswith("NOVENA:") or p.strip().startswith("DÉCIMA:") or p.strip().startswith("DÉCIMA PRIMERA:") or p.strip().startswith("DÉCIMA SEGUNDA:") or p.strip().startswith("DÉCIMA TERCERA:") or p.strip().startswith("DÉCIMA CUARTA:"):
                story.append(Paragraph(p.strip(), clausula_titulo_style))
            else:
                story.append(Paragraph(p.strip(), clausula_style))
            
            if i != len(lineas) - 1:
                story.append(Spacer(1, 8))

        # Fecha y lugar
        story.append(Spacer(1, 20))
        fecha_lugar = Paragraph(f"{data.get('ciudad', 'Trinidad')}, {data.get('fecha', '____/____/______')}.", clausula_titulo_style)
        story.append(fecha_lugar)
        story.append(Spacer(1, 25))

        # Firmas
        firmas_texto = f"""
        __________________________<br/>
        <b>{data.get('empresa_representante', '________________')}</b><br/>
        <i>{data.get('empresa_nombre', '________________')}</i><br/><br/><br/>

        __________________________<br/>
        <b>{data.get('cliente_nombre', '________________')}</b><br/>
        <i>PROPIETARIO/A</i><br/><br/><br/>

        __________________________<br/>
        <b>{data.get('agente_nombre', '________________')}</b><br/>
        <i>AGENTE ASOCIADO</i>
        """
        story.append(Paragraph(firmas_texto, firma_style))

        # Footer
        story.append(Spacer(1, 20))
        footer_text = f"""
        {data.get('direccion_oficina', '________________')}<br/>
        {data.get('telefono_oficina', '________________')}<br/>
        {data.get('email_oficina', '________________')}<br/>
        <i>Cada oficina es de propiedad y operación independiente</i>
        """
        story.append(Paragraph(footer_text, footer_style))

        # Generar PDF
        doc.build(story)
        buffer.seek(0)

        # Devolver PDF
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="contrato_servicios_anticretico_inmobiliarios_{data.get("cliente_nombre","cliente")}.pdf"'
        return response