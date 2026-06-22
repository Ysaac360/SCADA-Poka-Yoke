# app/camera/ip_camera.py
import cv2
import threading
import os
import time
import logging
from app.core.config import Config

# ==============================================================================
# OTIMIZACAO DE REDE E ANTI-CRASH
# ==============================================================================


class IPCamera:
    def __init__(self, sources, nome="CAMERA"):
        self.nome = nome
        self.sources = sources
        self.current_source_index = 0
        self.cap = None
        self.running = False
        self.thread = None

        # Lock garante que a Inteligencia Artificial e o Leitor de QR leiam sempre o
        # quadro exato deste milissegundo, sem atropelar a memoria.
        self.frame_atual = None
        self.ultima_atualizacao = 0
        self.lock = threading.Lock()

        self.watchdog_thread = None

    def _get_backend(self, source):
        return cv2.CAP_FFMPEG if isinstance(source, str) else cv2.CAP_ANY

    def connect(self):
        source = self.sources[self.current_source_index]

        # Aplica a blindagem pesada do FFMPEG APENAS se for protocolo RTSP
        # Industrial (H264)
        if isinstance(source, str) and source.startswith("rtsp://"):
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay|hwaccel;auto|stimeout;3000000|max_delay;500000|timeout;3000|reorder_queue_size;0|discardcorrupt;1"
        else:
            # Para testes em bancada via IP Webcam (HTTP/MJPEG), limpa as
            # variáveis para não crashar a conexão
            if "OPENCV_FFMPEG_CAPTURE_OPTIONS" in os.environ:
                del os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"]

        self.cap = cv2.VideoCapture(source, self._get_backend(source))

        # Dupla blindagem: alem da variavel de ambiente, forca o OpenCV a
        # segurar apenas 1 frame
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # Puxando do Config para centralizar o controle de resolucao
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, Config.FRAME_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, Config.FRAME_HEIGHT)

        if not self.cap.isOpened():
            self._next_source()
            return False
        return True

    def start(self):
        if not self.running:
            self.running = True
            self.connect()

            # Inicia o laço de captura contínua
            self.thread = threading.Thread(
                target=self._capture_loop, daemon=True)
            self.thread.start()

    def _capture_loop(self):
        falhas = 0
        while self.running:
            if not self.cap or not self.cap.isOpened():
                time.sleep(1)
                self._reconnect()
                continue

            # BLINDAGEM: Captura falhas de pacote do C++/FFMPEG sem matar a
            # thread
            try:
                ret, frame = self.cap.read()
            except Exception as e:
                logging.warning(
                    f"[{self.nome}] Falha no pacote de video (C++ Exception): {e}")
                ret, frame = False, None

            if not ret or frame is None:
                falhas += 1
                if falhas >= 5:
                    self._reconnect()
                    falhas = 0
                continue

            falhas = 0

            # Atualiza sempre o frame mais recente de forma super rapida
            with self.lock:
                self.frame_atual = frame
                self.ultima_atualizacao = time.time()

    def read(self):
        # Retorna uma COPIA do frame atual e o Timestamp para filtro Anti-Ghost
        with self.lock:
            if self.frame_atual is not None:
                return self.frame_atual.copy(), self.ultima_atualizacao
            return None, 0

    def _reconnect(self):
        if self.cap:
            self.cap.release()
        time.sleep(0.5)
        self._next_source()
        self.connect()

    def _next_source(self):
        self.current_source_index = (
            self.current_source_index + 1) % len(self.sources)

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
        if self.cap:
            self.cap.release()
