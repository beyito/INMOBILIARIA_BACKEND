# contrato/views.py
# contrato/views.py
from datetime import timedelta
import os, io
from decimal import Decimal, InvalidOperation

from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from django.http import HttpResponse, FileResponse
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from fpdf import FPDF
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib import colors
from reportlab.lib.units import cm

from usuario.models import Usuario
from inmueble.models import InmuebleModel as Inmueble
from inmueble.models import InmuebleModel
from contrato.models import Contrato
from contrato.serializers import ContratoSerializer
from inmobiliaria.permissions import (
    requiere_actualizacion,
    requiere_creacion,
    requiere_eliminacion,
    requiere_lectura,
    requiere_permiso,
)
from utils.encrypted_logger import registrar_accion, leer_logs


from django.http import FileResponse, Http404

import os


@api_view(["GET"])
# @requiere_permiso("Comision", "leer")
def dashboard_comisiones(request):
    """
    Dashboard de control de comisiones para administradores
    """
    try:
        # Filtros por fecha (opcionales)
        fecha_inicio = request.GET.get("fecha_inicio")
        fecha_fin = request.GET.get("fecha_fin")
        incluir_servicios = (
            request.GET.get("incluir_servicios", "false").lower() == "true"
        )

        # Base queryset
        if incluir_servicios:
            contratos = Contrato.objects.filter(estado="activo")
        else:
            contratos = Contrato.objects.filter(estado="activo").exclude(
                tipo_contrato="servicios"
            )

        # Aplicar filtros de fecha si existen
        if fecha_inicio:
            contratos = contratos.filter(fecha_contrato__gte=fecha_inicio)
        if fecha_fin:
            contratos = contratos.filter(fecha_contrato__lte=fecha_fin)
            incluir_servicios = (
                request.GET.get("incluir_servicios", "false").lower() == "true"
            )

        hay_contratos_servicios = Contrato.objects.filter(
            tipo_contrato="servicios", estado="activo"
        ).exists()

        # Base queryset - excluir servicios por defecto
        if incluir_servicios:
            contratos = Contrato.objects.filter(estado="activo")
        else:
            contratos = Contrato.objects.filter(estado="activo").exclude(
                tipo_contrato="servicios"
            )

        # Estadísticas generales
        stats_generales = {
            "total_contratos": contratos.count(),
            "total_comisiones": float(
                contratos.aggregate(Sum("comision_monto"))["comision_monto__sum"] or 0
            ),
            "comision_promedio": float(
                contratos.aggregate(avg=Avg("comision_porcentaje"))["avg"] or 0
            ),
        }

        # Comisiones por agente
        comisiones_agente = (
            contratos.values("agente__id", "agente__nombre", "agente__username")
            .annotate(
                total_contratos=Count("id"),
                total_comision=Sum("comision_monto"),
                comision_promedio=Avg("comision_porcentaje"),
            )
            .order_by("-total_comision")
        )

        # Comisiones por tipo de contrato
        comisiones_tipo = (
            contratos.values("tipo_contrato")
            .annotate(total_contratos=Count("id"), total_comision=Sum("comision_monto"))
            .order_by("-total_comision")
        )

        # Comisiones mensuales (últimos 6 meses)
        seis_meses_atras = timezone.now().date() - timedelta(days=180)
        comisiones_mensuales = (
            contratos.filter(fecha_contrato__gte=seis_meses_atras)
            .extra(
                {
                    "mes": "EXTRACT(month FROM fecha_contrato)",
                    "ano": "EXTRACT(year FROM fecha_contrato)",
                }
            )
            .values("mes", "ano")
            .annotate(total_comision=Sum("comision_monto"), total_contratos=Count("id"))
            .order_by("-ano", "-mes")[:6]
        )

        # Top 5 contratos con mayor comisión
        top_contratos = contratos.select_related("agente", "inmueble").order_by(
            "-comision_monto"
        )[:5]
        top_contratos = contratos.select_related("agente", "inmueble").order_by(
            "-comision_monto"
        )[:5]
        top_contratos_data = []
        for contrato in top_contratos:
            top_contratos_data.append(
                {
                    "id": contrato.id,
                    "cliente": contrato.parte_contratante_nombre,
                    "agente": contrato.agente.nombre,
                    "inmueble": (
                        contrato.inmueble.titulo if contrato.inmueble else "N/A"
                    ),
                    "tipo_contrato": contrato.get_tipo_contrato_display(),
                    "monto_contrato": float(contrato.monto or 0),  # ✅ NUEVO
                    "comision_monto": float(contrato.comision_monto or 0),
                    "comision_porcentaje": float(contrato.comision_porcentaje or 0),
                    "fecha": contrato.fecha_contrato,
                }
            )
        if incluir_servicios:
            stats_generales["contratos_servicios"] = contratos.filter(
                tipo_contrato="servicios"
            ).count()

        return Response(
            {
                "status": 1,
                "error": 0,
                "message": "DASHBOARD DE CONTROL DE COMISIONES",
                "values": {
                    "stats_generales": stats_generales,
                    "comisiones_agente": comisiones_agente,
                    "comisiones_tipo": comisiones_tipo,
                    "comisiones_mensuales": comisiones_mensuales,
                    "top_contratos": top_contratos_data,
                    "hay_contratos_servicios": hay_contratos_servicios,
                },
            }
        )

    except Exception as e:
        return Response(
            {
                "status": 0,
                "error": 1,
                "message": f"Error al generar dashboard: {str(e)}",
                "values": {},
            },
            status=500,
        )


