import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from datetime import datetime

# Cargar variables desde .env
load_dotenv()

LOG_FILE_PATH = "secure_logs/audit.log"

def get_fernet():
    key = os.getenv("LOG_DEV_KEY")
    if not key:
        raise ValueError("❌ No se encontró la variable LOG_DEV_KEY en el entorno.")
    return Fernet(key.encode())

def registrar_accion(usuario, accion, ip):
    fernet = get_fernet()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log_line = f"[{ahora}] Usuario ID: {usuario.id} | Nombre de Usuario: {usuario.username} | Grupo del usuario: {usuario.grupo.nombre}  | IP: {ip} | Acción: {accion}\n"
    encrypted_log = fernet.encrypt(log_line.encode())

    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
    with open(LOG_FILE_PATH, "ab") as f:
        f.write(encrypted_log + b"\n")

def leer_logs(llave_ingresada):
    print(llave_ingresada)
    """Solo el desarrollador con la llave correcta puede leer"""
    key = os.getenv("LOG_DEV_KEY")
    print(key)
    if llave_ingresada != key:
        raise PermissionError("❌ Llave incorrecta. No tienes acceso a la bitácora.")

    fernet = Fernet(key.encode())
    with open(LOG_FILE_PATH, "rb") as f:
        lineas = f.readlines()

    logs_descifrados = []
    for linea in lineas:
        try:
            texto = fernet.decrypt(linea.strip()).decode()
            logs_descifrados.append(texto)
        except Exception:
            logs_descifrados.append("[LÍNEA CORRUPTA O NO DESCIFRABLE]")

    return logs_descifrados