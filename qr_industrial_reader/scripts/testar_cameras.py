# scripts/testar_cameras.py
from app.core.logger import setup_logger
from app.core.config import Config
import cv2
import os
import logging
import sys

# Adiciona o diretorio raiz ao path para os imports funcionarem se
# executado da pasta scripts
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            '..')))


# Inicializa o Logger
setup_logger()

# Otimizacao extrema para IP Webcams (Alinhada com a classe IPCamera)
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "timeout;3000|rtsp_transport;tcp|fflags;nobuffer+discardcorrupt|flags;low_delay|analyzeduration;0"


def testar_camera():
    logging.info("=" * 50)
    logging.info("INICIANDO DIAGNOSTICO DUPLO DE HARDWARE/REDE")
    logging.info("=" * 50)

    cameras_para_testar = []

    # Mapeia as cameras configuradas (Alinhado com a nova arquitetura)
    if Config.CAMERA_PECAS:
        cameras_para_testar.append({
            "id": "CAM 1 - PECAS (ESQUERDA)",
            "source": Config.CAMERA_PECAS[0],
            "cap": None, "falhas": 0, "frames": 0
        })

    if Config.CAMERA_NF:
        cameras_para_testar.append({
            "id": "CAM 2 - MASTER (DIREITA)",
            "source": Config.CAMERA_NF[0],
            "cap": None, "falhas": 0, "frames": 0
        })

    if not cameras_para_testar:
        logging.error(
            "Nenhuma camera configurada no arquivo config.py (ou .env)!")
        return

    # Inicializa as conexões
    for cam in cameras_para_testar:
        logging.info(
            f"Tentando conectar {
                cam['id']} na fonte: {
                cam['source']}")
        backend = cv2.CAP_FFMPEG if isinstance(
            cam['source'], str) else cv2.CAP_ANY

        cap = cv2.VideoCapture(cam['source'], backend)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if cap.isOpened():
            cam['cap'] = cap
            logging.info(f"[SUCESSO] {cam['id']} conectada!")
        else:
            logging.error(
                f"[FALHA CRITICA] Nao foi possivel abrir a {
                    cam['id']}.")

    # Filtra apenas as cameras que conseguiram conectar
    ativas = [cam for cam in cameras_para_testar if cam['cap'] is not None]

    if not ativas:
        logging.error(
            "Nenhuma camera conseguiu conectar. Encerrando diagnostico.")
        return

    logging.info("Sinais de video recebidos! Janelas serao abertas.")
    logging.info("Pressione 'ESC' com uma das janelas selecionada para sair.")

    while True:
        for cam in ativas:
            # BLINDAGEM: Evita que o script crashe com pacotes corrompidos
            try:
                ret, frame = cam['cap'].read()
            except Exception as e:
                logging.warning(f"[{cam['id']}] Falha no pacote de video: {e}")
                ret, frame = False, None

            if not ret or frame is None:
                cam['falhas'] += 1
                if cam['falhas'] % 15 == 0:
                    logging.warning(
                        f"[{cam['id']}] Queda de frames consecutiva detectada!")
                continue

            cam['falhas'] = 0
            cam['frames'] += 1

            if cam['frames'] % 30 == 0:
                h, w, _ = frame.shape
                logging.info(
                    f"[{cam['id']}] Sinal estavel | Resolucao recebida: {w}x{h}")

            # Redimensiona com altíssima qualidade (INTER_AREA) para
            # diagnóstico
            frame_resized = cv2.resize(
                frame, (640, 480), interpolation=cv2.INTER_AREA)

            # HUD Soft Amber no diagnóstico
            cv2.putText(frame_resized,
                        f"{cam['id']} - ESC p/ sair",
                        (15,
                         30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (38,
                            162,
                            255),
                        2,
                        cv2.LINE_AA)

            # Abre uma janela com o titulo igual ao ID da camera
            cv2.imshow(cam['id'], frame_resized)

        # Se apertar ESC (codigo 27), sai do loop
        if cv2.waitKey(1) & 0xFF == 27:
            logging.info("Diagnostico encerrado pelo usuario.")
            break

    # Libera os recursos do PC
    for cam in ativas:
        cam['cap'].release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    testar_camera()