# CONTRATO ANTICRETICO DUEÑO - AGENTE
@api_view(["GET"])
# @requiere_permiso("Comision", "leer")
def detalle_comisiones_agente(request, agente_id):
    """
    Detalle de comisiones de un agente específico
    """
    try:
        agente = Usuario.objects.get(id=agente_id, grupo__nombre="agente")

        # Filtros
        fecha_inicio = request.GET.get("fecha_inicio")
        fecha_fin = request.GET.get("fecha_fin")
        incluir_servicios = (
            request.GET.get("incluir_servicios", "false").lower() == "true"
        )

        # Base queryset - aplicar filtro de servicios
        if incluir_servicios:
            contratos_agente = Contrato.objects.filter(agente=agente, estado="activo")
        else:
            contratos_agente = Contrato.objects.filter(
                agente=agente, estado="activo"
            ).exclude(tipo_contrato="servicios")

        if fecha_inicio:
            contratos_agente = contratos_agente.filter(fecha_contrato__gte=fecha_inicio)
        if fecha_fin:
            contratos_agente = contratos_agente.filter(fecha_contrato__lte=fecha_fin)

        # Estadísticas del agente
        stats_agente = {
            "agente_nombre": agente.nombre,
            "agente_username": agente.username,
            "total_contratos": contratos_agente.count(),
            "total_comision": float(
                contratos_agente.aggregate(Sum("comision_monto"))["comision_monto__sum"]
                or 0
            ),
            "comision_promedio": float(
                contratos_agente.aggregate(avg=Avg("comision_porcentaje"))["avg"] or 0
            ),
            "monto_total_contratos": float(
                contratos_agente.aggregate(Sum("monto"))["monto__sum"] or 0
            ),
        }

        # Contratos del agente
        contratos_data = []
        for contrato in contratos_agente.select_related("inmueble").order_by(
            "-fecha_contrato"
        ):
            contratos_data.append(
                {
                    "id": contrato.id,
                    "cliente": contrato.parte_contratante_nombre,
                    "inmueble": (
                        contrato.inmueble.titulo if contrato.inmueble else "N/A"
                    ),
                    "tipo_contrato": contrato.get_tipo_contrato_display(),
                    "monto_contrato": float(contrato.monto or 0),
                    "comision_monto": float(contrato.comision_monto or 0),
                    "comision_porcentaje": float(contrato.comision_porcentaje or 0),
                    "fecha_contrato": contrato.fecha_contrato,
                    "vigencia_dias": contrato.vigencia_dias,
                    "estado": contrato.estado,
                }
            )

        # Comisiones por tipo de contrato
        comisiones_tipo = (
            contratos_agente.values("tipo_contrato")
            .annotate(
                total_contratos=Count("id"),
                total_comision=Sum("comision_monto"),
                monto_total=Sum("monto"),
            )
            .order_by("-total_comision")
        )

        return Response(
            {
                "status": 1,
                "error": 0,
                "message": f"DETALLE DE COMISIONES - {agente.nombre}",
                "values": {
                    "stats_agente": stats_agente,
                    "contratos": contratos_data,
                    "comisiones_tipo": comisiones_tipo,
                },
            }
        )

    except Usuario.DoesNotExist:
        return Response(
            {"status": 0, "error": 1, "message": "Agente no encontrado", "values": {}},
            status=404,
        )
    except Exception as e:
        return Response(
            {
                "status": 0,
                "error": 1,
                "message": f"Error al cargar detalle: {str(e)}",
                "values": {},
            },
            status=500,
        )


