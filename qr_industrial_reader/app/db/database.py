# app/db/database.py
import sqlite3
import os
import logging
import threading
import queue
from datetime import datetime


class Database:
    def __init__(self, db_name="scada_qr.db"):
        base_dir = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                '../..'))
        # Garante a criacao da pasta 'data' isolada
        data_dir = os.path.join(base_dir, 'data')
        os.makedirs(data_dir, exist_ok=True)

        self.db_path = os.path.join(data_dir, db_name)

        # MELHORIA: Cadeado para acesso simultaneo das cameras e conexao
        # persistente
        self.lock = threading.Lock()
        self.conn = self._connect()
        self._create_tables()

        # =========================================================
        # BANCO DE DADOS ASSÍNCRONO (Zero-Lag UI)
        # =========================================================
        self.db_queue = queue.Queue()
        self.running = True
        self.worker_thread = threading.Thread(
            target=self._db_worker, daemon=True)
        self.worker_thread.start()

    def _db_worker(self):
        """Thread de Background dedicada apenas à gravação de disco"""
        while self.running or not self.db_queue.empty():
            try:
                req = self.db_queue.get(timeout=0.2)
                tipo = req.get("tipo")
                try:
                    if tipo == "registrar_peca":
                        self._executar_registrar_peca(
                            req["nf_id"], req["codigo_qr"], req["agora"])
                    elif tipo == "concluir_nf":
                        self._executar_concluir_nf(
                            req["nf_id"], req["hora_atual"])
                except Exception as e:
                    logging.error(f"[DB ASYNC] Erro fatal no worker: {e}")
                finally:
                    self.db_queue.task_done()
            except queue.Empty:
                pass

    def _connect(self):
        # check_same_thread=False permite que as threads das câmeras usem esta
        # mesma conexão
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=15.0)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        # Forca a integridade relacional
        conn.execute('PRAGMA foreign_keys=ON')
        # Reforça a paciência do banco em concorrência
        conn.execute('PRAGMA busy_timeout=15000')
        return conn

    def _create_tables(self):
        with self.lock:
            # Gerencia transacao (commit/rollback) automaticamente
            with self.conn:
                self.conn.execute('''
                    CREATE TABLE IF NOT EXISTS ordens_producao (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nf_code TEXT UNIQUE NOT NULL,
                        data_inicio DATE NOT NULL,
                        hora_inicio TIME NOT NULL,
                        hora_fim TIME,
                        status TEXT NOT NULL
                    )
                ''')
                self.conn.execute('''
                    CREATE TABLE IF NOT EXISTS pecas_montadas (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nf_id INTEGER NOT NULL,
                        codigo_qr TEXT NOT NULL,
                        timestamp DATETIME NOT NULL,
                        FOREIGN KEY (nf_id) REFERENCES ordens_producao (id) ON DELETE CASCADE
                    )
                ''')
                self.conn.execute(
                    'CREATE INDEX IF NOT EXISTS idx_codigo_qr ON pecas_montadas(codigo_qr)')

    def iniciar_nf(self, nf_code: str) -> int:
        agora = datetime.now()
        data_str = agora.strftime("%Y-%m-%d")
        hora_str = agora.strftime("%H:%M:%S")

        try:
            with self.lock:
                with self.conn:
                    # UPSERT: Se o lote ja existe (ex: parada de maquina),
                    # retoma o lote
                    self.conn.execute('''
                        INSERT INTO ordens_producao (nf_code, data_inicio, hora_inicio, status)
                        VALUES (?, ?, ?, 'EM ANDAMENTO')
                        ON CONFLICT(nf_code) DO UPDATE SET
                            status = 'EM ANDAMENTO',
                            hora_fim = NULL
                    ''', (nf_code, data_str, hora_str))

                    cursor = self.conn.execute(
                        'SELECT id FROM ordens_producao WHERE nf_code = ?', (nf_code,))
                    result = cursor.fetchone()
                    return result[0] if result else None
        except Exception as e:
            logging.error(f"[DB] Erro ao Iniciar NF: {e}")
            return None

    def registrar_peca(self, nf_id: int, codigo_qr: str):
        # Dispara para o banco de dados via Fila Assíncrona para não travar a
        # UI
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.db_queue.put({
            "tipo": "registrar_peca",
            "nf_id": nf_id,
            "codigo_qr": codigo_qr,
            "agora": agora
        })

    def _executar_registrar_peca(self, nf_id: int, codigo_qr: str, agora: str):
        try:
            with self.lock:
                with self.conn:
                    cursor = self.conn.execute(
                        'SELECT EXISTS(SELECT 1 FROM pecas_montadas WHERE nf_id = ? AND codigo_qr = ?)',
                        (nf_id,
                         codigo_qr))
                    existe = cursor.fetchone()[0]

                    if not existe:
                        self.conn.execute('''
                            INSERT INTO pecas_montadas (nf_id, codigo_qr, timestamp)
                            VALUES (?, ?, ?)
                        ''', (nf_id, codigo_qr, agora))
        except Exception as e:
            logging.error(f"[DB ASYNC] Erro ao Registrar Peca: {e}")

    def concluir_nf(self, nf_id: int):
        hora_atual = datetime.now().strftime("%H:%M:%S")
        self.db_queue.put({
            "tipo": "concluir_nf",
            "nf_id": nf_id,
            "hora_atual": hora_atual
        })

    def _executar_concluir_nf(self, nf_id: int, hora_atual: str):
        try:
            with self.lock:
                with self.conn:
                    self.conn.execute(
                        "UPDATE ordens_producao SET status = 'CONCLUIDO', hora_fim = ? WHERE id = ?",
                        (hora_atual,
                         nf_id))
        except Exception as e:
            logging.error(f"[DB ASYNC] Erro ao Concluir NF: {e}")

    def contar_producao_hoje(self) -> int:
        try:
            with self.lock:
                cursor = self.conn.execute(
                    "SELECT COUNT(*) FROM ordens_producao WHERE status = 'CONCLUIDO' AND data_inicio = date('now', 'localtime')")
                return cursor.fetchone()[0]
        except Exception as e:
            logging.error(f"[DB] Erro ao buscar total produzido: {e}")
            return 0

    def close(self):
        """Fecha a conexao de forma limpa ao encerrar o sistema"""
        self.running = False
        # Dá tempo ao banco para salvar qualquer peça remanescente na fila
        # antes de morrer
        if getattr(self, 'worker_thread',
                   None) and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)

        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
