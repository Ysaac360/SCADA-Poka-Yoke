# script/testar_clp.py
"""
testar_clp.py — Console Interativo para CLP Altus via Modbus TCP
Mapeamento baseado no programa PLC_PRG (IEC 61131-3 Structured Text)

Recursos:
  • Dashboard de I/O em tempo real (refresh sem piscar)
  • Comandos manuais com verificação de consistência pós-escrita
  • Diagnóstico de conexão (ping Modbus com estatísticas)
  • Log estruturado em JSONL (rastreabilidade completa)
  • Reconexão automática com relatório de RTT
"""

import sys
import os
import time
import datetime
import json
import logging
from typing import Any

# ── Resolve raiz do projeto para importar Config ────────────────────────────
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..")))

try:
    from app.core.config import Config
    PLC_IP = Config.PLC_IP
    PLC_PORT = Config.PLC_PORT
except Exception:
    # Fallback: lê direto do .env na raiz se Config não existir
    PLC_IP = os.getenv("PLC_IP", "172.20.10.190")
    PLC_PORT = int(os.getenv("PLC_PORT", "502"))

try:
    from pyModbusTCP.client import ModbusClient
except ImportError:
    print("❌  pyModbusTCP não instalado. Execute: pip install pyModbusTCP")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════════════════
#  CORES ANSI
# ═══════════════════════════════════════════════════════════════════════════


class Cor:
    RST = "\033[0m"
    BLD = "\033[1m"
    DIM = "\033[2m"
    R = "\033[91m"
    G = "\033[92m"
    Y = "\033[93m"
    B = "\033[94m"
    M = "\033[95m"
    C = "\033[96m"
    W = "\033[97m"
    BG_R = "\033[41m"
    BG_G = "\033[42m"
    BG_Y = "\033[43m"
    BG_K = "\033[40m"


def badge(val: bool | None, t: str = "ON", f: str = "OFF") -> str:
    if val is None:
        return f"{Cor.DIM}[---]{Cor.RST}"
    return f"{Cor.BG_G}{Cor.BLD} {t} {Cor.RST}" if val else f"{Cor.BG_R}{Cor.BLD} {f} {Cor.RST}"

# ═══════════════════════════════════════════════════════════════════════════
#  MAPEAMENTO COMPLETO — PLC_PRG
# ═══════════════════════════════════════════════════════════════════════════


# Saídas Digitais %QX  →  Coils Modbus (FC01 leitura / FC05 escrita)
COILS: dict[str, dict[str, Any]] = {
    "Q00_Motor": {"addr": 0, "desc": "Motor Esteira", "icon": "⚙ "},
    "Q01_Avanca": {"addr": 1, "desc": "Cilindro Avança", "icon": "→ "},
    "Q02_Recua": {"addr": 2, "desc": "Cilindro Recua", "icon": "← "},
    "Q03_Lampada": {"addr": 3, "desc": "Lâmpada Lote OK", "icon": "* "},
}

# Entradas Digitais %IX  →  Discrete Inputs (FC02 leitura)
INPUTS: dict[str, dict[str, Any]] = {
    "I00_Stop": {"addr": 0, "desc": "Parada Emg (NF)", "icon": "! "},
    "I01_Start": {"addr": 1, "desc": "Partida (NA)", "icon": "+ "},
    "I02_Reset": {"addr": 2, "desc": "Reset Lote (NA)", "icon": "~ "},
    "I03_Sensor": {"addr": 3, "desc": "Sensor Peça (NA)", "icon": "@ "},
}

# Registradores %MW  →  Holding Registers (FC03 leitura / FC06 escrita)
REGISTERS: dict[str, dict[str, Any]] = {
    "Estado": {"addr": 0, "desc": "Máquina de Estados (0–6)"},
    "Contador_Pecas": {"addr": 1, "desc": "Peças no lote atual"},
}

ESTADOS: dict[int, str] = {
    0: "DESLIGADO",
    1: "PROCESSO ATIVO",
    2: "SENSOR DETECTADO - AGUARDA 1s",
    3: "AVANÇANDO (3s)",
    4: "RECUANDO (2s)",
    5: "CONTAGEM",
    6: "LOTE CONCLUÍDO",
}

LOTE_MAX = 5  # Contador_Pecas >= 5 → Estado 6

