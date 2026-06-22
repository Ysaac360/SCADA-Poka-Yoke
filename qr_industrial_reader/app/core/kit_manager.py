# app/core/kit_manager.py
import logging
import time
import threading
from app.db.database import Database
from app.core.plc_manager import PLCManager


class KitManager:
    def __init__(self):
        self.db = Database()
        self.plc = PLCManager()

        self.nf_atual = None
        self.nf_id_db = None
        self.pecas_esperadas = []
        self.pecas_lidas = set()
        self.status = "AGUARDANDO_NF"
        self.msg_erro = ""
        self.total_produzido = self.db.contar_producao_hoje()
        self.status_lock = threading.Lock()  # Lock para impedir colisao de memoria

        # MELHORIA: Controle de Estagnação (Timeout)
        self.timeout_segundos = 60
        self.ultima_peca_lida_time = 0
        self.watchdog_thread = threading.Thread(
            target=self._timeout_watchdog, daemon=True)
        self.watchdog_thread.start()

    def _timeout_watchdog(self):
        """Monitora silenciosamente se a linha de montagem ficou estagnada."""
        while True:
            time.sleep(5)  # Verificação leve a cada 5s
            # Se está no meio de uma montagem
            if getattr(self, 'status',
                       None) == "MONTANDO" and self.ultima_peca_lida_time > 0:
                tempo_ocioso = time.time() - self.ultima_peca_lida_time
                if tempo_ocioso > self.timeout_segundos:
                    # Timeout estourou! Aborta o processo.
                    with self.status_lock:
                        if self.status == "MONTANDO":
                            self.status = "ERRO"
                            self.msg_erro = f"TIMEOUT: Lote estagnado por {
                                int(tempo_ocioso)}s. Lote rejeitado!"
                            logging.warning(
                                f"[ALERTA CRITICO] {
                                    self.msg_erro}")

                            self.plc.acionar_falha()
                            self.ultima_peca_lida_time = 0  # Previne loop infinito de alarmes

    def registrar_nf(self, data: str) -> bool:
        data = data.strip()
        if not isinstance(data, str):
            return False

        # Flexibilidade extrema de delimitadores para a Data Matrix
        for delim in [',', '|', '\t']:
            data = data.replace(delim, ';')

        # Se ainda não tiver ponto e vírgula, mas tiver espaços separando
        if ';' not in data and ' ' in data:
            data = data.replace(' ', ';')

        # Agora verifica se conseguiu separar em pelo menos 2 partes
        if ";" not in data:
            return False

        partes = [item.strip() for item in data.split(';') if item.strip()]

        if len(partes) >= 1:
            # Identificação do Lote Virtual ou Real
            novo_nf = ""
            novas_esperadas = []
            if len(partes) > 5:
                novo_nf = partes[0]
                novas_esperadas = partes[1:]
            else:
                novo_nf = f"LOTE_{partes[0][:6]}"
                novas_esperadas = partes

            # Proteção contra re-leitura do mesmo Lote Master se já está
            # rodando
            if self.nf_atual == novo_nf and self.status == "MONTANDO":
                return False

            self.nf_atual = novo_nf
            self.pecas_esperadas = novas_esperadas
            self.pecas_lidas.clear()
            self.nf_id_db = self.db.iniciar_nf(self.nf_atual)
            with self.status_lock:
                self.status = "MONTANDO"
                self.msg_erro = ""
            self.ultima_peca_lida_time = time.time()  # Dispara o relógio de timeout

            logging.info(
                f"[KIT] Lote Master: {
                    self.nf_atual} | Aguardando {
                    len(
                        self.pecas_esperadas)} pecas: {
                    self.pecas_esperadas}")

            # Padrao de comando PLC: Libera a esteira para as peças virem
            self.plc.reset_sistema()
            self.plc.partida_esteira()
            return True

        return False

    def registrar_peca(self, data_peca: str) -> bool:
        data_peca = data_peca.strip()

        # Se não houver uma Master aberta, a Câmera 1 é ignorada
        if self.status != "MONTANDO":
            return False

        # Valida se a peça lida pertence à lista da Caixa Master
        if data_peca in self.pecas_esperadas:
            # FILTRO DE DUPLICIDADE ABSOLUTO
            if data_peca not in self.pecas_lidas:
                self.pecas_lidas.add(data_peca)
                # Reseta o relógio de timeout (peça válida recebida)
                self.ultima_peca_lida_time = time.time()

                # Salva no Banco de Dados apenas 1 vez!
                if self.nf_id_db:
                    self.db.registrar_peca(self.nf_id_db, data_peca)

                self._verificar_conclusao()

                # Retorna True PARA A UI: Autoriza colocar na lista da Aba de
                # Engenharia
                return True
            else:
                # O quadrado visual continua na tela, mas não registra
                # novamente
                return False
        else:
            # PEÇA INTRUSA DETECTADA (Erro Rigoroso)
            with self.status_lock:
                self.status = "ERRO"
                self.msg_erro = f"PECA INTRUSA: {data_peca}"
            logging.warning(f"[ALERTA CRITICO] {self.msg_erro}")

            # Intertravamento imediato: Para a esteira e liga a sirene
            self.plc.acionar_falha()
            return False

    def _verificar_conclusao(self):
        # Validação rigorosa: Só conclui se as 5 peças da Master forem lidas
        if len(self.pecas_lidas) == len(self.pecas_esperadas):
            with self.status_lock:
                self.status = "CONCLUIDO"
            self.ultima_peca_lida_time = 0  # Desliga o relógio de timeout

            if self.nf_id_db:
                self.db.concluir_nf(self.nf_id_db)

            self.total_produzido += 1
            logging.info(
                f"[KIT] SUCESSO! Lote {self.nf_atual} validado ({len(self.pecas_lidas)}/{len(self.pecas_esperadas)} peças).")

            # Comando PLC: Peças certas, avança a caixa Master
            self.plc.lote_concluido()

    def ignorar_erro_e_continuar(self):
        if self.status == "ERRO":
            logging.info(
                f"[KIT] Operador forçou retomada. Voltando a inspecionar o lote {
                    self.nf_atual}...")
            with self.status_lock:
                self.status = "MONTANDO"
                self.msg_erro = ""
            self.ultima_peca_lida_time = time.time()  # Reinicia o relógio

            self.plc.reset_sistema()
            self.plc.partida_esteira()
            return True
        return False

    def resetar_esteira(self):
        logging.info("[KIT] Reset de Emergência acionado. Memória esvaziada.")
        self.nf_atual = None
        self.nf_id_db = None
        self.pecas_esperadas = []
        self.pecas_lidas.clear()
        with self.status_lock:
            self.status = "AGUARDANDO_NF"
            self.msg_erro = ""
        self.ultima_peca_lida_time = 0  # Desliga o relógio

        self.plc.reset_sistema()

    def encerrar_sistema(self):
        self.plc.desconectar()
        self.db.close()