@api_view(["POST"])
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
            inmueble_id = data.get("inmueble_id")
            agente_id = data.get("agente_id")

            inmueble = InmuebleModel.objects.get(id=inmueble_id)
            agente = Usuario.objects.get(id=agente_id)
            propietario = inmueble.cliente

            if not propietario:
                return Response(
                    {
                        "error": f"El inmueble (ID: {inmueble.id}) no tiene un 'Cliente' (Dueño) asignado. Edita el inmueble y asígnale uno."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if inmueble.tipo_operacion != "anticretico":
                return Response(
                    {
                        "error": f"El inmueble '{inmueble.titulo}' (ID: {inmueble.id}) está listado para '{inmueble.tipo_operacion}', no para 'anticretico'."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except InmuebleModel.DoesNotExist:
            return Response(
                {"error": f"Inmueble con id={inmueble_id} no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Usuario.DoesNotExist:
            return Response(
                {"error": f"Agente con id={agente_id} o Propietario no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 2. Preparar los datos para guardar en el modelo Contrato
        datos_contrato = {
            "agente": agente.id,
            "inmueble": inmueble.id,
            "tipo_contrato": "anticretico",
            "estado": "pendiente",
            "ciudad": data.get("ciudad"),
            "fecha_contrato": data.get("fecha_contrato"),
            "parte_contratante_nombre": propietario.nombre,
            "parte_contratante_ci": propietario.ci,
            "parte_contratante_domicilio": propietario.ubicacion,
            "parte_contratada_nombre": data.get("cliente_nombre"),
            "parte_contratada_ci": data.get("cliente_ci"),
            "parte_contratada_domicilio": data.get("cliente_domicilio"),
            "monto": data.get("monto"),
            "comision_porcentaje": data.get("comision_porcentaje"),
            "vigencia_meses": data.get("vigencia_meses"),
            "creado_por": (
                request.user.id if request.user.is_authenticated else agente.id
            ),
        }

        # 3. Validar y Guardar (Paso Inicial)
        serializer = ContratoSerializer(
            data=datos_contrato, context={"request": request}
        )
        if serializer.is_valid():
            # Guardamos el contrato en la BD
            serializer.save()

            # --- ❌ BLOQUE DE PDF (WEASYPRINT) ELIMINADO ---

            # Devolver los datos del contrato
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response(
            {
                "status": 0,
                "error": 1,
                "message": f"Error inesperado al crear contrato: {str(e)}",
                "values": {},
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
# @requiere_permiso("Contrato", "leer")
def descargar_contrato_pdf(request, contrato_id):
    """
    Genera un PDF profesional usando un .txt y fpdf.
    """
    try:
        # 1. Buscar el contrato y sus relaciones
        # Usamos 'select_related' para cargar los datos del inmueble y agente
        # en una sola consulta a la BD (más eficiente).
        contrato = Contrato.objects.select_related("inmueble", "agente").get(
            id=contrato_id
        )

        # 2. Cargar la plantilla .txt
        # (Usamos la ruta corregida que apunta a la carpeta 'templates')
        template_path = os.path.join(
            settings.BASE_DIR, "contrato", "templates", "plantilla_anticretico.txt"
        )

        with open(template_path, "r", encoding="utf-8") as f:
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
            "monto_literal": f"{contrato.monto:,.2f}",  # De momento usamos el número
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
        pdf.multi_cell(0, 5, texto_final.encode("latin-1", "replace").decode("latin-1"))

        # Convertir el PDF a bytes
        pdf_output = pdf.output(dest="S").encode("latin-1")

        # 5. Crear la respuesta HTTP
        nombre_archivo = f"contrato_anticretico_{contrato.id}.pdf"
        response = HttpResponse(pdf_output, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{nombre_archivo}"'

        return response

    except Contrato.DoesNotExist:
        return Response(
            {"error": "Contrato no encontrado"}, status=status.HTTP_404_NOT_FOUND
        )
    except FileNotFoundError:
        return Response(
            {
                "status": 0,
                "error": 1,
                "message": "Error: No se encontró el archivo 'plantilla_anticretico.txt'. Asegúrate de que esté en 'contrato/templates/'.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception as e:
        return Response(
            {
                "status": 0,
                "error": 1,
                "message": f"Error al generar PDF: {str(e)}",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
# @requiere_permiso("Contrato", "leer")
def detalle_contrato(request, contrato_id):
    """
    (AC 1 y 2) Busca un contrato por ID y muestra todos sus detalles.
    """
    try:
        contrato = Contrato.objects.select_related("inmueble", "agente").get(
            id=contrato_id
        )
        serializer = ContratoSerializer(contrato, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Contrato.DoesNotExist:
        return Response(
            {"error": "Contrato no encontrado"}, status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {"error": f"Error inesperado: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["PATCH"])
# @requiere_permiso("Contrato", "actualizar")
def aprobar_contrato(request, contrato_id):
    """
    (Lógica de AC 3) Aprueba un contrato que está 'pendiente'.
    Lo pasa de 'pendiente' a 'activo' (vigente).
    """
    try:
        contrato = Contrato.objects.get(id=contrato_id)

        if contrato.estado != "pendiente":
            return Response(
                {
                    "error": f"El contrato no se puede aprobar, su estado actual es '{contrato.estado}'."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        contrato.estado = "activo"
        contrato.save()

        serializer = ContratoSerializer(contrato, context={"request": request})
        return Response(
            {"message": "Contrato aprobado y vigente.", "contrato": serializer.data},
            status=status.HTTP_200_OK,
        )

    except Contrato.DoesNotExist:
        return Response(
            {"error": "Contrato no encontrado"}, status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {"error": f"Error inesperado: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["PATCH"])
# @requiere_permiso("Contrato", "actualizar")
def finalizar_contrato(request, contrato_id):
    """
    (AC 4 y 5) Finaliza un contrato que está 'activo' (vigente).
    Lo pasa de 'activo' a 'finalizado'.
    """
    try:
        contrato = Contrato.objects.get(id=contrato_id)

        if contrato.estado != "activo":
            return Response(
                {
                    "error": f"El contrato no se puede finalizar, su estado actual es '{contrato.estado}' (debe estar 'activo')."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        contrato.estado = "finalizado"
        # (Aquí podrías añadir lógica para la garantía si la tuvieras en el modelo)
        # ej: contrato.garantia_devuelta = True
        contrato.save()

        # (AC 5) Mensaje de éxito
        return Response(
            {"message": "Contrato finalizado y garantía actualizada."},
            status=status.HTTP_200_OK,
        )

    except Contrato.DoesNotExist:
        return Response(
            {"error": "Contrato no encontrado"}, status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {"error": f"Error inesperado: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class ContratoServiciosAnticreticoView(APIView):
    def post(self, request):
        data = request.data
        print("DATA CONTRATO SERVICIOS ANTICRETICO INMOBILIARIOS", data)

        try:
            agente = Usuario.objects.get(id=data.get("agente_id"))
            print(agente)
            inmueble = Inmueble.objects.get(id=data.get("inmueble_id"))

            # ✅ BUSCAR contrato existente para el mismo agente e inmueble
            contrato_existente = Contrato.objects.filter(
                agente=agente, inmueble=inmueble, tipo_contrato="servicios"
            ).first()

            # Función helper para convertir a Decimal seguro
            def safe_decimal(value, default=0):
                if value is None or value == "":
                    return default
                try:
                    # Remover posibles comas y convertir a Decimal
                    if isinstance(value, str):
                        value = value.replace(",", "")
                    return Decimal(str(value))
                except (ValueError, TypeError, InvalidOperation):
                    return default

            if contrato_existente:
                # ✅ ACTUALIZAR contrato existente
                print(f"🔄 Actualizando contrato existente ID: {contrato_existente.id}")

                contrato_existente.ciudad = data.get(
                    "ciudad", contrato_existente.ciudad
                )
                contrato_existente.fecha_contrato = data.get(
                    "fecha", contrato_existente.fecha_contrato
                )

                # Partes del contrato
                contrato_existente.parte_contratante_nombre = data.get(
                    "cliente_nombre", contrato_existente.parte_contratante_nombre
                )
                contrato_existente.parte_contratante_ci = data.get(
                    "cliente_ci", contrato_existente.parte_contratante_ci
                )
                contrato_existente.parte_contratante_domicilio = data.get(
                    "cliente_domicilio", contrato_existente.parte_contratante_domicilio
                )

                contrato_existente.parte_contratada_nombre = data.get(
                    "empresa_nombre", contrato_existente.parte_contratada_nombre
                )
                contrato_existente.parte_contratada_ci = data.get(
                    "empresa_ci", contrato_existente.parte_contratada_ci
                )
                contrato_existente.parte_contratada_domicilio = data.get(
                    "empresa_domicilio", contrato_existente.parte_contratada_domicilio
                )

                # Términos económicos - CONVERSIÓN SEGURA A DECIMAL
                contrato_existente.comision_porcentaje = safe_decimal(
                    data.get("comision"), contrato_existente.comision_porcentaje
                )
                contrato_existente.vigencia_dias = data.get(
                    "vigencia_dias", contrato_existente.vigencia_dias
                )
                contrato_existente.monto = safe_decimal(
                    data.get("precio_inmueble"), contrato_existente.monto
                )

                # Calcular comisión_monto automáticamente si es necesario
                if contrato_existente.monto and contrato_existente.comision_porcentaje:
                    contrato_existente.comision_monto = (
                        contrato_existente.monto
                        * contrato_existente.comision_porcentaje
                    ) / 100

                # Actualizar detalles adicionales (merge con existentes)
                detalles_actuales = contrato_existente.detalles_adicionales or {}
                nuevos_detalles = {
                    "empresa_representante": data.get(
                        "empresa_representante",
                        detalles_actuales.get("empresa_representante"),
                    ),
                    "cliente_estado_civil": data.get(
                        "cliente_estado_civil",
                        detalles_actuales.get("cliente_estado_civil"),
                    ),
                    "cliente_profesion": data.get(
                        "cliente_profesion", detalles_actuales.get("cliente_profesion")
                    ),
                    "agente_nombre": data.get(
                        "agente_nombre", detalles_actuales.get("agente_nombre")
                    ),
                    "agente_ci": data.get(
                        "agente_ci", detalles_actuales.get("agente_ci")
                    ),
                    "agente_estado_civil": data.get(
                        "agente_estado_civil",
                        detalles_actuales.get("agente_estado_civil"),
                    ),
                    "agente_domicilio": data.get(
                        "agente_domicilio", detalles_actuales.get("agente_domicilio")
                    ),
                    "inmueble_direccion": data.get(
                        "inmueble_direccion",
                        detalles_actuales.get("inmueble_direccion"),
                    ),
                    "inmueble_superficie": data.get(
                        "inmueble_superficie",
                        detalles_actuales.get("inmueble_superficie"),
                    ),
                    "inmueble_distrito": data.get(
                        "inmueble_distrito", detalles_actuales.get("inmueble_distrito")
                    ),
                    "inmueble_manzana": data.get(
                        "inmueble_manzana", detalles_actuales.get("inmueble_manzana")
                    ),
                    "inmueble_lote": data.get(
                        "inmueble_lote", detalles_actuales.get("inmueble_lote")
                    ),
                    "inmueble_zona": data.get(
                        "inmueble_zona", detalles_actuales.get("inmueble_zona")
                    ),
                    "inmueble_matricula": data.get(
                        "inmueble_matricula",
                        detalles_actuales.get("inmueble_matricula"),
                    ),
                    "precio_inmueble": data.get(
                        "precio_inmueble", detalles_actuales.get("precio_inmueble")
                    ),
                    "direccion_oficina": data.get(
                        "direccion_oficina", detalles_actuales.get("direccion_oficina")
                    ),
                    "telefono_oficina": data.get(
                        "telefono_oficina", detalles_actuales.get("telefono_oficina")
                    ),
                    "email_oficina": data.get(
                        "email_oficina", detalles_actuales.get("email_oficina")
                    ),
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
                precio_inmueble = safe_decimal(data.get("precio_inmueble"))
                comision_porcentaje = safe_decimal(data.get("comision"))

                # Calcular comisión_monto
                comision_monto = None
                if precio_inmueble and comision_porcentaje:
                    comision_monto = (precio_inmueble * comision_porcentaje) / 100

                contrato = Contrato.objects.create(
                    agente=agente,
                    inmueble=inmueble,
                    creado_por=request.user,
                    tipo_contrato="servicios",
                    ciudad=data.get("ciudad", ""),
                    fecha_contrato=data.get("fecha", ""),
                    parte_contratante_nombre=data.get("cliente_nombre", ""),
                    parte_contratante_ci=data.get("cliente_ci", ""),
                    parte_contratante_domicilio=data.get("cliente_domicilio", ""),
                    parte_contratada_nombre=data.get("empresa_nombre", ""),
                    parte_contratada_ci=data.get("empresa_ci", ""),
                    parte_contratada_domicilio=data.get("empresa_domicilio", ""),
                    monto=precio_inmueble,
                    comision_porcentaje=comision_porcentaje,
                    comision_monto=comision_monto,
                    vigencia_dias=data.get("vigencia_dias", 0),
                    detalles_adicionales={
                        "empresa_representante": data.get("empresa_representante", ""),
                        "cliente_estado_civil": data.get("cliente_estado_civil", ""),
                        "cliente_profesion": data.get("cliente_profesion", ""),
                        "agente_nombre": data.get("agente_nombre", ""),
                        "agente_ci": data.get("agente_ci", ""),
                        "agente_estado_civil": data.get("agente_estado_civil", ""),
                        "agente_domicilio": data.get("agente_domicilio", ""),
                        "inmueble_direccion": data.get("inmueble_direccion", ""),
                        "inmueble_superficie": data.get("inmueble_superficie", ""),
                        "inmueble_distrito": data.get("inmueble_distrito", ""),
                        "inmueble_manzana": data.get("inmueble_manzana", ""),
                        "inmueble_lote": data.get("inmueble_lote", ""),
                        "inmueble_zona": data.get("inmueble_zona", ""),
                        "inmueble_matricula": data.get("inmueble_matricula", ""),
                        "precio_inmueble": data.get("precio_inmueble", ""),
                        "direccion_oficina": data.get("direccion_oficina", ""),
                        "telefono_oficina": data.get("telefono_oficina", ""),
                        "email_oficina": data.get("email_oficina", ""),
                    },
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
            return Response(
                {"error": f"Error al procesar contrato: {str(e)}"}, status=500
            )

        # Ruta del archivo de plantilla
        plantilla_path = os.path.join(
            settings.BASE_DIR,
            "usuario/contratoServicioAnticreticoPDF/contrato_servicios_anticretico.txt",
        )
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
            bottomMargin=40,
        )

        # Estilos
        styles = getSampleStyleSheet()
        titulo_style = ParagraphStyle(
            "Titulo",
            parent=styles["Heading1"],
            fontSize=14,
            leading=18,
            alignment=TA_CENTER,
            spaceAfter=20,
            textColor=colors.black,
            fontName="Helvetica-Bold",
        )
        clausula_titulo_style = ParagraphStyle(
            "ClausulaTitulo",
            parent=styles["Normal"],
            fontSize=11,
            leading=14,
            alignment=TA_LEFT,
            spaceAfter=6,
            textColor=colors.black,
            fontName="Helvetica-Bold",
        )
        clausula_style = ParagraphStyle(
            "Clausula",
            fontSize=10,
            leading=13,
            alignment=TA_JUSTIFY,
            spaceAfter=8,
        )
        firma_style = ParagraphStyle(
            "Firma",
            fontSize=10,
            leading=12,
            alignment=TA_CENTER,
        )
        footer_style = ParagraphStyle(
            "Footer",
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
            textColor=colors.grey,
        )

        story = []

        # Título
        story.append(
            Paragraph(
                "CONTRATO PRIVADO DE PRESTACIÓN DE SERVICIOS INMOBILIARIOS",
                titulo_style,
            )
        )
        story.append(Spacer(1, 10))

        # Introducción
        intro_text = f"""Conste por el presente Contrato Privado de Servicios Inmobiliarios, que con el sólo reconocimiento de firmas surtirá los efectos de documento público, conforme al tenor de las siguientes cláusulas y condiciones:"""
        story.append(Paragraph(intro_text, clausula_style))
        story.append(Spacer(1, 15))

        # Separar por párrafos usando doble salto de línea
        lineas = contrato_text.strip().split("\n\n")

        # Agregar cláusulas
        for i, p in enumerate(lineas):
            if (
                p.strip().startswith("PRIMERA:")
                or p.strip().startswith("SEGUNDA:")
                or p.strip().startswith("TERCERA:")
                or p.strip().startswith("CUARTA:")
                or p.strip().startswith("QUINTA:")
                or p.strip().startswith("SEXTA:")
                or p.strip().startswith("SÉPTIMA:")
                or p.strip().startswith("OCTAVA:")
                or p.strip().startswith("NOVENA:")
                or p.strip().startswith("DÉCIMA:")
                or p.strip().startswith("DÉCIMA PRIMERA:")
                or p.strip().startswith("DÉCIMA SEGUNDA:")
                or p.strip().startswith("DÉCIMA TERCERA:")
                or p.strip().startswith("DÉCIMA CUARTA:")
            ):
                story.append(Paragraph(p.strip(), clausula_titulo_style))
            else:
                story.append(Paragraph(p.strip(), clausula_style))

            if i != len(lineas) - 1:
                story.append(Spacer(1, 8))

        # Fecha y lugar
        story.append(Spacer(1, 20))
        fecha_lugar = Paragraph(
            f"{data.get('ciudad', 'Trinidad')}, {data.get('fecha', '____/____/______')}.",
            clausula_titulo_style,
        )
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
        response = HttpResponse(buffer, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="contrato_servicios_anticretico_inmobiliarios_{data.get("cliente_nombre","cliente")}.pdf"'
        )
        return response


class ContratoAlquilerView(APIView):
    """
    CU27 - Generación y registro de contratos de alquiler.
    Entre el propietario (arrendador) y el inquilino (arrendatario).
    """

    def post(self, request):
        from datetime import datetime

        try:
            data = request.data
            print("📄 DATA CONTRATO ALQUILER:", data)

            # 1️⃣ Validar y obtener datos base
            agente = Usuario.objects.get(id=data.get("agente_id"))
            inmueble = Inmueble.objects.get(id=data.get("inmueble_id"))

            # 2️⃣ Obtener propietario o usar fallback
            if inmueble.cliente:
                arrendador = inmueble.cliente
                print(f"🏠 Propietario del inmueble: {arrendador.nombre}")
            else:
                arrendador = agente  # fallback temporal
                print(
                    "⚠️ Inmueble sin propietario, usando AGENTE como arrendador temporal."
                )

            # 2️⃣ Manejo seguro de la fecha del contrato
            fecha_str = data.get("fecha") or data.get("fecha_inicio")
            fecha_contrato = None
            if fecha_str:
                try:
                    fecha_contrato = datetime.strptime(fecha_str, "%Y-%m-%d").date()
                except ValueError:
                    print("⚠️ Fecha inválida, usando fecha actual")
                    fecha_contrato = datetime.now().date()
            else:
                fecha_contrato = datetime.now().date()
            print("🗓️ Fecha contrato usada:", fecha_contrato)

            # 3️⃣ Crear contrato en BD
            creador = request.user if request.user.is_authenticated else None

            contrato = Contrato.objects.create(
                agente=agente,
                inmueble=inmueble,
                creado_por=creador,
                tipo_contrato="alquiler",
                ciudad=data.get("ciudad", inmueble.ciudad or ""),
                fecha_contrato=fecha_contrato,
                parte_contratante_nombre=arrendador.nombre,
                parte_contratante_ci=arrendador.ci or "",
                parte_contratante_domicilio=data.get("arrendador_domicilio", ""),
                parte_contratada_nombre=data.get("arrendatario_nombre", ""),
                parte_contratada_ci=data.get("arrendatario_ci", ""),
                parte_contratada_domicilio=data.get("arrendatario_domicilio", ""),
                monto=data.get("monto_alquiler", 0),
                vigencia_meses=data.get("vigencia_meses", 0),
                detalles_adicionales={
                    "monto_garantia": data.get("monto_garantia", ""),
                    "fecha_inicio": data.get("fecha_inicio", ""),
                    "fecha_fin": data.get("fecha_fin", ""),
                    "metodo_pago": data.get("metodo_pago", "mensual"),
                },
            )

            # 4️⃣ Actualizar anuncio del inmueble (si existe)
            anuncio = getattr(inmueble, "anuncio", None)
            if anuncio:
                anuncio.estado = "alquilado"
                anuncio.is_active = False
                anuncio.save()
                print(f"✅ Anuncio {anuncio.id} marcado como ALQUILADO")

            # 🧾 Registrar acción (bitácora opcional)
            try:
                registrar_accion(
                    usuario=request.user,
                    accion=f"Generó contrato de alquiler (ID {contrato.id}) para el inmueble ID {inmueble.id}.",
                    ip=request.META.get("REMOTE_ADDR"),
                )
            except Exception as e:
                print(f"⚠️ No se registró en bitácora: {e}")

            # 5️⃣ Generar PDF
            plantilla_path = os.path.join(
                settings.BASE_DIR, "usuario/contratoPDF/contrato_alquiler.txt"
            )
            print("📂 Cargando plantilla desde:", plantilla_path)

            with open(plantilla_path, "r", encoding="utf-8") as f:
                contrato_texto = f.read().format(
                    **{
                        "ciudad": data.get("ciudad", "________________"),
                        "fecha": fecha_contrato.strftime("%d/%m/%Y"),
                        "arrendador_nombre": arrendador.nombre,
                        "arrendador_ci": arrendador.ci or "_________",
                        "arrendador_domicilio": data.get(
                            "arrendador_domicilio", "_________"
                        ),
                        "arrendatario_nombre": data.get(
                            "arrendatario_nombre", "_________"
                        ),
                        "arrendatario_ci": data.get("arrendatario_ci", "_________"),
                        "arrendatario_domicilio": data.get(
                            "arrendatario_domicilio", "_________"
                        ),
                        "inmueble_direccion": inmueble.direccion or "_________",
                        "inmueble_zona": inmueble.zona or "_________",
                        "inmueble_superficie": inmueble.superficie or "0",
                        "monto_alquiler": data.get("monto_alquiler", "0"),
                        "monto_garantia": data.get("monto_garantia", "0"),
                        "vigencia_meses": data.get("vigencia_meses", "0"),
                        "fecha_inicio": data.get("fecha_inicio", "____/____/______"),
                        "fecha_fin": data.get("fecha_fin", "____/____/______"),
                        "agente_nombre": agente.nombre,
                    }
                )

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=LETTER,
                rightMargin=40,
                leftMargin=40,
                topMargin=50,
                bottomMargin=40,
            )

            styles = getSampleStyleSheet()

            style_normal = ParagraphStyle(
                "Normal", fontSize=11, leading=18, alignment=TA_JUSTIFY
            )

            style_clausula = ParagraphStyle(
                "Clausula",
                fontSize=11,
                leading=18,
                alignment=TA_JUSTIFY,
                spaceBefore=10,
                spaceAfter=5,
            )

            style_titulo = ParagraphStyle(
                "Titulo", fontSize=14, alignment=TA_CENTER, spaceAfter=15, leading=20
            )

            story = []
            story.append(Paragraph("<b>CONTRATO DE ALQUILER</b>", style_titulo))
            story.append(Spacer(1, 10))

            for bloque in contrato_texto.split("\n\n"):
                lineas = bloque.strip().split("\n")
                if not lineas or lineas == [""]:
                    story.append(Spacer(1, 8))
                    continue

                if (
                    lineas[0]
                    .strip()
                    .startswith(
                        (
                            "PRIMERA",
                            "SEGUNDA",
                            "TERCERA",
                            "CUARTA",
                            "QUINTA",
                            "SEXTA",
                            "SÉPTIMA",
                            "OCTAVA",
                            "NOVENA",
                            "DÉCIMA",
                        )
                    )
                ):
                    story.append(Paragraph(f"<b>{lineas[0]}</b>", style_clausula))
                    for linea in lineas[1:]:
                        story.append(Paragraph(linea, style_normal))
                else:
                    story.append(Paragraph("<br/>".join(lineas), style_normal))

                story.append(Spacer(1, 12))

            doc.build(story)
            buffer.seek(0)

            # 6️⃣ Guardar PDF
            pdf_filename = f"contrato_alquiler_{contrato.id}.pdf"
            pdf_path = os.path.join(settings.MEDIA_ROOT, "contratos", pdf_filename)
            os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
            with open(pdf_path, "wb") as f:
                f.write(buffer.getbuffer())

            contrato.archivo_pdf = f"contratos/{pdf_filename}"
            contrato.save()

            # 7️⃣ Respuesta final
            return Response(
                {
                    "status": 1,
                    "error": 0,
                    "message": "Contrato de alquiler generado y registrado correctamente.",
                    "values": {
                        "contrato_id": contrato.id,
                        "inmueble_id": inmueble.id,
                        "pdf_url": f"/contratos/{pdf_filename}",
                        "anuncio_actualizado": bool(anuncio),
                    },
                }
            )

        except Usuario.DoesNotExist:
            return Response(
                {
                    "status": 0,
                    "error": 1,
                    "message": "Agente no encontrado.",
                    "values": {},
                },
                status=404,
            )

        except Inmueble.DoesNotExist:
            return Response(
                {
                    "status": 0,
                    "error": 1,
                    "message": "Inmueble no encontrado.",
                    "values": {},
                },
                status=404,
            )

        except Exception as e:
            import traceback

            print("❌ Error en ContratoAlquilerView:", e)
            print(traceback.format_exc())
            return Response(
                {
                    "status": 0,
                    "error": 1,
                    "message": f"Error al generar contrato de alquiler: {str(e)}",
                    "values": {},
                },
                status=500,
            )


class ContratoViewPdf(APIView):
    """
    Permite visualizar o descargar el contrato PDF por ID de contrato.
    Ejemplo:
        GET /contrato/ver/1?descargar=true
    """

    def get(self, request, contrato_id):
        try:
            contrato = Contrato.objects.get(id=contrato_id)
            if not contrato.archivo_pdf:
                return Response(
                    {
                        "status": 0,
                        "error": 1,
                        "message": "El contrato no tiene archivo PDF asociado.",
                        "values": {},
                    },
                    status=404,
                )

            pdf_path = os.path.join(settings.MEDIA_ROOT, contrato.archivo_pdf.name)
            if not os.path.exists(pdf_path):
                return Response(
                    {
                        "status": 0,
                        "error": 1,
                        "message": "El archivo PDF no se encuentra en el servidor.",
                        "values": {},
                    },
                    status=404,
                )

            # 📦 Si viene ?descargar=true, forzamos descarga
            descargar = request.GET.get("descargar", "false").lower() == "true"
            response = FileResponse(
                open(pdf_path, "rb"), content_type="application/pdf"
            )

            if descargar:
                response["Content-Disposition"] = (
                    f'attachment; filename="{os.path.basename(pdf_path)}"'
                )

            return response

        except Contrato.DoesNotExist:
            return Response(
                {
                    "status": 0,
                    "error": 1,
                    "message": "Contrato no encontrado.",
                    "values": {},
                },
                status=404,
            )
        except Exception as e:
            return Response(
                {
                    "status": 0,
                    "error": 1,
                    "message": f"Error al obtener contrato PDF: {str(e)}",
                    "values": {},
                },
                status=500,
            )


@api_view(["GET"])
def listar_contratos(request):
    """
    Lista todos los contratos registrados en el sistema (con información del agente, cliente e inmueble).
    Puedes filtrar por tipo o estado:
        ?tipo=alquiler|venta|anticretico|servicios
        ?estado=activo|finalizado|cancelado|pendiente
    """
    try:
        tipo = request.GET.get("tipo")
        estado = request.GET.get("estado")

        # 🔍 Base queryset
        contratos = Contrato.objects.select_related("agente", "inmueble")

        # Aplicar filtros opcionales
        if tipo:
            contratos = contratos.filter(tipo_contrato=tipo)
        if estado:
            contratos = contratos.filter(estado=estado)

        data = []
        for c in contratos.order_by("-fecha_contrato"):
            data.append(
                {
                    "id": c.id,
                    "tipo_contrato": c.get_tipo_contrato_display(),
                    "estado": c.estado,
                    "ciudad": c.ciudad,
                    "fecha_contrato": c.fecha_contrato,
                    "fecha_inicio": c.fecha_inicio,
                    "fecha_fin": c.fecha_fin,
                    "vigencia_meses": c.vigencia_meses,
                    "monto": float(c.monto or 0),
                    "comision_porcentaje": float(c.comision_porcentaje or 0),
                    "comision_monto": float(c.comision_monto or 0),
                    "inmueble": {
                        "id": c.inmueble.id if c.inmueble else None,
                        "titulo": c.inmueble.titulo if c.inmueble else None,
                        "direccion": c.inmueble.direccion if c.inmueble else None,
                        "zona": c.inmueble.zona if c.inmueble else None,
                        "ciudad": c.inmueble.ciudad if c.inmueble else None,
                    },
                    "agente": {
                        "id": c.agente.id if c.agente else None,
                        "nombre": c.agente.nombre if c.agente else None,
                    },
                    "propietario": {
                        "nombre": c.parte_contratante_nombre,
                        "ci": c.parte_contratante_ci,
                    },
                    "inquilino": {
                        "nombre": c.parte_contratada_nombre,
                        "ci": c.parte_contratada_ci,
                    },
                    "pdf_url": f"/media/{c.archivo_pdf}" if c.archivo_pdf else None,
                    "fecha_creacion": c.fecha_creacion,
                }
            )

        return Response(
            {
                "status": 1,
                "error": 0,
                "message": "LISTADO DE CONTRATOS REGISTRADOS",
                "values": {"contratos": data},
            }
        )

    except Exception as e:
        return Response(
            {
                "status": 0,
                "error": 1,
                "message": f"Error al listar contratos: {str(e)}",
                "values": {},
            },
            status=500,
        )


@api_view(["GET"])
def detalle_contrato_pdf(request, contrato_id):
    """
    Retorna la información completa del contrato especificado.
    Si se agrega '?descargar=true' en la URL, devuelve directamente el archivo PDF.
    Ejemplo:
        GET /contrato/detalle/1               -> devuelve JSON con todos los datos
        GET /contrato/detalle/1?descargar=true -> descarga el PDF directamente
    """
    try:
        contrato = Contrato.objects.select_related("agente", "inmueble").get(
            id=contrato_id
        )

        # 📦 Si se pide descarga directa del PDF
        if request.GET.get("descargar", "false").lower() == "true":
            if not contrato.archivo_pdf:
                return Response(
                    {
                        "status": 0,
                        "error": 1,
                        "message": "El contrato no tiene archivo PDF asociado.",
                        "values": {},
                    },
                    status=404,
                )

            pdf_path = os.path.join(settings.MEDIA_ROOT, contrato.archivo_pdf.name)
            if not os.path.exists(pdf_path):
                return Response(
                    {
                        "status": 0,
                        "error": 1,
                        "message": "El archivo PDF no existe en el servidor.",
                        "values": {},
                    },
                    status=404,
                )

            # 📥 Responder como archivo descargable
            response = FileResponse(
                open(pdf_path, "rb"), content_type="application/pdf"
            )
            response["Content-Disposition"] = (
                f'attachment; filename="{os.path.basename(pdf_path)}"'
            )
            return response

        # 📄 Si no se pide descarga → devolver datos JSON completos
        data = {
            "id": contrato.id,
            "tipo_contrato": contrato.get_tipo_contrato_display(),
            "estado": contrato.estado,
            "ciudad": contrato.ciudad,
            "fecha_contrato": contrato.fecha_contrato,
            "fecha_inicio": contrato.fecha_inicio,
            "fecha_fin": contrato.fecha_fin,
            "vigencia_meses": contrato.vigencia_meses,
            "monto": float(contrato.monto or 0),
            "comision_porcentaje": float(contrato.comision_porcentaje or 0),
            "comision_monto": float(contrato.comision_monto or 0),
            "detalles_adicionales": contrato.detalles_adicionales,
            "inmueble": {
                "id": contrato.inmueble.id if contrato.inmueble else None,
                "titulo": contrato.inmueble.titulo if contrato.inmueble else None,
                "direccion": contrato.inmueble.direccion if contrato.inmueble else None,
                "zona": contrato.inmueble.zona if contrato.inmueble else None,
                "ciudad": contrato.inmueble.ciudad if contrato.inmueble else None,
                "tipo_operacion": (
                    contrato.inmueble.tipo_operacion if contrato.inmueble else None
                ),
                "superficie": (
                    float(contrato.inmueble.superficie or 0)
                    if contrato.inmueble
                    else None
                ),
                "precio": (
                    float(contrato.inmueble.precio or 0) if contrato.inmueble else None
                ),
            },
            "agente": {
                "id": contrato.agente.id if contrato.agente else None,
                "nombre": contrato.agente.nombre if contrato.agente else None,
                "email": contrato.agente.email if contrato.agente else None,
            },
            "propietario": {
                "nombre": contrato.parte_contratante_nombre,
                "ci": contrato.parte_contratante_ci,
                "domicilio": contrato.parte_contratante_domicilio,
            },
            "inquilino": {
                "nombre": contrato.parte_contratada_nombre,
                "ci": contrato.parte_contratada_ci,
                "domicilio": contrato.parte_contratada_domicilio,
            },
            "pdf_url": (
                f"/media/{contrato.archivo_pdf}" if contrato.archivo_pdf else None
            ),
            "fecha_creacion": contrato.fecha_creacion,
            "fecha_actualizacion": contrato.fecha_actualizacion,
        }

        return Response(
            {
                "status": 1,
                "error": 0,
                "message": f"DETALLE DEL CONTRATO ID {contrato_id}",
                "values": {"contrato": data},
            }
        )

    except Contrato.DoesNotExist:
        return Response(
            {
                "status": 0,
                "error": 1,
                "message": "Contrato no encontrado.",
                "values": {},
            },
            status=404,
        )
    except Exception as e:
        return Response(
            {
                "status": 0,
                "error": 1,
                "message": f"Error al obtener detalle del contrato: {str(e)}",
                "values": {},
            },
            status=500,
        )