# ═══════════════════════════════════════════════════════════════════════════
#  PATHS DE LOG
# ═══════════════════════════════════════════════════════════════════════════
_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_JSONL = os.path.join(_DIR, "clp_eventos.jsonl")
LOG_DEBUG = os.path.join(_DIR, "clp_debug.log")

logging.basicConfig(
    filename=LOG_DEBUG,
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)-8s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_log = logging.getLogger("clp")


def log_evento(tipo: str, dados: dict) -> None:
    entry = {"ts": datetime.datetime.now().isoformat(), "tipo": tipo, **dados}
    try:
        with open(LOG_JSONL, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass
    _log.info("%s | %s", tipo, dados)


# ═══════════════════════════════════════════════════════════════════════════
#  TERMINAL HELPERS
# ═══════════════════════════════════════════════════════════════════════════
def cls() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def separador(char="─", n=62) -> None:
    print(f"{Cor.DIM}{char * n}{Cor.RST}")


def header(subtitulo: str = "") -> None:
    cls()
    print(f"{Cor.B}{'═' * 62}{Cor.RST}")
    print(f"{Cor.C}{Cor.BLD}  ALTUS PLC CONSOLE  |  {PLC_IP}:{PLC_PORT}{Cor.RST}")
    if subtitulo:
        print(f"{Cor.DIM}  {subtitulo}{Cor.RST}")
    print(f"{Cor.B}{'═' * 62}{Cor.RST}")


def cor_estado(eid: int) -> str:
    mapa = {
        0: Cor.DIM,
        1: Cor.G,
        2: Cor.Y,
        3: Cor.C,
        4: Cor.M,
        5: Cor.B,
        6: Cor.G +
        Cor.BLD}
    return mapa.get(eid, Cor.W)


def fmt_estado(eid: int | None) -> str:
    if eid is None:
        return f"{Cor.DIM}???{Cor.RST}"
    return f"{cor_estado(eid)}[{eid}] {ESTADOS.get(eid, 'DESCONHECIDO')}{Cor.RST}"


def cursor_up(n: int) -> None:
    if n > 0:
        sys.stdout.write(f"\033[{n}A")
        sys.stdout.flush()


def overwrite_line(text: str) -> None:
    """Sobrescreve a linha atual limpando até o fim."""
    sys.stdout.write(f"\r{text}\033[K\n")


# ═══════════════════════════════════════════════════════════════════════════
#  HANDLER MODBUS
# ═══════════════════════════════════════════════════════════════════════════
class CLPHandler:
    def __init__(self) -> None:
        self._client = ModbusClient(
            host=PLC_IP,
            port=PLC_PORT,
            auto_open=True,
            auto_close=False,
            timeout=2.0,
        )
        self.online = False

    # ── Conexão ─────────────────────────────────────────────────────────
    def conectar(self, tentativas: int = 3, espera: float = 2.0) -> bool:
        print(f"\n{Cor.Y}  Conectando a {PLC_IP}:{PLC_PORT}...{Cor.RST}\n")
        for i in range(1, tentativas + 1):
            t0 = time.monotonic()
            try:
                ok = self._client.open()
            except Exception as exc:
                ok = False
                _log.error("open() excecao: %s", exc)

            rtt_ms = (time.monotonic() - t0) * 1000

            if ok:
                self.online = True
                print(
                    f"  {Cor.G}[{i}/{tentativas}] CONECTADO  RTT={rtt_ms:.1f}ms{Cor.RST}")
                log_evento(
                    "CONEXAO_OK", {
                        "ip": PLC_IP, "port": PLC_PORT, "rtt_ms": round(
                            rtt_ms, 2)})
                return True

            err_txt = getattr(self._client, "last_error_txt", "sem detalhe")
            print(
                f"  {Cor.R}[{i}/{tentativas}] FALHA  ({err_txt})  RTT={rtt_ms:.1f}ms{Cor.RST}")
            log_evento(
                "CONEXAO_FALHA", {
                    "tentativa": i, "erro": err_txt, "rtt_ms": round(
                        rtt_ms, 2)})

            if i < tentativas:
                time.sleep(espera)

        self.online = False
        return False

    def fechar(self) -> None:
        self._client.close()
        self.online = False

    # ── Leituras básicas ─────────────────────────────────────────────────
    def _coils(self, addr: int, count: int) -> list[bool] | None:
        return self._client.read_coils(addr, count)

    def _inputs(self, addr: int, count: int) -> list[bool] | None:
        return self._client.read_discrete_inputs(addr, count)

    def _regs(self, addr: int, count: int) -> list[int] | None:
        return self._client.read_holding_registers(addr, count)

    def _write_coil(self, addr: int, val: bool) -> bool:
        return bool(self._client.write_single_coil(addr, val))

    # ── Snapshot completo ─────────────────────────────────────────────────
    def snapshot(self) -> dict[str, Any]:
        snap: dict[str, Any] = {
            "ts": datetime.datetime.now().isoformat(),
            "online": False,
            "coils": {k: None for k in COILS},
            "inputs": {k: None for k in INPUTS},
            "registers": {"Estado": None, "Contador_Pecas": None},
        }

        # Saídas Q (Coils)
        coils_raw = self._coils(0, len(COILS))
        if coils_raw:
            snap["online"] = True
            for nome, info in COILS.items():
                idx = info["addr"]
                snap["coils"][nome] = coils_raw[idx] if idx < len(
                    coils_raw) else None

        # Entradas I (Discrete Inputs)
        inp_raw = self._inputs(0, len(INPUTS))
        if inp_raw:
            for nome, info in INPUTS.items():
                idx = info["addr"]
                snap["inputs"][nome] = inp_raw[idx] if idx < len(
                    inp_raw) else None

        # Registradores %MW (Holding Registers)
        reg_raw = self._regs(0, len(REGISTERS))
        if reg_raw:
            snap["registers"]["Estado"] = reg_raw[0]
            snap["registers"]["Contador_Pecas"] = reg_raw[1]

        self.online = snap["online"]
        return snap

    # ── Escrita com verificação ───────────────────────────────────────────
    def escrever_coil(self, addr: int, val: bool) -> tuple[bool, bool | None]:
        """
        Escreve coil e verifica consistência após 100ms.
        Retorna: (escrita_ok, valor_lido_apos)
        """
        ok = self._write_coil(addr, val)
        log_evento("ESCRITA", {"addr": addr, "valor": val, "ack": ok})

        time.sleep(0.1)
        lido = self._coils(addr, 1)
        lido_val = lido[0] if lido else None
        log_evento(
            "VERIFICACAO", {
                "addr": addr, "esperado": val, "lido": lido_val})
        return ok, lido_val


# ═══════════════════════════════════════════════════════════════════════════
#  TELA: DASHBOARD EM TEMPO REAL
# ═══════════════════════════════════════════════════════════════════════════
_DASH_LINHAS = 0  # rastreia quantas linhas foram impressas


def _render_dashboard(snap: dict) -> int:
    """Renderiza o dashboard e retorna a quantidade de linhas impressas."""
    global _DASH_LINHAS
    linhas: list[str] = []

    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    conn_badge = badge(snap["online"], "ONLINE", "OFFLINE")
    linhas.append(f"  {Cor.DIM}[ {ts} ]  CLP: {conn_badge}{Cor.RST}")
    linhas.append("")

    # Estado e Contador
    eid = snap["registers"]["Estado"]
    cnt = snap["registers"]["Contador_Pecas"]
    bar = ""
    if cnt is not None:
        filled = min(cnt, LOTE_MAX)
        bar = f"{
            Cor.G}{
            '█' *
            filled}{
            Cor.DIM}{
                '░' *
                (
                    LOTE_MAX -
                    filled)}{
                        Cor.RST}"

    linhas.append(f"  {Cor.BLD}ESTADO   :{Cor.RST} {fmt_estado(eid)}")
    linhas.append(
        f"  {
            Cor.BLD}LOTE     :{
            Cor.RST} {bar}  {
                Cor.Y}{
                    Cor.BLD}{
                        cnt if cnt is not None else '?'}{
                            Cor.RST}/{LOTE_MAX}")
    linhas.append("")

    # Saídas Q
    linhas.append(f"  {Cor.BLD}SAÍDAS DIGITAIS  %QX  (Coils){Cor.RST}")
    linhas.append(f"  {Cor.DIM}{'─' * 54}{Cor.RST}")
    for nome, info in COILS.items():
        val = snap["coils"].get(nome)
        linhas.append(
            f"  {
                info['icon']} {
                nome:<16} {
                Cor.DIM}{
                    info['desc']:<22}{
                        Cor.RST} {
                            badge(val)}")

    linhas.append("")

    # Entradas I
    linhas.append(
        f"  {
            Cor.BLD}ENTRADAS DIGITAIS  %IX  (Discrete Inputs){
            Cor.RST}")
    linhas.append(f"  {Cor.DIM}{'─' * 54}{Cor.RST}")
    for nome, info in INPUTS.items():
        val = snap["inputs"].get(nome)
        linhas.append(
            f"  {
                info['icon']} {
                nome:<16} {
                Cor.DIM}{
                    info['desc']:<22}{
                        Cor.RST} {
                            badge(
                                val,
                                'ATIVO',
                                'INATIVO')}")

    linhas.append("")
    linhas.append(f"{Cor.DIM}  CTRL+C para voltar ao menu{'─' * 33}{Cor.RST}")

    # Overwrite linhas anteriores (sem piscar)
    if _DASH_LINHAS > 0:
        cursor_up(_DASH_LINHAS)

    for linha in linhas:
        overwrite_line(linha)

    _DASH_LINHAS = len(linhas)
    return _DASH_LINHAS


