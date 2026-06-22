# app/core/config.py
import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Define o caminho raiz do projeto para evitar erros de "File Not Found"
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))


def _parse_cameras(env_string, default_list):
    if not env_string:
        return default_list

    sources = []
    for item in env_string.split(','):
        item = item.strip()
        # Se for apenas um número (ex: 0), converte para inteiro (Webcam USB)
        if item.isdigit():
            sources.append(int(item))
        elif item:
            sources.append(item)
    return sources


class Config:
    # ---------------------------------------------------------
    # CÂMERAS E VÍDEO
    # ---------------------------------------------------------
    CAMERA_NF = _parse_cameras(os.getenv("CAMERA_NF"), default_list=[0])
    CAMERA_PECAS = _parse_cameras(os.getenv("CAMERA_PECAS"), default_list=[1])

    TARGET_FPS = 30
    FRAME_WIDTH = 1280
    FRAME_HEIGHT = 720
    DETECT_EVERY = 3

    # ---------------------------------------------------------
    # INTELIGÊNCIA ARTIFICIAL (YOLO)
    # ---------------------------------------------------------
    USE_IA = os.getenv("USE_IA", "False").lower() in ("true", "1", "yes")

    try:
        YOLO_CONFIDENCE = float(
            os.getenv(
                "YOLO_CONFIDENCE",
                "0.60").replace(
                ',',
                '.'))
    except ValueError:
        YOLO_CONFIDENCE = 0.60
        logging.warning(
            "Erro no formato do YOLO_CONFIDENCE no .env. Usando 0.60 padrão.")

    # Caminho absoluto para garantir que sempre acha o arquivo ONNX
    YOLO_MODEL = os.getenv(
        "YOLO_MODEL",
        os.path.join(
            BASE_DIR,
            "models",
            "yolov8n.onnx"))

    # ---------------------------------------------------------
    # COMUNICAÇÃO MODBUS TCP (CLP)
    # ---------------------------------------------------------
    PLC_IP = os.getenv("PLC_IP", "172.20.10.157")

    # Tratamento de erro seguro para as portas e coils
    try:
        PLC_PORT = int(os.getenv("PLC_PORT", 502))
        COIL_ESTEIRA = int(os.getenv("COIL_ESTEIRA", 0))
        COIL_ALARME = int(os.getenv("COIL_ALARME", 1))
        COIL_SUCESSO = int(os.getenv("COIL_SUCESSO", 2))
    except ValueError:
        logging.error(
            "Erro na leitura das portas ou coils no .env. Usando valores default.")
        PLC_PORT, COIL_ESTEIRA, COIL_ALARME, COIL_SUCESSO = 502, 0, 1, 2

    MAX_RECONNECT = 5
    TIMEOUT = 3
