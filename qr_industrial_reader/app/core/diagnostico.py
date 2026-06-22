# app/core/diagnostico.py
import cv2
import os
import time
import logging
from app.core.config import Config

# Otimizacao extrema para fluxos de rede no OpenCV
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "timeout;3000|rtsp_transport;tcp|fflags;nobuffer+discardcorrupt|flags;low_delay|analyzeduration;0"


def testar_camera(nome_camera="NF"):
    """
    Testa a câmera especificada.
    :param nome_camera: 'NF' para testar a CAMERA_NF ou 'PECAS' para CAMERA_PECAS
    """
    logging.info("=" * 50)
    logging.info(
        f"INICIANDO DIAGNOSTICO DE HARDWARE/REDE - ALVO: {nome_camera}")
    logging.info("=" * 50)

    # Seleciona a fonte baseada no argumento
    if nome_camera.upper() == "NF" and Config.CAMERA_NF:
        source = Config.CAMERA_NF[0]
    elif nome_camera.upper() == "PECAS" and Config.CAMERA_PECAS:
        source = Config.CAMERA_PECAS[0]
    else:
        logging.error(
            f"Camera '{nome_camera}' não configurada no arquivo config.py (ou .env)!")
        return

    logging.info(f"Testando a fonte primaria: {source}")

    backend = cv2.CAP_ANY
    if isinstance(source, str) and ("http" in source or "rtsp" in source):
        backend = cv2.CAP_FFMPEG
        logging.info("Driver selecionado: FFMPEG (Conexão de Rede RTSP/HTTP)")
    elif isinstance(source, int) or (isinstance(source, str) and source.isdigit()):
        source = int(source)  # Garante que seja inteiro para webcams
        logging.info("Driver selecionado: AUTO (Câmera Local/USB)")

    logging.info("Estabelecendo conexão... (Aguarde o Handshake)")

    cap = cv2.VideoCapture(source, backend)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        logging.error(
            f"Falha CRÍTICA ao abrir o fluxo de vídeo da fonte: {source}")
        cap.release()
        return

    logging.info("Sinal de vídeo recebido com sucesso!")
    logging.info("Uma janela será aberta. Pressione 'ESC' nela para sair.")

    frames_lidos = 0
    falhas_consecutivas = 0

    try:
        while True:
            # BLINDAGEM: Evita crash com pacotes corrompidos
            try:
                ret, frame = cap.read()
            except Exception as e:
                logging.warning(
                    f"Falha no pacote de vídeo (C++ Exception): {e}")
                ret, frame = False, None

            if not ret or frame is None:
                falhas_consecutivas += 1
                logging.warning(
                    f"Queda de frame detectada ({falhas_consecutivas}/10)")
                time.sleep(0.5)
                if falhas_consecutivas >= 10:
                    logging.error(
                        "Perda total de sinal (Timeout). Encerrando o diagnóstico.")
                    break
                continue

            falhas_consecutivas = 0
            frames_lidos += 1
            h, w, _ = frame.shape

            if frames_lidos % 30 == 0:
                logging.info(
                    f"Sinal estável | Resolução nativa recebida: {w}x{h}")

            # Mantém a proporção (Aspect Ratio) redimensionando pela largura
            # desejada (ex: 800)
            escala = 800 / w
            nova_largura = 800
            nova_altura = int(h * escala)
            frame_resized = cv2.resize(frame, (nova_largura, nova_altura))

            # HUD (Heads-Up Display) de Diagnóstico
            cv2.putText(frame_resized, f"MODO DIAGNOSTICO: {nome_camera} - Pressione ESC", (15, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.putText(frame_resized, f"Resolucao Real: {w}x{h}", (15, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            cv2.imshow("Teste de Leitura de Camera", frame_resized)

            if cv2.waitKey(1) & 0xFF == 27:
                logging.info(
                    "Diagnóstico encerrado manualmente pelo operador (ESC).")
                break

    finally:
        # Garante que os recursos serão liberados até se alguém apertar Ctrl+C
        # no terminal
        cap.release()
        cv2.destroyAllWindows()
        logging.info("Recursos de vídeo liberados com sucesso.")


if __name__ == "__main__":
    # Configuração básica de log para exibir as mensagens ao rodar isoladamente
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s')

    # Você pode testar facilmente ambas as câmeras assim:
    testar_camera("NF")
    # testar_camera("PECAS")