def tela_dashboard(clp: CLPHandler) -> None:
    global _DASH_LINHAS
    _DASH_LINHAS = 0
    header("Dashboard de I/O — Tempo Real  |  Modbus FC01 + FC02 + FC03")
    print(f"\n{Cor.C}  Iniciando leitura contínua...{Cor.RST}\n")
    try:
        while True:
            snap = clp.snapshot()
            _render_dashboard(snap)
            time.sleep(0.4)
    except KeyboardInterrupt:
        _DASH_LINHAS = 0
        print(f"\n\n  {Cor.Y}Voltando ao menu...{Cor.RST}\n")
        time.sleep(0.5)


# ═══════════════════════════════════════════════════════════════════════════
#  TELA: COMANDOS MANUAIS
# ═══════════════════════════════════════════════════════════════════════════

# (coil_key, val, label)
CMDS_COIL = {
    "1": ("Q00_Motor", True, "Motor LIGAR"),
    "2": ("Q00_Motor", False, "Motor DESLIGAR"),
    "3": ("Q01_Avanca", True, "Avanço ATIVAR"),
    "4": ("Q01_Avanca", False, "Avanço DESATIVAR"),
    "5": ("Q02_Recua", True, "Recuo ATIVAR"),
    "6": ("Q02_Recua", False, "Recuo DESATIVAR"),
    "7": ("Q03_Lampada", True, "Lâmpada LIGAR"),
    "8": ("Q03_Lampada", False, "Lâmpada APAGAR"),
}


