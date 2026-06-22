# app/ui/views/tab_engenharia.py
import tkinter as tk
from tkinter import ttk
import time

# IMPORTAÇÃO CRÍTICA: Puxa as configurações do .env para a Interface Gráfica
from app.core.config import Config

# ===============================================================
# SCADA DEEP DARK MODE
# ===============================================================
BG_MAIN = "#0A0A0A"
BG_PANEL = "#141414"
TEXT_LIGHT = "#E0E0E0"
BTN_BG = "#1A1A1A"
BOX_BG = "#0F0F0F"
ACCENT_GREEN = "#00E676"
ACCENT_BLUE = "#00B0FF"
ACCENT_ORANGE = "#FF9100"
ACCENT_RED = "#FF1744"


class TabEngenharia:
    def __init__(self, parent):
        self.frame = tk.Frame(parent, bg=BG_MAIN)
        self._build_ui()

    def _build_ui(self):
        # ==============================================================
        # PAINEL ESQUERDO: STATUS DO LOTE E BANCO DE DADOS
        # ==============================================================
        painel_esq = tk.Frame(self.frame, bg=BG_PANEL, bd=0)
        painel_esq.pack(
            side="left",
            fill="both",
            expand=True,
            padx=10,
            pady=10)

        tk.Label(
            painel_esq,
            text="STATUS DA MONTAGEM ATUAL",
            font=(
                "Segoe UI",
                12,
                "bold"),
            fg=TEXT_LIGHT,
            bg=BG_PANEL).pack(
            pady=5)
        self.lbl_estado_kit = tk.Label(
            painel_esq, text="AGUARDANDO MASTER...", font=(
                "Segoe UI", 16, "bold"), fg=ACCENT_ORANGE, bg=BG_PANEL)
        self.lbl_estado_kit.pack(pady=5)

        self.lista_pecas = tk.Listbox(
            painel_esq,
            font=(
                "Consolas",
                13,
                "bold"),
            bg=BOX_BG,
            fg=TEXT_LIGHT,
            selectbackground=BG_PANEL,
            bd=0,
            height=8,
            highlightthickness=1,
            highlightcolor="#333333")
        self.lista_pecas.pack(fill="x", padx=15, pady=10)

        tk.Label(
            painel_esq,
            text="REGISTROS DO BANCO DE DADOS (TEMPO REAL)",
            font=(
                "Segoe UI",
                12,
                "bold"),
            fg=TEXT_LIGHT,
            bg=BG_PANEL).pack(
            pady=10)

        style = ttk.Style()
        style.configure(
            "Treeview",
            background=BOX_BG,
            foreground=TEXT_LIGHT,
            fieldbackground=BOX_BG,
            borderwidth=0,
            font=(
                "Segoe UI",
                10))
        style.configure(
            "Treeview.Heading",
            background="#1A1A1A",
            foreground="#A0A0A0",
            font=(
                "Segoe UI",
                10,
                "bold"))
        style.map("Treeview", background=[('selected', BG_PANEL)])

        colunas = ("nf", "peca", "hora")
        self.tree_db = ttk.Treeview(
            painel_esq,
            columns=colunas,
            show="headings",
            height=10)
        self.tree_db.heading("nf", text="LOTE / MASTER")
        self.tree_db.heading("peca", text="PEÇA LIDA")
        self.tree_db.heading("hora", text="HORÁRIO")

        self.tree_db.column("nf", width=150, anchor="center")
        self.tree_db.column("peca", width=250, anchor="w")
        self.tree_db.column("hora", width=100, anchor="center")
        self.tree_db.pack(fill="both", expand=True, padx=15, pady=5)

        # ==============================================================
        # PAINEL DIREITO: COMUNICAÇÃO DE HARDWARE E CLP
        # ==============================================================
        # Levemente mais largo para as labels
        painel_dir = tk.Frame(self.frame, bg=BG_PANEL, bd=0, width=380)
        painel_dir.pack(side="right", fill="y", expand=False, padx=10, pady=10)
        painel_dir.pack_propagate(False)

        tk.Label(
            painel_dir,
            text="COMUNICAÇÃO MODBUS TCP",
            font=(
                "Segoe UI",
                12,
                "bold"),
            fg=TEXT_LIGHT,
            bg=BG_PANEL).pack(
            pady=10)

        # Bloco Estruturado de Status do CLP
        frame_status = tk.Frame(painel_dir, bg=BOX_BG, bd=1, relief="solid")
        frame_status.pack(fill="x", padx=15, pady=5)

        self.lbl_plc_status = tk.Label(
            frame_status,
            text="CLP: DESCONECTADO",
            fg="#9E9E9E",
            bg=BOX_BG,
            font=(
                "Segoe UI",
                11,
                "bold"))
        self.lbl_plc_status.pack(pady=(10, 2))

        # Puxa o IP configurado para provar na tela para onde o Python está
        # enviando pacotes
        self.lbl_plc_ip = tk.Label(
            frame_status,
            text=f"IP ALVO: {
                Config.PLC_IP}:{
                Config.PLC_PORT}",
            fg=ACCENT_BLUE,
            bg=BOX_BG,
            font=(
                "Consolas",
                10))
        self.lbl_plc_ip.pack(pady=(0, 10))

        self.lbl_producao = tk.Label(
            painel_dir, text="PRODUÇÃO DIÁRIA: 0", font=(
                "Segoe UI", 14, "bold"), fg=ACCENT_BLUE, bg=BG_PANEL)
        self.lbl_producao.pack(pady=15)

        # ==============================================================
        # MAPEAMENTO DE BOBINAS (LEDS)
        # ==============================================================
        tk.Label(
            painel_dir,
            text="MONITORAMENTO DE COILS (SAÍDAS)",
            font=(
                "Segoe UI",
                10,
                "bold"),
            fg="#A0A0A0",
            bg=BG_PANEL).pack(
            pady=(
                5,
                0))

        frame_leds = tk.Frame(painel_dir, bg=BG_PANEL)
        frame_leds.pack(pady=5)

        # Vincula os LEDs virtuais aos respectivos Coils do .env
        self.leds_config = {
            "MOTOR": {"nome": f"MOTOR ESTEIRA [Coil {Config.COIL_ESTEIRA}]", "row": 0},
            "SIRENE": {"nome": f"SIRENE DE ERRO [Coil {Config.COIL_ALARME}]", "row": 1},
            "SUCESSO": {"nome": f"LUZ DE SUCESSO [Coil {Config.COIL_SUCESSO}]", "row": 2}
        }

        self.led_canvas = {}
        for key, info in self.leds_config.items():
            tk.Label(
                frame_leds,
                text=info["nome"],
                fg=TEXT_LIGHT,
                bg=BG_PANEL,
                font=(
                    "Segoe UI",
                    10,
                    "bold")).grid(
                row=info["row"],
                column=0,
                padx=10,
                pady=5,
                sticky="e")
            canvas = tk.Canvas(
                frame_leds,
                width=24,
                height=24,
                bg=BG_PANEL,
                highlightthickness=0)
            self.led_canvas[key] = (
                canvas,
                canvas.create_oval(
                    2,
                    2,
                    22,
                    22,
                    fill="#1E1E1E",
                    outline="#333333",
                    width=2))
            canvas.grid(row=info["row"], column=1)

        # ==============================================================
        # PAINEL DE COMANDOS FORÇADOS
        # ==============================================================
        frame_cmd = tk.Frame(painel_dir, bg=BOX_BG, bd=0)
        frame_cmd.pack(pady=20, padx=15, fill="x")
        tk.Label(
            frame_cmd,
            text="PAINEL DE COMANDO FÍSICO",
            font=(
                "Segoe UI",
                10,
                "bold"),
            fg=TEXT_LIGHT,
            bg=BOX_BG).pack(
            pady=10)

        self.btn_reset = tk.Button(
            frame_cmd,
            text="RESET CICLO (Zerar Memória)",
            bg=ACCENT_RED,
            fg="white",
            font=(
                "Segoe UI",
                11,
                "bold"),
            relief="flat",
            height=1,
            activebackground="#B71C1C",
            activeforeground="white")
        self.btn_reset.pack(fill="x", padx=15, pady=5)

        # Botão indica exatamente o que faz no hardware
        self.btn_ignorar = tk.Button(
            frame_cmd,
            text=f"FORÇAR RETOMADA (Desligar Coil {
                Config.COIL_ALARME})",
            bg=ACCENT_ORANGE,
            fg="white",
            font=(
                "Segoe UI",
                10,
                "bold"),
            relief="flat",
            height=2,
            activebackground="#E65100",
            activeforeground="white")
        self.btn_ignorar.pack(fill="x", padx=15, pady=5)

        # Botão indica exatamente qual motor é Jogado
        self.btn_jog_esteira = tk.Button(
            frame_cmd,
            text=f"JOG MOTOR (Forçar Coil {
                Config.COIL_ESTEIRA})",
            bg=BTN_BG,
            fg="white",
            font=(
                "Segoe UI",
                10,
                "bold"),
            relief="flat",
            height=2,
            activebackground="#333333",
            activeforeground="white")
        self.btn_jog_esteira.pack(fill="x", padx=15, pady=5)

    def adicionar_log_db(self, nf, peca):
        hora_atual = time.strftime("%H:%M:%S")
        self.tree_db.insert("", 0, values=(nf, peca, hora_atual))
        if len(self.tree_db.get_children()) > 30:
            self.tree_db.delete(self.tree_db.get_children()[-1])

    def atualizar_dados(self, kit):
        clp_online = kit.plc.client.is_open if (
            hasattr(kit.plc, 'client') and kit.plc.client) else False

        # 1. ATUALIZA A CONEXÃO MODBUS
        if clp_online:
            self.lbl_plc_status.config(
                text="STATUS: ONLINE (MODBUS TCP)", fg=ACCENT_GREEN)
            self.lbl_plc_ip.config(
                text=f"IP ALVO: {
                    Config.PLC_IP}:{
                    Config.PLC_PORT} | TX/RX: OK",
                fg=ACCENT_BLUE)

            # --- O SEGREDO DA MALHA FECHADA ---
            # Aqui o SCADA interroga a placa mãe do CLP para saber o status dos
            # relés
            if hasattr(kit.plc, 'ler_status_fisico'):
                status_fisico = kit.plc.ler_status_fisico()
                st_motor = status_fisico.get(Config.COIL_ESTEIRA, False)
                st_sirene = status_fisico.get(Config.COIL_ALARME, False)
                st_sucesso = status_fisico.get(Config.COIL_SUCESSO, False)
            else:
                st_motor = (kit.status == "MONTANDO")
                st_sirene = (kit.status == "ERRO")
                st_sucesso = (kit.status == "CONCLUIDO")
        else:
            self.lbl_plc_status.config(
                text="STATUS: OFFLINE / TENTANDO...", fg=ACCENT_RED)
            self.lbl_plc_ip.config(
                text=f"IP ALVO: {
                    Config.PLC_IP}:{
                    Config.PLC_PORT} | TX/RX: FALHA",
                fg="#9E9E9E")

            # Se o cabo estiver desconectado, o LED não pode acender de jeito
            # nenhum!
            st_motor = False
            st_sirene = False
            st_sucesso = False

        # 2. ACENDE OS LEDs COM BASE NA LEITURA REAL
        self.led_canvas["MOTOR"][0].itemconfig(
            self.led_canvas["MOTOR"][1],
            fill=ACCENT_GREEN if st_motor else "#1E1E1E")
        self.led_canvas["SIRENE"][0].itemconfig(
            self.led_canvas["SIRENE"][1],
            fill=ACCENT_RED if st_sirene else "#1E1E1E")
        self.led_canvas["SUCESSO"][0].itemconfig(
            self.led_canvas["SUCESSO"][1],
            fill=ACCENT_GREEN if st_sucesso else "#1E1E1E")

        # 3. ATUALIZA TEXTOS DE STATUS
        cores_status = {
            "AGUARDANDO_NF": ACCENT_ORANGE,
            "MONTANDO": ACCENT_BLUE,
            "CONCLUIDO": ACCENT_GREEN,
            "ERRO": ACCENT_RED}
        self.lbl_estado_kit.config(
            text=kit.status if kit.status != "ERRO" else kit.msg_erro,
            fg=cores_status.get(
                kit.status,
                TEXT_LIGHT))
        self.lbl_producao.config(
            text=f"PRODUÇÃO DIÁRIA: {
                kit.total_produzido}")

        # 4. ATUALIZA LISTA DE PEÇAS
        self.lista_pecas.delete(0, tk.END)
        if not kit.pecas_esperadas:
            self.lista_pecas.insert(
                tk.END, " Aguardando Leitura da Caixa Master...")
            self.lista_pecas.itemconfig(tk.END, {'fg': '#9E9E9E'})
        else:
            for peca in kit.pecas_esperadas:
                status = "[ OK ]" if peca in kit.pecas_lidas else "[ -- ]"
                self.lista_pecas.insert(tk.END, f" {status} {peca}")
                self.lista_pecas.itemconfig(
                    tk.END, {'fg': ACCENT_GREEN if peca in kit.pecas_lidas else '#757575'})
