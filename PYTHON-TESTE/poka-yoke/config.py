# config.py
import os

URL_CAMERA = "http://10.10.0.26:8080/video"
MODELO_YOLO = 'yolov8n.pt'

# Pasta para salvar as fotos do Poka-Yoke
DIR_FOTOS = "fotos_producao"
os.makedirs(DIR_FOTOS, exist_ok=True)

# Configurações de Desempenho
RESOLUCAO = (1280, 720) # Aumentando qualidade para a demo (HD)
TEMPO_COOLDOWN = 3.0    # Ajuste de tempo de cooldown para leitura do mesmo código
YOLO_SKIP_FRAMES = 5    # Roda a YOLO a cada 5 frames para garantir visão contínua e boa performance

# Configurações de Interface - Design Industrial Moderno
BG_COLOR = "#0B0F19"        # Fundo principal escuro azulado
PANEL_COLOR = "#151A27"     # Cor dos painéis laterais e blocos
ACCENT_COLOR = "#00B4D8"    # Azul vibrante/Ciano para detalhes
TEXT_COLOR = "#E2E8F0"      # Texto claro
SUCCESS_COLOR = "#10B981"   # Verde para sucesso/operação
WARNING_COLOR = "#F59E0B"   # Amarelo/Laranja para alertas
DANGER_COLOR = "#EF4444"    # Vermelho para parado/erro

FONT_TITLE = ("Segoe UI", 14, "bold")
FONT_SUBTITLE = ("Segoe UI", 11, "bold")
FONT_DATA = ("Segoe UI", 12, "normal")
FONT_MONO = ("Consolas", 10, "normal")