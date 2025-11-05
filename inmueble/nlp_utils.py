# inmueble/nlp_utils.py

import json
from decouple import config
# Importamos genai solo aquí para que la configuración sea local
import google.generativeai as genai 

# ----------------- PROMPT PRINCIPAL -----------------
PROMPT_PLANTILLA = """
Eres un analizador de lenguaje natural experto en inmobiliarias.
Tu tarea es analizar la solicitud del usuario y extraer los parámetros relevantes
para una consulta de base de datos de inmuebles.

Reglas:
1. Siempre devuelve la salida como un objeto JSON válido.
2. Si un parámetro no se menciona, usa una cadena vacía "" o 0 para números, NO 'null'.
3. Los precios siempre deben convertirse a números enteros o flotantes, sin comas ni puntos de mil.
4. Las características son palabras clave para buscar en la descripción (ej: piscina, garaje, terraza).

Parámetros JSON (¡DEBES USAR ESTOS NOMBRES EXACTOS!):
- tipo_propiedad: (string, ej: 'Departamento', 'Casa', 'Lote')
- tipo_operacion: (string, ej: 'venta', 'alquiler')
- ciudad: (string)
- zona: (string, ej: 'norte', 'sur')
- precio_minimo: (float/integer)
- precio_maximo: (float/integer)
- dormitorios_min: (integer)
- caracteristicas_clave: (lista de strings, palabras clave)

Solicitud del usuario: "{texto_usuario}"
Devuelve SOLAMENTE el objeto JSON.
"""
# ----------------------------------------------------

def parse_natural_query(texto_usuario: str) -> dict:
    
    api_key = config('API_GEMINI', default=config('GOOGLE_API_KEY', default=''))
    if not api_key:
        print("ERROR: Clave API_GEMINI no configurada.")
        return {}
    
    # 🚨 PRUEBA DE CLAVE 🚨 (Imprimir solo los primeros caracteres)
    print(f"DIAGNÓSTICO: API Key leída (inicio): {api_key[:5]}...") 

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash') 

        prompt = PROMPT_PLANTILLA.format(texto_usuario=texto_usuario)

# ALTERNATIVA (SOLO si la anterior falla después de la actualización):
        response = model.generate_content(
            prompt
        )

        raw_text = response.text.strip()
        
        # 🚨 PRUEBA DE TEXTO CRUDO 🚨 (Muestra el texto en la consola de tu servidor)
        print(f"DIAGNÓSTICO: Texto CRUDO devuelto por Gemini (len={len(raw_text)}): '{raw_text[:50]}'") 
        
        # Limpieza defensiva del texto de respuesta (la dejamos como estaba)
        if raw_text.startswith("```json"):
            raw_text = raw_text.lstrip("```json").rstrip("```").strip()
        elif raw_text.startswith("```"):
            raw_text = raw_text.lstrip("```").rstrip("```").strip()

        # Intentar parsear el JSON limpio
        return json.loads(raw_text)

    except json.JSONDecodeError as e:
        print(f"Error JSON Decode: No se pudo parsear el JSON de Gemini. Texto crudo: '{raw_text[:50]}...'")
        return {} 

    except Exception as e:
        # Esto atrapará errores de red, permisos, o errores de modelo (como clave inválida)
        print(f"Error FATAL en Gemini API (Revisar logs o clave): {type(e).__name__}: {e}")
        return {}