def _resultado_escrita(coil_key: str, val: bool, ok: bool,
                       lido: bool | None) -> None:
    nome = COILS[coil_key]["desc"]
    ack_cor = Cor.G if ok else Cor.R
    ack_ico = "OK" if ok else "NAK"
    print(
        f"\n  {ack_cor}[ESCRITA {ack_ico}]  {nome} → {
            'ON' if val else 'OFF'}{
            Cor.RST}")

    if lido is None:
        print(f"  {Cor.R}[VERIFICAÇÃO] Leitura de confirmação falhou{Cor.RST}")
    elif lido == val:
        print(
            f"  {
                Cor.G}[VERIFICAÇÃO] CLP confirmou: {
                'ON' if lido else 'OFF'}  ✓ Consistente{
                Cor.RST}")
    else:
        print(
            f"  {
                Cor.R}[VERIFICAÇÃO] DIVERGÊNCIA!  Escrito={
                'ON' if val else 'OFF'}  Lido={
                'ON' if lido else 'OFF'}{
                    Cor.RST}")
        print(
            f"  {
                Cor.Y}  Possível causa: intertravamento do programa PLC_PRG{
                Cor.RST}")


def tela_comandos(clp: CLPHandler) -> None:
    while True:
        header("Comandos Manuais — Escrita Direta nos Coils %QX")
        print(f"\n{Cor.M}  COMANDOS INDIVIDUAIS{Cor.RST}")
        separador()
        for k, (coil, val, label) in CMDS_COIL.items():
            ico = Cor.G + "+" if val else Cor.R + "-"
            print(
                f"  [{
                    Cor.Y}{k}{
                    Cor.RST}] {ico}{
                    Cor.RST}  {
                    label:<28}  {
                        Cor.DIM}addr={
                            COILS[coil]['addr']}{
                                Cor.RST}")

        print(f"\n{Cor.M}  COMANDOS GLOBAIS{Cor.RST}")
        separador()
        print(f"  [{Cor.Y}A{Cor.RST}] Todos ON   (Emergency-ON)")
        print(f"  [{Cor.Y}Z{Cor.RST}] Todos OFF  (Emergency-STOP)")
        print(f"  [{Cor.Y}L{Cor.RST}] Ler snapshot de I/O agora")
        print(f"\n  [{Cor.R}0{Cor.RST}] Voltar ao menu principal")
        separador()

        cmd = input(f"\n  {Cor.C}Comando:{Cor.RST} ").strip().upper()

        if cmd == "0":
            break

        elif cmd == "A":
            print()
            for coil_key, info in COILS.items():
                ok, lido = clp.escrever_coil(info["addr"], True)
                cor = Cor.G if ok else Cor.R
                print(
                    f"  {cor}{
                        'OK' if ok else 'ERR'}{
                        Cor.RST}  {coil_key}  → ON")
            input(f"\n  {Cor.DIM}[ENTER]{Cor.RST}")

        elif cmd == "Z":
            print()
            for coil_key, info in COILS.items():
                ok, lido = clp.escrever_coil(info["addr"], False)
                cor = Cor.G if ok else Cor.R
                print(
                    f"  {cor}{
                        'OK' if ok else 'ERR'}{
                        Cor.RST}  {coil_key}  → OFF")
            input(f"\n  {Cor.DIM}[ENTER]{Cor.RST}")

        elif cmd == "L":
            snap = clp.snapshot()
            print(f"\n  {Cor.C}Snapshot @ {snap['ts']}{Cor.RST}")
            print(
                f"  Online: {
                    snap['online']}  Estado: {
                    snap['registers']['Estado']}  Peças: {
                    snap['registers']['Contador_Pecas']}")
            for k, v in snap["coils"].items():
                print(
                    f"  {k}: {
                        'ON' if v else 'OFF' if v is not None else '?'}")
            for k, v in snap["inputs"].items():
                print(
                    f"  {k}: {
                        'ATIVO' if v else 'INATIVO' if v is not None else '?'}")
            input(f"\n  {Cor.DIM}[ENTER]{Cor.RST}")

        elif cmd in CMDS_COIL:
            coil_key, val, label = CMDS_COIL[cmd]
            addr = COILS[coil_key]["addr"]
            ok, lido = clp.escrever_coil(addr, val)
            _resultado_escrita(coil_key, val, ok, lido)
            input(f"\n  {Cor.DIM}[ENTER]{Cor.RST}")

        else:
            print(f"  {Cor.R}Opção inválida.{Cor.RST}")
            time.sleep(0.6)


