# app/core/plc_manager.py
import logging
import time
import queue
import threading
from app.core.config import Config

try:
    from pyModbusTCP.client import ModbusClient
except ImportError:
    ModbusClient = None
    logging.warning(
        "[SISTEMA] Biblioteca pyModbusTCP nao encontrada. O CLP operara apenas em MODO SIMULACAO.")


class PLCManager:
    def __init__(self):
        self.ip = Config.PLC_IP
        self.port = Config.PLC_PORT
        self.client = None
        self.modo_simulacao = True

        # MELHORIA: Tolerância a falhas na rede industrial
        self.max_retries = 3

        if ModbusClient:
            # Timeout otimizado para não gargalar o processamento do vídeo
            self.client = ModbusClient(
                host=self.ip,
                port=self.port,
                auto_open=True,
                timeout=0.5)

        # =========================================================
        # MOTOR ASSÍNCRONO MODBUS (Zero-Lag UI)
        # =========================================================
        self.cmd_queue = queue.Queue()
        self.running = True
        self.alarme_ativo_cache = False  # Cache Anti-Lag
        self.worker_thread = threading.Thread(
            target=self._modbus_worker, daemon=True)
        self.worker_thread.start()

    def _modbus_worker(self):
        """Carteiro Invisível: Processa fila Modbus sem travar o PC"""
        while self.running:
            try:
                cmd = self.cmd_queue.get(timeout=0.5)
                # cmd = {"coil": 0, "estado": True, "nome": "MOTOR"}
                self._escrever_fisico(cmd["coil"], cmd["estado"], cmd["nome"])
            except queue.Empty:
                pass

    def conectar(self) -> bool:
        if self.client and self.client.open():
            self.modo_simulacao = False
            logging.info(
                f"[CLP] ONLINE - Handshake estabelecido via Modbus TCP {self.ip}:{self.port}")
            return True
        else:
            self.modo_simulacao = True
            logging.warning(
                f"[CLP] OFFLINE - Falha de comunicacao em {
                    self.ip}:{
                    self.port}. Ativando MODO SIMULACAO.")
            return False

    def _escrever_bobina_segura(
            self, coil: int, estado: bool, nome: str) -> bool:
        """
        Coloca a ordem na fila do carteiro em background (retorna na hora, liberando a tela).
        """
        if self.modo_simulacao or not self.client:
            return True

        self.cmd_queue.put({"coil": coil, "estado": estado, "nome": nome})
        return True

    def _escrever_fisico(self, coil: int, estado: bool, nome: str) -> bool:
        """
        Execução real e pesada do Modbus que roda no background.
        """
        for tentativa in range(self.max_retries):
            sucesso = self.client.write_single_coil(coil, estado)
            if sucesso:
                if coil == Config.COIL_ALARME:
                    self.alarme_ativo_cache = estado
                txt_estado = "LIGADO (ON)" if estado else "DESLIGADO (OFF)"
                logging.info(
                    f"[CLP COMANDO] {nome} [Coil {coil}] forçado para -> {txt_estado}")
                return True

            logging.warning(
                f"[CLP REDE] Pacote perdido ao acionar {nome} (Coil {coil}). Tentativa {
                    tentativa + 1}/{
                    self.max_retries}...")
            time.sleep(0.05)  # Backoff curto antes de tentar novamente

        logging.error(
            f"[CLP ERRO CRÍTICO] Falha de comunicação Modbus ao acionar {nome} após {
                self.max_retries} tentativas.")
        return False

    def _ler_bobina_segura(self, coil: int, nome: str) -> bool:
        """Lê o status atual no CLP."""
        if self.modo_simulacao or not self.client:
            return False

        resultado = self.client.read_coils(coil, 1)
        if resultado:
            return resultado[0]

        return False

    # ==========================================
    # LÓGICA DE MALHA FECHADA (FEEDBACK P/ UI)
    # ==========================================
    def ler_status_fisico(self):
        """
        Lê a memória real do CLP em uma ÚNICA REQUISIÇÃO (Bulk Read)
        para economizar banda de rede e evitar travamentos na interface.
        """
        if self.modo_simulacao or not self.client:
            return {Config.COIL_ESTEIRA: False,
                    Config.COIL_ALARME: False, Config.COIL_SUCESSO: False}

        # Lê 3 coils começando do endereço 0 (assumindo que Esteira=0, Alarme=1, Sucesso=2)
        # Atenção: Isso exige que os Coils no config.py sejam adjacentes (0, 1
        # e 2).
        menor_coil = min(
            Config.COIL_ESTEIRA,
            Config.COIL_ALARME,
            Config.COIL_SUCESSO)
        quantidade_coils = 3

        resultados = self.client.read_coils(menor_coil, quantidade_coils)

        if resultados and len(resultados) == 3:
            self.alarme_ativo_cache = resultados[1]
            # Assumindo a ordem física: 0=Esteira, 1=Alarme, 2=Sucesso
            return {
                Config.COIL_ESTEIRA: resultados[0],
                Config.COIL_ALARME: resultados[1],
                Config.COIL_SUCESSO: resultados[2]
            }
        else:
            return {Config.COIL_ESTEIRA: False,
                    Config.COIL_ALARME: False, Config.COIL_SUCESSO: False}

    # ==========================================
    # LÓGICA DE MÁQUINA E INTERTRAVAMENTOS
    # ==========================================

    def partida_esteira(self):
        """ Aciona a esteira com Intertravamento usando Cache (Zero Lag). """
        if self.alarme_ativo_cache:
            logging.warning(
                "[CLP INTERTRAVAMENTO] Bloqueio de Partida: Alarme ativo na Memoria RAM. Faça o RESET primeiro.")
            return False

        return self._escrever_bobina_segura(
            Config.COIL_ESTEIRA, True, "MOTOR ESTEIRA")

    def parada_esteira(self):
        """ Corta a movimentação imediatamente. """
        self._escrever_bobina_segura(
            Config.COIL_ESTEIRA, False, "MOTOR ESTEIRA")

    def acionar_falha(self):
        """ Sequência Poka-Yoke: Para Motor, Corta Sucesso, Aciona Sirene. """
        self.parada_esteira()
        self._escrever_bobina_segura(Config.COIL_SUCESSO, False, "LUZ SUCESSO")
        self._escrever_bobina_segura(
            Config.COIL_ALARME, True, "SIRENE DE ERRO")

    def reset_sistema(self):
        """ Acknowledgement (ACK). Zera alarmes. """
        self.parada_esteira()
        self._escrever_bobina_segura(Config.COIL_SUCESSO, False, "LUZ SUCESSO")
        self._escrever_bobina_segura(
            Config.COIL_ALARME, False, "SIRENE DE ERRO")

    def lote_concluido(self):
        """ Handshake de Fim de Ciclo. """
        self.parada_esteira()
        self._escrever_bobina_segura(
            Config.COIL_ALARME, False, "SIRENE DE ERRO")
        self._escrever_bobina_segura(Config.COIL_SUCESSO, True, "LUZ SUCESSO")

    # ==========================================
    # ALIASES DE COMPATIBILIDADE PARA O KIT_MANAGER
    # ==========================================
    def sinalizar_erro(self, estado=True):
        if estado:
            self.acionar_falha()
        else:
            self._escrever_bobina_segura(
                Config.COIL_ALARME, False, "SIRENE DE ERRO")

    def sinalizar_sucesso(self, estado=True):
        if estado:
            self.lote_concluido()
        else:
            self._escrever_bobina_segura(
                Config.COIL_SUCESSO, False, "LUZ SUCESSO")

    def parar_esteira(self):
        self.parada_esteira()

    # ==========================================
    # DESCONEXÃO SEGURA
    # ==========================================
    def desconectar(self):
        """Procedimento seguro de shutdown da rede Modbus."""
        self.running = False  # Encerra o carteiro

        if self.client and self.client.is_open:
            # Estado Seguro Total Forçado de Imediato (bypass da fila pra
            # garantir desligamento)
            self._escrever_fisico(
                Config.COIL_ESTEIRA,
                False,
                "MOTOR ESTEIRA (SHUTDOWN)")
            self._escrever_fisico(Config.COIL_ALARME, False, "SHUTDOWN")
            self._escrever_fisico(Config.COIL_SUCESSO, False, "SHUTDOWN")

            self.client.close()
            logging.info(
                "[CLP] Conexão Modbus TCP encerrada com segurança e máquina em repouso.")
        else:
            logging.info("[CLP] Conexão virtual encerrada.")
