# app/ui/main_window.py
import tkinter as tk
from tkinter import ttk
import time

from app.services.scan_service import ScanService
from app.core.config import Config
from app.core.kit_manager import KitManager
from app.ui.views.tab_operacao import TabOperacao
from app.ui.views.tab_engenharia import TabEngenharia

# Cores base do tema Soft SCADA
BG_MAIN = "#2D2D30"
BG_PANEL = "#3E3E42"
TEXT_LIGHT = "#F5F5F5"


class MainWindow:
    def __init__(self, root=None):
        self.root = root if root else tk.Tk()

        self.root.title("IHM SCADA - Poka-Yoke 4.0")
        self.root.geometry("1366x768")
        self.root.configure(bg=BG_MAIN)
        self.root.state('zoomed')
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.service_pecas = ScanService(Config.CAMERA_PECAS, "CAM1-PECAS")
        self.service_nf = ScanService(Config.CAMERA_NF, "CAM2-MASTER")

        # ====================================================
        # CORREÇÃO AQUI: Instanciar o cérebro do sistema (KitManager)
        # ====================================================
        self.kit = KitManager()

        self.rodando = False
        self.tempo_conclusao = 0

        # Calcula o tempo de atualização apenas UMA vez na inicialização
        self.loop_delay = int(
            1000 /
            Config.TARGET_FPS) if hasattr(
            Config,
            'TARGET_FPS') else 33

        self._build_tabs()
        self.root.after(1000, self.start)

    def _build_tabs(self):
        style = ttk.Style()
        style.theme_use("default")

        style.configure("TNotebook", background="#0A0A0A", borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background="#141414",
            foreground="#E0E0E0",
            padding=[
                15,
                5],
            font=(
                'Segoe UI',
                10,
                'bold'))
        style.map(
            "TNotebook.Tab", background=[
                ("selected", "#00B0FF")], foreground=[
                ("selected", "#0A0A0A")])

        header = tk.Frame(self.root, bg=BG_PANEL, height=60, bd=0)
        header.pack(fill="x", side="top")

        # Cria um banner de telemetria SCADA
        self.banner_status = tk.Label(
            header,
            text="SISTEMA DE INSPEÇÃO POKA-YOKE",
            font=(
                "Segoe UI",
                18,
                "bold"),
            fg=TEXT_LIGHT,
            bg=BG_PANEL)
        self.banner_status.pack(pady=10)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_operador = TabOperacao(self.notebook)
        self.tab_engenheiro = TabEngenharia(self.notebook)

        self.notebook.add(self.tab_operador.frame, text=" VISÃO DAS CÂMERAS ")
        self.notebook.add(
            self.tab_engenheiro.frame,
            text=" ENGENHARIA E STATUS ")

        self.tab_engenheiro.btn_reset.config(command=self.reset_kit)
        self.tab_engenheiro.btn_ignorar.config(command=self.retomar_kit)
        self.tab_engenheiro.btn_jog_esteira.bind(
            "<ButtonPress-1>", lambda e: self.kit.plc.partida_esteira())
        self.tab_engenheiro.btn_jog_esteira.bind(
            "<ButtonRelease-1>", lambda e: self.kit.plc.parada_esteira())

    def on_closing(self):
        self.rodando = False
        self.service_nf.stop()
        self.service_pecas.stop()
        self.kit.encerrar_sistema()
        self.root.destroy()

    def start(self):
        if not self.rodando:
            # 1. LIGA O CÉREBRO: Força a conexão com o CLP puxando o IP do .env
            self.kit.plc.conectar()

            # 2. LIGA OS OLHOS: Inicia as câmeras
            self.service_nf.start()
            self.service_pecas.start()
            self.rodando = True

            # 3. ATUALIZA A TELA: Força o painel a ficar VERDE imediatamente
            self.tab_engenheiro.atualizar_dados(self.kit)

            self.update()

    def reset_kit(self):
        self.kit.resetar_esteira()
        # Limpa as estações da tela visual
        self.tab_operador.atualizar_master(None, [])
        self.tab_operador.atualizar_estacoes([], [])
        self.tab_engenheiro.atualizar_dados(self.kit)
        self.tempo_conclusao = 0

    def retomar_kit(self):
        if self.kit.ignorar_erro_e_continuar():
            self.tab_engenheiro.atualizar_dados(self.kit)

    def update(self):
        if not self.rodando:
            return

        self.service_pecas.ia_ativa = (self.kit.status == "MONTANDO")

        atualizou_algo = False
        aba_atual = self.notebook.index(self.notebook.select())

        # =========================================================
        # Renderiza CAM 1 (Esquerda - 5 Peças e IA)
        # =========================================================
        ev_pecas = []
        # Esvazia a fila de eventos rapidamente
        while not self.service_pecas.event_queue.empty():
            ev_pecas.append(self.service_pecas.event_queue.get_nowait())

        # Processa as Peças Lidas e Registra no Histórico
        for ev in ev_pecas:
            if ev.get("novo"):
                codigo = ev["data"]
                # Sempre registra no histórico como LIDO (rastreabilidade
                # absoluta)
                nf_atual_log = self.kit.nf_atual if self.kit.nf_atual else "SEM LOTE"
                self.tab_engenheiro.adicionar_log_db(
                    nf_atual_log, f"LIDO: {codigo}")

                # Se estiver montando, tenta encaixar a peça no Lote
                if self.kit.status == "MONTANDO":
                    sucesso = self.kit.registrar_peca(codigo)
                    if sucesso:
                        atualizou_algo = True
                        self.tab_operador.atualizar_estacoes(
                            self.kit.pecas_esperadas, self.kit.pecas_lidas)
                    else:
                        # Se não teve sucesso, e o status foi para ERRO,
                        # significa Peça Intrusa!
                        if self.kit.status == "ERRO":
                            self.tab_operador.mostrar_rejeicao(codigo)
                            self.tab_engenheiro.adicionar_log_db(
                                self.kit.nf_atual, f"❌ REJEITADO: {codigo}")
                            atualizou_algo = True

        # Pega o frame já processado da fila
        frame_pecas_ui = None
        if not self.service_pecas.ui_queue.empty():
            frame_pecas_ui = self.service_pecas.ui_queue.get_nowait()
            self.ultimo_frame_pecas_time = time.time()

        if frame_pecas_ui is not None and aba_atual == 0:
            self.tab_operador.renderizar_video_pecas(frame_pecas_ui)
        elif aba_atual == 0 and (time.time() - getattr(self, 'ultimo_frame_pecas_time', 0)) > 2.0:
            # Força o frame de SINAL PERDIDO
            self.tab_operador.renderizar_video_pecas(None)

        # =========================================================
        # Renderiza CAM 2 (Direita - Master/Lote)
        # =========================================================
        ev_nf = []
        # 1. Esvazia a fila de eventos rapidamente (Sem usar Lock)
        while not self.service_nf.event_queue.empty():
            ev_nf.append(self.service_nf.event_queue.get_nowait())

        # 2. Pega o frame já processado
        frame_nf_ui = None
        if not self.service_nf.ui_queue.empty():
            frame_nf_ui = self.service_nf.ui_queue.get_nowait()
            self.ultimo_frame_nf_time = time.time()

        if frame_nf_ui is not None and aba_atual == 0:
            self.tab_operador.renderizar_video_nf(frame_nf_ui)
        elif aba_atual == 0 and (time.time() - getattr(self, 'ultimo_frame_nf_time', 0)) > 2.0:
            self.tab_operador.renderizar_video_nf(None)

        # 4. Processa os Eventos (Registra no Banco e UI)
        for ev in ev_nf:
            if ev["novo"] and self.kit.status in [
                    "AGUARDANDO_NF", "CONCLUIDO"]:
                if self.kit.registrar_nf(ev["data"]):
                    atualizou_algo = True
                    self.tab_operador.atualizar_master(
                        self.kit.nf_atual, self.kit.pecas_esperadas)
                    self.tab_operador.atualizar_estacoes(
                        self.kit.pecas_esperadas, self.kit.pecas_lidas)
                    self.tab_engenheiro.adicionar_log_db(
                        self.kit.nf_atual, "--- LOTE INICIADO ---")

        if atualizou_algo:
            self.tab_engenheiro.atualizar_dados(self.kit)

        # =========================================================
        # BANNER DE STATUS SCADA
        # =========================================================
        if self.kit.status == "AGUARDANDO_NF":
            self.banner_status.config(
                text="STATUS: AGUARDANDO LEITURA DO LOTE MASTER",
                bg=BG_PANEL,
                fg=TEXT_LIGHT)
            self.banner_status.master.config(bg=BG_PANEL)
        elif self.kit.status == "MONTANDO":
            progresso = len(self.kit.pecas_lidas)
            total = len(self.kit.pecas_esperadas)
            self.banner_status.config(
                text=f"STATUS: MONTANDO LOTE {
                    self.kit.nf_atual} [{progresso}/{total}]",
                bg="#1565C0",
                fg="#FFFFFF")
            self.banner_status.master.config(bg="#1565C0")
        elif self.kit.status == "ERRO":
            self.banner_status.config(
                text=f"ALERTA CRÍTICO: {
                    self.kit.msg_erro}",
                bg="#D32F2F",
                fg="#FFFFFF")
            self.banner_status.master.config(bg="#D32F2F")
        elif self.kit.status == "CONCLUIDO":
            self.banner_status.config(
                text=f"LOTE {
                    self.kit.nf_atual} CONCLUÍDO COM SUCESSO",
                bg="#2E7D32",
                fg="#FFFFFF")
            self.banner_status.master.config(bg="#2E7D32")

        if self.kit.status == "CONCLUIDO":
            if self.tempo_conclusao == 0:
                self.tempo_conclusao = time.time()
            elif time.time() - self.tempo_conclusao > 4.0:
                self.reset_kit()

                # ... (resto do método update)

        if self.kit.status == "CONCLUIDO":
            if self.tempo_conclusao == 0:
                self.tempo_conclusao = time.time()
            elif time.time() - self.tempo_conclusao > 4.0:
                self.reset_kit()

        # ✅ APENAS ISSO FICA AQUI NO FINAL DO UPDATE
        self.root.after(self.loop_delay, self.update)

    def run(self):
        self.root.mainloop()
