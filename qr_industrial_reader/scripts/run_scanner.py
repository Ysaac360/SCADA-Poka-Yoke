# scripts/run_scanner.py
from app.core.kit_manager import KitManager
from app.core.config import Config
from app.services.scan_service import ScanService
from app.core.logger import setup_logger
import sys
import os
import time
import logging

# Adiciona o diretorio raiz ao path para os imports funcionarem
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            '..')))

# Inicializa o Logger Industrial PRIMEIRO
setup_logger()


def main():
    logging.info("=" * 50)
    logging.info(
        "[SYSTEM] Iniciando SCADA em Modo Headless (Sem Interface Grafica)")
    logging.info("=" * 50)

    # Instanciamos o cerebro (Que conecta no BD e no CLP)
    kit = KitManager()

    # 1. FORCA A CONEXAO COM O CLP ANTES DE INICIAR A ESTEIRA
    kit.plc.conectar()

    # Instanciamos os scanners (Alinhado com as novas regras: Cam 1=Pecas, Cam
    # 2=Master)
    service_pecas = ScanService(Config.CAMERA_PECAS, "CAM1-PECAS")
    service_nf = ScanService(Config.CAMERA_NF, "CAM2-MASTER")

    try:
        service_nf.start()
        service_pecas.start()

        logging.info(
            "[SYSTEM] Servicos de visao computacional e CLP em execucao.")
        logging.info(
            "[DICA] Em modo Headless, apresente um QR Code escrito 'RESET' para destravar a esteira em caso de erro.")

        tempo_conclusao = 0
        while True:
            # Otimização: A IA só gasta CPU se a Caixa Master já tiver sido
            # lida
            service_pecas.ia_ativa = (kit.status == "MONTANDO")

            ev_nf = []
            ev_pecas = []

            # ========================================================
            # COLETA ASSINCRONA DE DADOS (Consumo de Filas)
            # ========================================================
            while not service_nf.event_queue.empty():
                ev_nf.append(service_nf.event_queue.get_nowait())

            while not service_pecas.event_queue.empty():
                ev_pecas.append(service_pecas.event_queue.get_nowait())

            # ========================================================
            # PROCESSAMENTO DA CÂMERA 2 (Caixa Master e Lote)
            # ========================================================
            for ev in ev_nf:
                if ev["novo"]:
                    if kit.status in ["AGUARDANDO_NF", "CONCLUIDO"]:
                        kit.registrar_nf(ev["data"])
                    elif kit.status == "ERRO" and ev["data"].strip().upper() == "RESET":
                        # OPERACAO INDUSTRIAL: Reset via visao computacional
                        logging.info(
                            "[OPERACAO] Comando de RESET via QR Code reconhecido na Cam 2!")
                        kit.ignorar_erro_e_continuar()

            # ========================================================
            # PROCESSAMENTO DA CÂMERA 1 (Peças e IA)
            # ========================================================
            for ev in ev_pecas:
                if ev["novo"]:
                    if kit.status == "ERRO":
                        # Permite que o operador mostre o RESET na camera de
                        # pecas tambem
                        if ev["data"].strip().upper() == "RESET":
                            logging.info(
                                "[OPERACAO] Comando de RESET via QR Code reconhecido na Cam 1!")
                            kit.ignorar_erro_e_continuar()
                    else:
                        kit.registrar_peca(ev["data"])

            # ========================================================
            # CONTROLE DE FIM DE CICLO
            # ========================================================
            if kit.status == "CONCLUIDO":
                if tempo_conclusao == 0:
                    tempo_conclusao = time.time()
                elif time.time() - tempo_conclusao > 4.0:
                    kit.resetar_esteira()
                    tempo_conclusao = 0

            # Dorme um pouco para nao fritar a CPU (Modo Headless e muito
            # rapido)
            time.sleep(0.05)

    except KeyboardInterrupt:
        logging.info("\n[SYSTEM] Encerrado pelo usuario (Ctrl+C).")
    except Exception as e:
        logging.exception("[ERRO CRITICO] Falha no laco principal Headless:")
    finally:
        logging.info("[SYSTEM] Parando maquinas e servicos...")
        service_nf.stop()
        service_pecas.stop()
        kit.encerrar_sistema()
        sys.exit(0)


if __name__ == "__main__":
    main()
