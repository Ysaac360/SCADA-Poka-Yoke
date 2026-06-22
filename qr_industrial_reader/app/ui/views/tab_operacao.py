# app/ui/views/tab_operacao.py
import tkinter as tk
import cv2
import numpy as np
from PIL import Image, ImageTk

LARGURA_CAM = 640
ALTURA_CAM = 480

# ===============================================================
# SCADA DEEP DARK MODE (Cyberpunk Industrial Premium)
# ===============================================================
BG_MAIN = "#0A0A0A"
BG_PANEL = "#141414"
TEXT_LIGHT = "#E0E0E0"
ACCENT_GREEN = "#00E676"  # Verde Neon
ACCENT_BLUE = "#00B0FF"   # Azul Neon
ACCENT_ORANGE = "#FF9100"  # Laranja Neon
ACCENT_RED = "#FF1744"    # Vermelho Sangue (Falha Crítica)
BOX_BG = "#0F0F0F"        # Fundo interno das caixas


class TabOperacao:
    def __init__(self, parent):
        self.frame = tk.Frame(parent, bg=BG_MAIN)
        self.imgtk_nf = None
        self.imgtk_pecas = None

        # Cria frames de "Sem Sinal" para usar como fallback de erro, já em
        # RGB!
        self.frame_sem_sinal = np.zeros(
            (ALTURA_CAM, LARGURA_CAM, 3), dtype=np.uint8)
        cv2.putText(self.frame_sem_sinal, "SINAL DA CAMERA PERDIDO", (80, ALTURA_CAM // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 3)

        self._build_ui()

    def _build_ui(self):
        container = tk.Frame(self.frame, bg=BG_MAIN)
        container.pack(expand=True, fill="both", padx=15, pady=15)

        # ===============================================================
        # PAINEL ESQUERDO: CÂMERA 1 (PEÇAS / AS 5 ESTAÇÕES)
        # ===============================================================
        painel_pecas = tk.Frame(container, bg=BG_PANEL, bd=0)
        painel_pecas.pack(side="left", expand=True, fill="both", padx=10)

        tk.Label(
            painel_pecas,
            text="CÂMERA 1: PEÇAS (5 CÓDIGOS + IA)",
            font=(
                "Segoe UI",
                12,
                "bold"),
            fg=TEXT_LIGHT,
            bg=BG_PANEL).pack(
            pady=10)
        self.video_pecas = tk.Label(
            painel_pecas,
            bg="#000000",
            width=LARGURA_CAM,
            height=ALTURA_CAM)
        self.video_pecas.pack(padx=15, pady=5)

        box_registro_pecas = tk.Frame(
            painel_pecas, bg=BOX_BG, bd=1, relief="solid")
        box_registro_pecas.pack(fill="both", expand=True, padx=15, pady=10)

        tk.Label(
            box_registro_pecas,
            text="STATUS DAS 5 ESTAÇÕES:",
            fg=TEXT_LIGHT,
            bg=BOX_BG,
            font=(
                "Segoe UI",
                11,
                "bold")).pack(
            anchor="w",
            padx=10,
            pady=(
                10,
                5))

        self.leds_estacoes = []
        for i in range(5):
            f_estacao = tk.Frame(box_registro_pecas, bg=BOX_BG)
            f_estacao.pack(anchor="w", padx=15, pady=2)

            canvas = tk.Canvas(
                f_estacao,
                width=20,
                height=20,
                bg=BOX_BG,
                highlightthickness=0)
            canvas.pack(side="left")
            led = canvas.create_oval(
                2, 2, 18, 18, fill="#424242", outline="#111111", width=2)

            lbl = tk.Label(
                f_estacao,
                text=f"ESTAÇÃO {
                    i + 1}: AGUARDANDO LOTE",
                fg="#757575",
                bg=BOX_BG,
                font=(
                    "Consolas",
                    12,
                    "bold"))
            lbl.pack(side="left", padx=10)

            self.leds_estacoes.append(
                {"canvas": canvas, "led": led, "lbl": lbl})

        self.lbl_rejeitada = tk.Label(
            box_registro_pecas,
            text="",
            fg=ACCENT_RED,
            bg=BOX_BG,
            font=(
                "Segoe UI",
                11,
                "bold"))
        self.lbl_rejeitada.pack(anchor="w", padx=15, pady=(10, 0))

        # ===============================================================
        # PAINEL DIREITO: CÂMERA 2 (CAIXA MASTER / LOTE)
        # ===============================================================
        painel_nf = tk.Frame(container, bg=BG_PANEL, bd=0)
        painel_nf.pack(side="right", expand=True, fill="both", padx=10)

        tk.Label(
            painel_nf,
            text="CÂMERA 2: CAIXA MASTER (LOTE)",
            font=(
                "Segoe UI",
                12,
                "bold"),
            fg=TEXT_LIGHT,
            bg=BG_PANEL).pack(
            pady=10)
        self.video_nf = tk.Label(
            painel_nf,
            bg="#000000",
            width=LARGURA_CAM,
            height=ALTURA_CAM)
        self.video_nf.pack(padx=15, pady=5)

        box_registro_nf = tk.Frame(painel_nf, bg=BOX_BG, bd=1, relief="solid")
        box_registro_nf.pack(fill="both", expand=True, padx=15, pady=10)

        tk.Label(
            box_registro_nf,
            text="CÓDIGO MASTER (LOTE):",
            fg=TEXT_LIGHT,
            bg=BOX_BG,
            font=(
                "Segoe UI",
                11,
                "bold")).pack(
            anchor="w",
            padx=10,
            pady=(
                10,
                0))
        self.lbl_master_valor = tk.Label(
            box_registro_nf,
            text="[ AGUARDANDO MASTER ]",
            fg=ACCENT_BLUE,
            bg=BOX_BG,
            font=(
                "Consolas",
                13,
                "bold"))
        self.lbl_master_valor.pack(anchor="w", padx=15, pady=2)

        tk.Label(
            box_registro_nf,
            text="PEÇAS VINCULADAS AO LOTE:",
            fg=TEXT_LIGHT,
            bg=BOX_BG,
            font=(
                "Segoe UI",
                10,
                "bold")).pack(
            anchor="w",
            padx=10,
            pady=(
                10,
                0))
        self.lbl_master_pecas = tk.Label(
            box_registro_nf, text="...", fg="#9E9E9E", bg=BOX_BG, font=(
                "Consolas", 11, "bold"), justify="left")
        self.lbl_master_pecas.pack(anchor="w", padx=15, pady=2)

    # ===============================================================
    # ATUALIZADORES DE LÓGICA DE NEGÓCIO
    # ===============================================================
    def mostrar_rejeicao(self, codigo):
        self.lbl_rejeitada.config(text=f"❌ PEÇA REJEITADA (INTRUSA): {codigo}")

    def atualizar_estacoes(self, esperadas, lidas):
        if not esperadas:
            for i in range(5):
                item = self.leds_estacoes[i]
                item["lbl"].config(
                    text=f"ESTAÇÃO {
                        i + 1}: AGUARDANDO LOTE",
                    fg="#757575")
                item["canvas"].itemconfig(
                    item["led"], fill="#424242", outline="#111111")
            return

        for i in range(5):
            item = self.leds_estacoes[i]
            if i < len(esperadas):
                peca = esperadas[i]
                if peca in lidas:
                    item["lbl"].config(
                        text=f"ESTAÇÃO {
                            i + 1}: {peca}",
                        fg=TEXT_LIGHT)
                    # LED VERDE NEON
                    item["canvas"].itemconfig(
                        item["led"], fill=ACCENT_GREEN, outline="#FFFFFF")
                else:
                    item["lbl"].config(
                        text=f"ESTAÇÃO {
                            i + 1}: AGUARDANDO LIGAÇÃO...",
                        fg=ACCENT_ORANGE)
                    # LED LARANJA NEON PISCANDO
                    item["canvas"].itemconfig(
                        item["led"], fill=ACCENT_ORANGE, outline="#FFFFFF")
            else:
                item["lbl"].config(
                    text=f"ESTAÇÃO {
                        i + 1}: NÃO UTILIZADA",
                    fg="#555555")
                item["canvas"].itemconfig(
                    item["led"], fill="#212121", outline="#111111")

    def atualizar_master(self, master_code, esperadas):
        # Limpa a rejeição ao iniciar novo master ou reset
        self.lbl_rejeitada.config(text="")
        if not master_code:
            self.lbl_master_valor.config(
                text="[ AGUARDANDO MASTER ]", fg=ACCENT_BLUE)
            self.lbl_master_pecas.config(text="...", fg="#757575")
            return

        self.lbl_master_valor.config(text=master_code)

        # OTIMIZAÇÃO: Uso de list comprehension para montar a string
        linhas_pecas = [
            f"QR{
                i + 1} -> {peca}" for i,
            peca in enumerate(esperadas)]
        texto_pecas = "\n".join(linhas_pecas)

        self.lbl_master_pecas.config(text=texto_pecas, fg=TEXT_LIGHT)

    # ===============================================================
    # RENDERIZADORES DE VÍDEO (AGORA 100% DINÂMICOS E LEVES)
    # ===============================================================
    def renderizar_video_pecas(self, frame_rgb):
        # POKA-YOKE: Se o Wi-fi falhar, injeta frame de alerta!
        if frame_rgb is None:
            frame_rgb = self.frame_sem_sinal

        self.imgtk_pecas = ImageTk.PhotoImage(image=Image.fromarray(frame_rgb))
        self.video_pecas.configure(image=self.imgtk_pecas)

    def renderizar_video_nf(self, frame_rgb):
        # POKA-YOKE: Se o Wi-fi falhar, injeta frame de alerta!
        if frame_rgb is None:
            frame_rgb = self.frame_sem_sinal

        self.imgtk_nf = ImageTk.PhotoImage(image=Image.fromarray(frame_rgb))
        self.video_nf.configure(image=self.imgtk_nf)
