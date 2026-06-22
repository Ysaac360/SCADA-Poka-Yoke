# app/core/logger.py
import logging
from logging.handlers import TimedRotatingFileHandler
import os


def setup_logger():
    # Cria a pasta de logs na raiz se nao existir
    base_dir = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            '../..'))
    log_dir = os.path.join(base_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, 'scada_poka_yoke.log')

    # MELHORIA 1: Formato industrial com rastreabilidade de arquivo e linha
    # Exemplo: 2026-04-07 14:30:00 [INFO] [kit_manager.py:42] Lote validado.
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Handler 1: Console (Terminal)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Handler 2: Arquivo Rotativo
    file_handler = TimedRotatingFileHandler(
        log_file,
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)

    # Configura o Logger Raiz (Root)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Limpa handlers antigos para nao duplicar linhas caso a funcao seja
    # chamada duas vezes
    if logger.hasHandlers():
        logger.handlers.clear()

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    # MELHORIA 2: Silenciador de Bibliotecas Externas (Evita poluir o log)
    # Impede que bibliotecas gerem mensagens de INFO desnecessarias no arquivo
    # da esteira
    logging.getLogger("ultralytics").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)  # Blindagem extra
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)

    # Handler 3: Arquivo Exclusivo para Erros (Grave, Fatal, Crash)
    error_log_file = os.path.join(log_dir, 'scada_erros_criticos.log')
    error_handler = TimedRotatingFileHandler(
        error_log_file,
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)  # <--- SÓ CAPTURA ERROR OU CRITICAL
    logger.addHandler(error_handler)

    return logger
