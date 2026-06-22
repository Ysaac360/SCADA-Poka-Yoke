# app/services/scan_service.py
import threading
import logging
import cv2
import time
import queue  # <-- IMPORTANTE: Adicionar a biblioteca queue nativa
import gc
from ultralytics import YOLO

from app.camera.ip_camera import IPCamera
from app.qr.qr_decoder import QRDecoder
from app.qr.qr_drawer import QRDrawer
from app.qr.qr_processor import QRProcessor
from app.core.config import Config


class ScanService:
    def __init__(self, sources, nome):
        self.nome = nome
        self.camera = IPCamera(sources, nome)
        self.decoder = QRDecoder()
        self.drawer = QRDrawer()
        self.processor = QRProcessor()

        self.model = None
        self.is_yolo_cam = "PECAS" in self.nome.upper()
        self.is_qr_cam = True

        self.limite_codigos = 5 if self.is_yolo_cam else 1
        self.ia_ativa = False

        if getattr(Config, 'USE_IA', False):
            try:
                self.model = YOLO(Config.YOLO_MODEL, task='detect')
                logging.info(f"[{self.nome}] Modelo IA carregado com sucesso.")
            except Exception as e:
                self.model = None
                logging.error(f"[{self.nome}] Erro ao carregar IA: {e}")

        self.running = False
        self.thread = None
        self.yolo_thread = None
        self.yolo_lock = threading.Lock()
        self.current_frame_for_yolo = None
        self.latest_yolo_results = []

        # Thread de Decodificação Assíncrona (Para não travar o vídeo)
        self.decode_thread = None
        self.decode_lock = threading.Lock()
        self.current_frame_for_decode = None
        self.latest_qrs_to_draw = []
        self.latest_eventos = []

        # ========================================================
        # ARQUITETURA ANTI-LAG COM QUEUES (Filas de tamanho fixo)
        # ========================================================
        # maxsize=2 significa que guardamos no máximo o frame de "agora" e o "anterior".
        # Se a UI não buscar a tempo, jogamos o velho fora para nunca ter lag.
        self.ui_queue = queue.Queue(maxsize=2)

        # Fila dedicada para eventos de peças (para o KitManager e DB)
        self.event_queue = queue.Queue()

    def start(self):
        if not self.running:
            self.running = True
            self.camera.start()

            # Thread que cuida de entregar os frames pra interface
            self.thread = threading.Thread(
                target=self._process_loop, daemon=True)
            self.thread.start()

            # Thread que cuida apenas do processamento pesado da YOLO
            if self.model:
                self.yolo_thread = threading.Thread(
                    target=self._yolo_loop, daemon=True)
                self.yolo_thread.start()

            # Thread que cuida de ZBar e Matrix pesado sem travar vídeo
            if self.is_qr_cam:
                self.decode_thread = threading.Thread(
                    target=self._decode_loop, daemon=True)
                self.decode_thread.start()

    def _decode_loop(self):
        while self.running:
            frame_to_decode = None
            with self.decode_lock:
                if self.current_frame_for_decode is not None:
                    frame_to_decode = self.current_frame_for_decode.copy()
                    self.current_frame_for_decode = None

            if frame_to_decode is None:
                time.sleep(0.01)
                continue

            qrs_to_draw_local = []
            eventos_local = []

            # Pega as caixas da YOLO direto do cache para cruzar com o QR
            qr_boxes = []
            if self.model:
                with self.yolo_lock:
                    res = self.latest_yolo_results
                for r in res:
                    for c in r.boxes:
                        cls_nome = self.model.names[int(c.cls[0])].upper()
                        if "QR" in cls_nome or "MATRIX" in cls_nome:
                            qr_boxes.append(tuple(map(int, c.xyxy[0])))

            qrs = self.decoder.decode(
                frame_to_decode,
                max_codes=self.limite_codigos,
                boxes=qr_boxes)
            for qr in qrs:
                if "bbox" in qr and qr["bbox"]:
                    res = self.processor.process(qr["data"])
                    if res:
                        eventos_local.append(res)
                    qrs_to_draw_local.append(
                        {"qr": qr, "is_new": res["novo"] if res else False})

            with self.decode_lock:
                self.latest_eventos.extend(eventos_local)
                self.latest_qrs_to_draw = qrs_to_draw_local

            time.sleep(0.01)

    def _yolo_loop(self):
        while self.running:
            frame_to_process = None
            with self.yolo_lock:
                if self.current_frame_for_yolo is not None:
                    frame_to_process = self.current_frame_for_yolo.copy()
                    self.current_frame_for_yolo = None  # Limpa para pegar o próximo

            if frame_to_process is None or not (
                    self.ia_ativa or self.is_qr_cam):
                time.sleep(0.02)
                continue

            try:
                # OTIMIZAÇÃO MAXIMA: Inferência sem bloquear o vídeo
                resultados = self.model.predict(
                    source=frame_to_process,
                    imgsz=640,
                    conf=Config.YOLO_CONFIDENCE,
                    iou=0.45,
                    max_det=15,
                    device='cpu',
                    verbose=False
                )
                with self.yolo_lock:
                    self.latest_yolo_results = resultados
            except Exception as e:
                logging.error(f"[{self.nome}] Erro na YOLO: {e}")

            time.sleep(0.01)

    def _process_loop(self):
        # Cache visual para manter o overlay vivo entre as detecções da IA
        last_qr_boxes = []
        last_ia_boxes_to_draw = []
        last_frame_time = 0
        while self.running:
            frame_data = self.camera.read()
            # Tratamento de segurança caso o unpack falhe em transições de
            # sistema
            if isinstance(frame_data, tuple):
                frame, frame_time = frame_data
            else:
                frame, frame_time = frame_data, 0

            # Bloqueador Anti-Fantasma: Impede re-processar e re-desenhar o
            # mesmo Frame repetidas vezes.
            if frame is None or frame_time == last_frame_time:
                time.sleep(0.01)
                continue

            last_frame_time = frame_time

            eventos_local = []
            qrs_to_draw = []

            # Passa o frame atual para a YOLO trabalhar no background
            if self.model:
                with self.yolo_lock:
                    self.current_frame_for_yolo = frame
                    resultados = self.latest_yolo_results
                    self.latest_yolo_results = []  # Consome os resultados
            else:
                resultados = []

            # 1. ATUALIZAÇÃO DA IA (YOLO) ASSÍNCRONA
            if resultados:
                qr_boxes = []
                ia_boxes_to_draw = []

                for r in resultados:
                    for c in r.boxes:
                        x1, y1, x2, y2 = map(int, c.xyxy[0])
                        conf = float(c.conf[0])
                        cls_nome = self.model.names[int(c.cls[0])].upper()

                        if "QR" in cls_nome or "MATRIX" in cls_nome:
                            qr_boxes.append((x1, y1, x2, y2))
                        elif self.is_yolo_cam and self.ia_ativa:
                            codigo_ia = f"IA_{cls_nome}"
                            res_ia = self.processor.process(codigo_ia)
                            if res_ia:
                                eventos_local.append(res_ia)

                            color_box = (255, 165, 0)
                            ia_boxes_to_draw.append({
                                "box": (x1, y1, x2, y2),
                                "color": color_box,
                                "label": f"{cls_nome} {int(conf * 100)}%"
                            })

                last_qr_boxes = qr_boxes
                last_ia_boxes_to_draw = ia_boxes_to_draw

            # Usa os dados do cache visual se a IA ainda estiver processando o
            # último frame
            qr_boxes = last_qr_boxes if self.model else None
            ia_boxes_to_draw = last_ia_boxes_to_draw

            # 2. ALIMENTA E RECUPERA DA THREAD DE DECODIFICAÇÃO (Assíncrono!)
            if self.is_qr_cam:
                with self.decode_lock:
                    self.current_frame_for_decode = frame  # Manda o frame atual
                    # Puxa as caixinhas já prontas (mesmo que com atraso de ms)
                    qrs_to_draw = self.latest_qrs_to_draw

                    if self.latest_eventos:
                        eventos_local.extend(self.latest_eventos)
                        self.latest_eventos = []  # Limpa eventos já despachados

            # ========================================================
            # RENDERIZAÇÃO NO BACKGROUND (Zero Lag na UI)
            # ========================================================
            frame_ui = frame.copy()

            for item in ia_boxes_to_draw:
                x1, y1, x2, y2 = item["box"]
                color = item["color"]
                cv2.rectangle(
                    frame_ui, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)
                cv2.putText(
                    frame_ui, item["label"], (x1, max(
                        15, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1, cv2.LINE_AA)

            for item in qrs_to_draw:
                self.drawer.draw(frame_ui, item["qr"], is_new=item["is_new"])

            # Converte e Redimensiona aqui, fora da UI
            frame_ui_resized = cv2.resize(frame_ui, (640, 480))
            frame_ui_rgb = cv2.cvtColor(frame_ui_resized, cv2.COLOR_BGR2RGB)

            # ========================================================
            # DESPACHO PARA AS FILAS
            # ========================================================
            for evt in eventos_local:
                self.event_queue.put(evt)

            try:
                if self.ui_queue.full():
                    try:
                        self.ui_queue.get_nowait()
                        del lixo
                    except queue.Empty:
                        pass
                self.ui_queue.put_nowait(frame_ui_rgb)
            except queue.Full:
                pass

            # ========================================================
            # GARBAGE COLLECTION E CACHE FLUSH EXTREMO
            # ========================================================
            del frame
            del frame_ui
            del frame_ui_resized

            # Chama o limpador de lixo de geração 0 do Python a cada ciclo
            # para evitar que matrizes pesadas engasguem a memória a longo
            # prazo.
            gc.collect(0)

            time.sleep(0.01)

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
        self.camera.stop()