# ═══════════════════════════════════════════════════════════════════════════
#  TELA: DIAGNÓSTICO DE CONEXÃO
# ═══════════════════════════════════════════════════════════════════════════

def tela_diagnostico(clp: CLPHandler) -> None:
    header("Diagnóstico de Conexão — Ping Modbus TCP")

    AMOSTRAS = 15
    INTERVALO = 0.2

    print(f"\n  Executando {AMOSTRAS} leituras de coil (ping Modbus TCP)...\n")
    separador()

    rtts: list[float] = []
    erros = 0

    for i in range(1, AMOSTRAS + 1):
        t0 = time.monotonic()
        resultado = clp._client.read_coils(0, 1)
        rtt = (time.monotonic() - t0) * 1000

        if resultado is not None:
            rtts.append(rtt)
            barra = "█" * min(int(rtt / 5), 30)
            cor = Cor.G if rtt < 50 else (Cor.Y if rtt < 150 else Cor.R)
            print(
                f"  {
                    Cor.G}OK{
                    Cor.RST}  #{
                    i:02d}  {cor}{
                    rtt:6.1f} ms  {barra}{
                        Cor.RST}")
        else:
            erros += 1
            err_txt = getattr(clp._client, "last_error_txt", "timeout")
            print(
                f"  {
                    Cor.R}ERR{
                    Cor.RST} #{
                    i:02d}  {
                    Cor.R}TIMEOUT / {err_txt}{
                        Cor.RST}")

        time.sleep(INTERVALO)

    separador()

    total = len(rtts)
    taxa = 100 * total // AMOSTRAS
    cor_taxa = Cor.G if taxa >= 90 else (Cor.Y if taxa >= 60 else Cor.R)

    print(f"\n  {Cor.BLD}RESULTADOS{Cor.RST}")
    print(
        f"  Pacotes OK   : {
            Cor.G}{total}/{AMOSTRAS}{
            Cor.RST}  ({cor_taxa}{taxa}%{
                Cor.RST})")
    print(f"  Pacotes ERR  : {Cor.R if erros else Cor.DIM}{erros}{Cor.RST}")

    if rtts:
        avg = sum(rtts) / len(rtts)
        print(f"  Latência min : {min(rtts):.2f} ms")
        print(f"  Latência max : {max(rtts):.2f} ms")
        print(f"  Latência avg : {avg:.2f} ms")
        print(f"  Jitter       : {max(rtts) - min(rtts):.2f} ms")

        qualidade = "ÓTIMA" if avg < 10 else (
            "BOA" if avg < 50 else (
                "ACEITÁVEL" if avg < 150 else "DEGRADADA"))
        cor_q = Cor.G if qualidade == "ÓTIMA" else (
            Cor.G if qualidade == "BOA" else (
                Cor.Y if qualidade == "ACEITÁVEL" else Cor.R))
        print(f"\n  Qualidade    : {cor_q}{Cor.BLD}{qualidade}{Cor.RST}")

        log_evento("DIAGNOSTICO", {
            "amostras": AMOSTRAS, "ok": total, "erros": erros, "taxa_pct": taxa,
            "min_ms": round(min(rtts), 2), "max_ms": round(max(rtts), 2),
            "avg_ms": round(avg, 2), "jitter_ms": round(max(rtts) - min(rtts), 2),
        })
    else:
        print(
            f"\n  {
                Cor.R}{
                Cor.BLD}CLP INACESSÍVEL — Nenhuma resposta recebida.{
                Cor.RST}")
        print(f"  Verifique:")
        print(f"    • IP configurado:  {PLC_IP}")
        print(f"    • Porta Modbus:    {PLC_PORT}")
        print(f"    • Sub-rede do adaptador Ethernet")
        print(f"    • Firmware Modbus TCP ativo no CLP Altus")
        log_evento(
            "DIAGNOSTICO_SEM_RESPOSTA", {
                "ip": PLC_IP, "port": PLC_PORT})

    print(f"\n  {Cor.DIM}Log: {LOG_JSONL}{Cor.RST}")
    input(f"\n  {Cor.DIM}[ENTER para voltar]{Cor.RST}")


