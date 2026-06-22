# main.py
import time
import queue
import tkinter as tk
from tkinter import ttk
import cv2
from PIL import Image, ImageTk

import config
from camera import CameraStream
from vision import VisionProcessor

class ScadaInterface:
    def __init__(self, root):
        self.root = root
        self.root.title("SCADA VISION DEMO - MULTI-LEITURA & IA")
        self.root.geometry("1280x800")
        self.root.configure(bg=config.BG_COLOR)

        self.cap_queue = queue.Queue(maxsize=2)
        self.res_queue = queue.Queue(maxsize=2)
        
        self.camera_thread = None
        self.vision_thread = None
        self.running = False
        
        self.setup_ui()

    def setup_ui(self):
        # Header
        header = tk.Frame(self.root, bg=config.ACCENT_COLOR, height=40)
        header.pack(fill="x")
        self.lbl_header = tk.Label(header, text="SUPERVISÓRIO POKA-YOKE | STATUS: PARADO", 
                                   bg=config.ACCENT_COLOR, font=config.FONT_TITLE)
        self.lbl_header.pack(pady=10)

        main_container = tk.Frame(self.root, bg=config.BG_COLOR)
        main_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Monitor de Vídeo
        self.vid_label = tk.Label(main_container, bg="black", bd=2, relief="sunken")
        self.vid_label.pack(side="left", fill="both", expand=True)

        # Painel Lateral
        side_panel = tk.Frame(main_container, bg=config.BG_COLOR, width=350)
        side_panel.pack(side="right", fill="y", padx=(10, 0))

        tk.Label(side_panel, text="ÚLTIMA PEÇA LIDA", fg="#888", bg=config.BG_COLOR).pack()
        self.qr_val = tk.Label(side_panel, text="---", fg=config.ACCENT_COLOR, bg=config.PANEL_COLOR, 
                               font=config.FONT_DATA, width=20, pady=10)
        self.qr_val.pack(pady=5)

        tk.Label(side_panel, text="REGISTRO DE PRODUÇÃO (CÓDIGO + OBJETOS)", fg="white", bg=config.BG_COLOR).pack(anchor="w", pady=(10,0))
        
        # Tabela (Treeview)
        self.log_tree = ttk.Treeview(side_panel, columns=("T", "C"), show="headings", height=15)
        self.log_tree.heading("T", text="HORA")
        self.log_tree.heading("C", text="REGISTRO DE INSPEÇÃO")
        self.log_tree.column("T", width=80, anchor="center")
        self.log_tree.column("C", width=400, anchor="w") # <-- Aumentei a largura de 250 para 400
        self.log_tree.pack(fill="both", expand=True)
        
        self.btn_start = tk.Button(side_panel, text="INICIAR SCADA", command=self.start_system, 
                                   bg="#008800", fg="white", font=config.FONT_TITLE, height=2)
        self.btn_start.pack(fill="x", pady=10)
        
        tk.Button(side_panel, text="PARAR", command=self.stop_system, bg="#444", fg="white", font=config.FONT_TITLE).pack(fill="x")

    def start_system(self):
        if not self.running:
            self.running = True
            self.btn_start.config(state="disabled", bg="#222")
            self.lbl_header.config(text="SUPERVISÓRIO POKA-YOKE | STATUS: EM OPERAÇÃO")
            
            self.camera_thread = CameraStream(config.URL_CAMERA, self.cap_queue)
            self.vision_thread = VisionProcessor(self.cap_queue, self.res_queue, config.MODELO_YOLO)
            
            self.camera_thread.start()
            self.vision_thread.start()
            
            self.update_screen()

    def update_screen(self):
        if not self.running:
            return

        try:
            # Esvazia a fila para pegar sempre o frame mais RECENTE.
            # Isso evita que o vídeo fique com atraso (delay) em relação à vida real.
            processed_frame, qr_code, info_log = None, "NENHUM", "NENHUM"
            
            while not self.res_queue.empty():
                processed_frame, qr_code, info_log = self.res_queue.get_nowait()
            
            if processed_frame is not None:
                img = Image.fromarray(cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB))
                imgtk = ImageTk.PhotoImage(image=img)
                self.vid_label.configure(image=imgtk)
                self.vid_label.image = imgtk
                
                # Atualiza o registro APENAS se houver uma nova leitura confirmada
                if info_log != "NENHUM":
                    self.qr_val.config(text=qr_code)
                    self.log_tree.insert("", 0, values=(time.strftime("%H:%M:%S"), info_log))
                    
        except queue.Empty:
            pass

        # Podemos baixar para 15ms ou 20ms para a tela ficar mais fluida
        self.root.after(20, self.update_screen)
                    
    def stop_system(self):
        self.running = False
        if self.camera_thread: self.camera_thread.stop()
        if self.vision_thread: self.vision_thread.stop()
        self.btn_start.config(state="normal", bg="#008800")
        self.lbl_header.config(text="SUPERVISÓRIO POKA-YOKE | STATUS: PARADO")

if __name__ == "__main__":
    root = tk.Tk()
    app = ScadaInterface(root)
    root.mainloop()