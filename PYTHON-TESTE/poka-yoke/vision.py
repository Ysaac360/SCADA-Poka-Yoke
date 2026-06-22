# vision.py
import cv2
import time
import threading
import queue
import os
from datetime import datetime
import pyzbar.pyzbar as pyzbar
from ultralytics import YOLO
import numpy as np
import config

class VisionProcessor(threading.Thread):
    def __init__(self, capture_queue, result_queue, model_path):
        super().__init__(daemon=True)
        self.capture_queue = capture_queue
        self.result_queue = result_queue
        self.modelo = YOLO(model_path, task='detect')
        self.running = False
        
        self.ultimo_qr = ""
        self.tempo_ultimo_qr = 0
        
        self.frame_counter = 0
        self.last_yolo_objects = []
        self.last_yolo_boxes = []

    def run(self):
        self.running = True
        while self.running:
            try:
                frame = self.capture_queue.get(timeout=1)
                self.frame_counter += 1
                
                # YOLO - Roda a cada N frames para visão contínua sem travar o vídeo
                if self.frame_counter % config.YOLO_SKIP_FRAMES == 0:
                    self.last_yolo_objects, self.last_yolo_boxes = self._rodar_yolo(frame)
                else:
                    # Desenha as caixas salvas nos frames intermediários para manter a UI fluida
                    for label, (x1, y1, x2, y2) in self.last_yolo_boxes:
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
                        cv2.putText(frame, f"{label}", (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

                # LEITURA DE CÓDIGOS (QR, Barra, Matriz, PDF417)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                codigos = pyzbar.decode(gray) # Sem restrições de symbols para ler todos
                
                info_log = None # Dados formatados do código lido para a UI
                
                for code in codigos:
                    qr_lido = code.data.decode("utf-8")
                    tipo_codigo = code.type
                    tempo_atual = time.time()
                    
                    # Desenha o contorno verde e texto
                    pts = code.polygon
                    if len(pts) == 4:
                        pts_array = np.array(pts, dtype=np.int32).reshape((-1, 1, 2))
                        cv2.polylines(frame, [pts_array], True, (0, 255, 0), 3)
                        
                        texto_cv = f"{tipo_codigo}: {qr_lido}"
                        cv2.putText(frame, texto_cv, (pts[0].x, pts[0].y - 10), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    
                    # LÓGICA DO GATILHO: Só registra se for novo ou passar do cooldown
                    if qr_lido != self.ultimo_qr or (tempo_atual - self.tempo_ultimo_qr) > config.TEMPO_COOLDOWN:
                        self.ultimo_qr = qr_lido
                        self.tempo_ultimo_qr = tempo_atual
                        
                        # Salva a foto exata da detecção
                        timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
                        nome_arquivo = f"peca_{qr_lido}_{timestamp}.jpg"
                        nome_arquivo = "".join(x for x in nome_arquivo if x.isalnum() or x in "._-") # Evitar erros de nome de arquivo
                        caminho_foto = os.path.join(config.DIR_FOTOS, nome_arquivo)
                        
                        cv2.imwrite(caminho_foto, frame)
                        
                        # Informa à interface que uma nova leitura ocorreu
                        info_log = {
                            "codigo": qr_lido,
                            "tipo": tipo_codigo,
                            "objetos": self.last_yolo_objects.copy(),
                            "foto": nome_arquivo
                        }
                        break # Processa 1 código novo por frame para evitar duplicidade na tabela
                
                # Atualiza a fila com a imagem tratada, o log de leitura (se houver), e a visão atual da YOLO
                if not self.result_queue.full():
                    self.result_queue.put((frame, info_log, self.last_yolo_objects.copy()))
                    
            except queue.Empty:
                continue

    def _rodar_yolo(self, frame):
        objetos = []
        boxes_info = []
        # Removido o filtro de classes para YOLO reconhecer qualquer coisa (visão total)
        results = self.modelo(frame, verbose=False, conf=0.5, imgsz=320)[0]
        
        for box in results.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            label = results.names[int(box.cls[0])].upper()
            objetos.append(label)
            boxes_info.append((label, (x1, y1, x2, y2)))
            
            # Desenha no frame atual
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
            cv2.putText(frame, f"{label}", (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            
        return list(set(objetos)), boxes_info

    def stop(self):
        self.running = False