# camera.py
import cv2
import threading
import queue
import time
import config

class CameraStream(threading.Thread):
    def __init__(self, url, capture_queue):
        super().__init__(daemon=True)
        self.url = url
        self.capture_queue = capture_queue
        self.running = False

    def _open_camera(self):
        cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    def run(self):
        self.running = True
        cap = self._open_camera()
        
        while self.running:
            if not cap.isOpened():
                time.sleep(1) # Tenta reconectar a cada 1 segundo se cair
                cap = self._open_camera()
                continue

            ret, frame = cap.read()
            if not ret:
                cap.release()
                time.sleep(1)
                continue
            
            # REDUÇÃO IMEDIATA DE CARGA: Redimensiona antes de jogar na fila
            frame = cv2.resize(frame, config.RESOLUCAO)
            
            # Drop de frames velhos para garantir o TEMPO REAL
            if self.capture_queue.full():
                try:
                    self.capture_queue.get_nowait()
                except queue.Empty:
                    pass
            
            self.capture_queue.put(frame)
            
        cap.release()

    def stop(self):
        self.running = False