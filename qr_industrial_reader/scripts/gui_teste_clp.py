from app.core.config import Config
import os
import sys
import time
import tkinter as tk
import threading

# Garante que o Python ache o Config do projeto
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..")))

try:
    from pyModbusTCP.client import ModbusClient
except ImportError:
    print("Execute 'pip install pyModbusTCP' antes de rodar.")
    sys.exit(1)


class AppTesteCLP:
    def __init__(self, root):
        self.root = root
        self.root.title("Monitor Rápido - Kit Servo")
        self.root.geometry("400x550")
        self.root.configure(bg="#2D2D30")

        self.ip = Config.PLC_IP
        self.port = Config.PLC_PORT
        self.client = ModbusClient(
            host=self.ip,
            port=self.port,
            auto_open=True,
            timeout=0.5)

        # Cabeçalho
        tk.Label(
            root,
            text="DIAGNÓSTICO DIRETO DO CLP",
            fg="white",
            bg="#2D2D30",
            font=(
                "Arial",
                14,
                "bold")).pack(
            pady=10)
        self.lbl_status = tk.Label(
            root,
            text="Conectando...",
            fg="orange",
            bg="#2D2D30",
            font=(
                "Arial",
                11,
                "bold"))
        self.lbl_status.pack(pady=5)

        # Frame Inputs (Sensores / Botoeiras)
        frame_in = tk.LabelFrame(
            root,
            text=" Entradas Físicas (Botões no Kit) ",
            bg="#2D2D30",
            fg="white",
            font=(
                "Arial",
                10))
        frame_in.pack(fill="x", padx=20, pady=10)

        self.ind_i01 = tk.Label(
            frame_in,
            text="I0.1 (Botão LIGA)",
            bg="gray",
            fg="white",
            font=(
                "Arial",
                12,
                "bold"),
            width=25,
            pady=8)
        self.ind_i01.pack(pady=8)
        self.ind_i00 = tk.Label(
            frame_in,
            text="I0.0 (Botão DESLIGA)",
            bg="gray",
            fg="white",
            font=(
                "Arial",
                12,
                "bold"),
            width=25,
            pady=8)
        self.ind_i00.pack(pady=8)

        # Frame Outputs (Motores)
        frame_out = tk.LabelFrame(
            root,
            text=" Saídas Físicas (Motores) ",
            bg="#2D2D30",
            fg="white",
            font=(
                "Arial",
                10))
        frame_out.pack(fill="x", padx=20, pady=10)

        self.ind_q00 = tk.Label(
            frame_out,
            text="Q0.0 (Motor Principal)",
            bg="gray",
            fg="white",
            font=(
                "Arial",
                12,
                "bold"),
            width=25,
            pady=8)
        self.ind_q00.pack(pady=8)
        self.ind_q01 = tk.Label(
            frame_out,
            text="Q0.1 (Outro Motor)",
            bg="gray",
            fg="white",
            font=(
                "Arial",
                12,
                "bold"),
            width=25,
            pady=8)
        self.ind_q01.pack(pady=8)

        # Comandos Modbus Override
        frame_cmd = tk.LabelFrame(
            root,
            text=" Painel de Comandos (Forçar Modbus) ",
            bg="#2D2D30",
            fg="white",
            font=(
                "Arial",
                10))
        frame_cmd.pack(fill="x", padx=20, pady=10)

        btn_frame1 = tk.Frame(frame_cmd, bg="#2D2D30")
        btn_frame1.pack(fill="x", pady=5)
        tk.Button(
            btn_frame1, text="LIGAR Q0.0", bg="#4CAF50", fg="white", font=(
                "Arial", 10, "bold"), command=lambda: self.escrever_saida(
                0, True), width=15).pack(
            side="left", padx=10)
        tk.Button(
            btn_frame1, text="DESLIGAR Q0.0", bg="#F44336", fg="white", font=(
                "Arial", 10, "bold"), command=lambda: self.escrever_saida(
                0, False), width=15).pack(
            side="right", padx=10)

        btn_frame2 = tk.Frame(frame_cmd, bg="#2D2D30")
        btn_frame2.pack(fill="x", pady=5)
        tk.Button(
            btn_frame2, text="LIGAR Q0.1", bg="#2196F3", fg="white", font=(
                "Arial", 10, "bold"), command=lambda: self.escrever_saida(
                1, True), width=15).pack(
            side="left", padx=10)
        tk.Button(
            btn_frame2, text="DESLIGAR Q0.1", bg="#FF9800", fg="white", font=(
                "Arial", 10, "bold"), command=lambda: self.escrever_saida(
                1, False), width=15).pack(
            side="right", padx=10)

        self.running = True
        self.thread = threading.Thread(target=self.loop_leitura, daemon=True)
        self.thread.start()

    def atualizar_cor(self, label, estado):
        cor = "#4CAF50" if estado else "#F44336"  # Verde se True, Vermelho se False
        # Manter nome base sem concatenar 'ON' infinitamente
        texto = label.cget("text").split(" - ")[0]
        label.config(bg=cor,
                     text=f"{texto} - {'ON (ATIVO)' if estado else 'OFF'}")

    def loop_leitura(self):
        while self.running:
            if self.client.open():
                self.lbl_status.config(
                    text=f"✓ ONLINE - Conectado a {self.ip}:{self.port}", fg="#4CAF50")

                # Lê Entradas Discretas %IX0.0 e %IX0.1 (Função Modbus 02)
                inputs = self.client.read_discrete_inputs(0, 2)
                if inputs:
                    self.atualizar_cor(self.ind_i00, inputs[0])
                    self.atualizar_cor(self.ind_i01, inputs[1])

                # Lê Saídas (Coils) %QX0.0 e %QX0.1 (Função Modbus 01)
                coils = self.client.read_coils(0, 2)
                if coils:
                    self.atualizar_cor(self.ind_q00, coils[0])
                    self.atualizar_cor(self.ind_q01, coils[1])
            else:
                self.lbl_status.config(
                    text=f"✕ OFFLINE - Tentando {self.ip}...", fg="#F44336")

            # Atualiza 10 vezes por segundo para resposta instantânea
            time.sleep(0.1)

    def escrever_saida(self, addr, valor):
        # Dispara comando FC05 em Thread para não congelar a UI
        def _write():
            sucesso = self.client.write_single_coil(addr, valor)
            if sucesso:
                print(
                    f"[MODBUS] Sucesso! Forçando Saída Q0.{addr} para {
                        'LIGADO' if valor else 'DESLIGADO'}")
            else:
                print(f"[MODBUS ERRO] Falha ao forçar Saída Q0.{addr}.")
        threading.Thread(target=_write).start()

    def on_close(self):
        self.running = False
        self.client.close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = AppTesteCLP(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
