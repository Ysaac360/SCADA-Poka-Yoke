# script/db_backup.py
from app.core.logger import setup_logger
import os
import sqlite3
import glob
import time
import sys
from datetime import datetime

# Adiciona o diretorio raiz ao path para os imports funcionarem
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            '..')))

# Inicializa o Logger Industrial para registrar o resultado do backup no
# arquivo de logs
logger = setup_logger()

# Define quantos dias os backups serao mantidos antes de serem deletados
# para poupar disco
DIAS_RETENCAO = 30


def fazer_backup():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    data_dir = os.path.join(base_dir, 'data')
    db_path = os.path.join(data_dir, 'scada_qr.db')

    if not os.path.exists(db_path):
        logger.error("[BACKUP ERRO] Banco de dados original nao encontrado.")
        return

    # Cria pasta de backup se nao existir
    backup_dir = os.path.join(data_dir, 'backups')
    os.makedirs(backup_dir, exist_ok=True)

    # Gera nome com a data atual
    data_str = datetime.now().strftime("%Y_%m_%d_%H%M")
    backup_path = os.path.join(backup_dir, f'scada_qr_backup_{data_str}.db')

    try:
        # COPIA SEGURA NATIVA DO SQLITE (Previne corrupcao do modo WAL)
        logger.info("[BACKUP] Iniciando snapshot seguro do banco de dados...")

        # Timeout para evitar falha se o banco estiver sob uso pesado
        banco_origem = sqlite3.connect(db_path, timeout=10.0)
        banco_destino = sqlite3.connect(backup_path)

        with banco_destino:
            # O metodo .backup trava transacoes milissegundos para gerar uma
            # copia perfeitamente integra
            banco_origem.backup(banco_destino)

        banco_origem.close()
        banco_destino.close()

        # AUDITORIA INDUSTRIAL: Verifica se o arquivo gerado possui dados reais
        # (não está vazio)
        tamanho_kb = os.path.getsize(backup_path) / 1024
        if tamanho_kb > 0:
            logger.info(
                f"[BACKUP SUCESSO] Copia finalizada em: {backup_path} ({
                    tamanho_kb:.2f} KB)")
        else:
            logger.error(
                f"[BACKUP ALERTA] Arquivo de backup gerado esta VAZIO (0 KB)! Verifique o disco.")

        # Limpa os backups muito antigos
        _limpar_backups_antigos(backup_dir)

    except Exception as e:
        logger.error(f"[BACKUP ERRO FATAL] Falha ao realizar o backup: {e}")


def _limpar_backups_antigos(backup_dir):
    agora = time.time()
    arquivos = glob.glob(os.path.join(backup_dir, '*.db'))

    removidos = 0
    for arquivo in arquivos:
        # Verifica a data de modificacao do arquivo
        if os.stat(arquivo).st_mtime < agora - \
                (DIAS_RETENCAO * 86400):  # 86400 segundos = 1 dia
            # try/except especifico para evitar crash se o Windows Defender
            # travar o arquivo
            try:
                os.remove(arquivo)
                removidos += 1
            except OSError as e:
                logger.warning(
                    f"[BACKUP AVISO] Nao foi possivel remover backup antigo {arquivo}: {e}")

    if removidos > 0:
        logger.info(
            f"[BACKUP LIMPEZA] {removidos} backup(s) antigo(s) removido(s) (Mais de {DIAS_RETENCAO} dias).")


if __name__ == "__main__":
    fazer_backup()
