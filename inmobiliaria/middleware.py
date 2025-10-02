from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
import traceback

class JsonErrorMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        """
        Captura cualquier excepción no manejada y responde en JSON.
        """
        response_data = {
            "error": str(exception),
        }

        # Si estamos en DEBUG, también devolver el traceback
        if settings.DEBUG:
            response_data["traceback"] = traceback.format_exc()

        return JsonResponse(response_data, status=500)

    def process_response(self, request, response):
        """
        Si la respuesta es 404/403/400 y no es JSON, devolver JSON estándar.
        """
        if response.status_code == 404:
            return JsonResponse({"error": "La URL solicitada no existe"}, status=404)

        if response.status_code == 403:
            return JsonResponse({"error": "Acceso denegado"}, status=403)

        if response.status_code == 400:
            return JsonResponse({"error": "Solicitud inválida"}, status=400)

        return response