# ═══════════════════════════════════════════════════════════════════════════
#  TELA: HISTÓRICO DE EVENTOS
# ═══════════════════════════════════════════════════════════════════════════

def tela_historico() -> None:
    header("Histórico de Eventos — Log JSONL")

    if not os.path.exists(LOG_JSONL):
        print(f"\n  {Cor.DIM}Nenhum log encontrado em {LOG_JSONL}{Cor.RST}")
        input(f"\n  {Cor.DIM}[ENTER]{Cor.RST}")
        return

    with open(LOG_JSONL, encoding="utf-8") as fh:
        linhas = fh.readlines()

    ultimas = linhas[-25:]
    print(
        f"\n  {
            Cor.DIM}Exibindo {
            len(ultimas)} de {
                len(linhas)} eventos totais{
                    Cor.RST}\n")
    separador()

    for raw in ultimas:
        try:
            e = json.loads(raw)
            ts = e.pop("ts", "")[-15:-3]   # HH:MM:SS.mmm
            tipo = e.pop("tipo", "?")
            cor = (Cor.G if "OK" in tipo
                   else Cor.R if ("FALHA" in tipo or "ERRO" in tipo or "SEM_RESPOSTA" in tipo)
                   else Cor.C)
            dados_str = "  ".join(f"{k}={v}" for k, v in e.items())
            print(
                f"  {
                    Cor.DIM}{ts}{
                    Cor.RST}  {cor}{
                    tipo:<28}{
                    Cor.RST}  {
                        Cor.DIM}{dados_str}{
                            Cor.RST}")
        except Exception:
            print(f"  {Cor.DIM}{raw.strip()}{Cor.RST}")

    separador()
    print(f"\n  {Cor.DIM}Log completo: {LOG_JSONL}{Cor.RST}")
    print(f"  {Cor.DIM}Debug:        {LOG_DEBUG}{Cor.RST}")
    input(f"\n  {Cor.DIM}[ENTER]{Cor.RST}")


# ═══════════════════════════════════════════════════════════════════════════
#  MENU PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════

def menu_principal(clp: CLPHandler) -> None:
    while True:
        cls()
        ts = datetime.datetime.now().strftime("%d/%m/%Y  %H:%M:%S")
        conn_badge = f"{
            Cor.G}ONLINE{
            Cor.RST}" if clp.online else f"{
            Cor.R}OFFLINE{
                Cor.RST}"

        print(f"{Cor.B}{'═' * 62}{Cor.RST}")
        print(
            f"{
                Cor.C}{
                Cor.BLD}  ALTUS PLC CONSOLE  |  {PLC_IP}:{PLC_PORT}  |  {conn_badge}{
                Cor.RST}")
        print(f"{Cor.DIM}  {ts}   Log: {os.path.basename(LOG_JSONL)}{Cor.RST}")
        print(f"{Cor.B}{'═' * 62}{Cor.RST}")
        print()
        print(f"  [{Cor.C}1{Cor.RST}]  Dashboard de I/O em Tempo Real")
        print(f"  [{Cor.C}2{Cor.RST}]  Comandos Manuais (escrita de coils)")
        print(f"  [{Cor.C}3{Cor.RST}]  Diagnóstico de Conexão (ping Modbus)")
        print(f"  [{Cor.C}4{Cor.RST}]  Histórico de Eventos (log JSONL)")
        print(f"  [{Cor.C}5{Cor.RST}]  Reconectar ao CLP")
        print()
        print(f"  [{Cor.R}0{Cor.RST}]  Sair")
        separador()

        cmd = input(f"\n  {Cor.C}Opção:{Cor.RST} ").strip()

        if cmd == "1":
            tela_dashboard(clp)
        elif cmd == "2":
            tela_comandos(clp)
        elif cmd == "3":
            tela_diagnostico(clp)
        elif cmd == "4":
            tela_historico()
        elif cmd == "5":
            clp.fechar()
            if not clp.conectar():
                print(f"  {Cor.R}Reconexão falhou.{Cor.RST}")
                time.sleep(1.5)
        elif cmd == "0":
            print(f"\n  {Cor.G}Encerrando sessão...{Cor.RST}")
            clp.fechar()
            log_evento("SESSAO_ENCERRADA", {"ip": PLC_IP})
            break
        else:
            print(f"  {Cor.R}Opção inválida.{Cor.RST}")
            time.sleep(0.5)


# ═══════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    cls()
    print(f"\n{Cor.C}{Cor.BLD}{'═' * 62}")
    print(f"  ALTUS PLC CONSOLE TESTER  v2.0")
    print(f"  Protocolo: Modbus TCP/IP  |  IEC 61131-3 ST")
    print(f"{'═' * 62}{Cor.RST}\n")
    print(f"  {Cor.DIM}Target  : {PLC_IP}:{PLC_PORT}")
    print(f"  Log     : {LOG_JSONL}")
    print(f"  Debug   : {LOG_DEBUG}{Cor.RST}\n")

    log_evento("SESSAO_INICIADA", {"ip": PLC_IP, "port": PLC_PORT})

    clp = CLPHandler()

    if clp.conectar(tentativas=3, espera=2.0):
        menu_principal(clp)
    else:
        print(
            f"\n  {
                Cor.R}{
                Cor.BLD}Impossível conectar ao CLP após 3 tentativas.{
                Cor.RST}\n")
        print(f"  {Cor.Y}Checklist:{Cor.RST}")
        print(f"    [ ] IP do adaptador Ethernet na faixa 172.20.10.x /24")
        print(f"    [ ] CLP Altus energizado e rodando")
        print(f"    [ ] Modbus TCP habilitado na configuração do CLP")
        print(f"    [ ] Porta {PLC_PORT} não bloqueada por firewall")
        print(f"    [ ] Cabo físico / switch funcional")
        log_evento("FALHA_CRITICA", {"motivo": "sem_conexao_apos_tentativas"})
        sys.exit(1)
