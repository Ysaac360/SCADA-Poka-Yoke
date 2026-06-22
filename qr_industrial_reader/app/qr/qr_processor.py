# app/qr/qr_processor.py
import time


class QRProcessor:
    def __init__(self, confirm_frames=1):
        self.buffer = {}
        self.CONFIRM_FRAMES = confirm_frames

        # ========================================================
        # MELHORIA DE MEMÓRIA (Empilhamento de Códigos)
        # ========================================================
        # Tempo para esquecer uma leitura rápida/borrada (lixo)
        self.TIMEOUT = 2.0
        # Tempo de retenção anti-spam: ignora leituras repetidas por 3 seg
        self.COOLDOWN = 3.0
        self.last_cleanup = time.time()

    def process(self, data):
        data = data.strip()
        if not data:
            return None

        agora = time.time()

        # OTIMIZAÇÃO: Roda a faxina na memória apenas a cada 1 segundo para
        # poupar CPU
        if agora - self.last_cleanup > 1.0:
            self._cleanup(agora)
            self.last_cleanup = agora

        # Se é a primeira vez que vê o código, adiciona ao buffer
        if data not in self.buffer:
            self.buffer[data] = {
                "count": 0,
                "last_seen": agora,
                "validated": False}

        item = self.buffer[data]
        item["last_seen"] = agora

        # ANTI-SPAM RESOLVIDO:
        # Se já foi validado, avisa a UI para pintar de verde (novo: False),
        # mas não atinge o banco de dados de novo.
        if item["validated"]:
            return {"data": data, "novo": False}

        item["count"] += 1

        # Confirmação do código (Atingiu a cota de frames necessários)
        if item["count"] >= self.CONFIRM_FRAMES:
            item["validated"] = True
            return {"data": data, "novo": True}

        # Se está sendo lido, mas ainda não atingiu o CONFIRM_FRAMES (evita
        # falsos positivos)
        return {"data": data, "novo": False, "pendente": True}

    def _cleanup(self, agora):
        chaves_para_remover = []

        for k, v in self.buffer.items():
            # Usa o COOLDOWN (3s) se for uma peça validada, ou TIMEOUT (2s) se
            # for leitura falsa
            tempo_limite = self.COOLDOWN if v["validated"] else self.TIMEOUT
            if (agora - v["last_seen"]) > tempo_limite:
                chaves_para_remover.append(k)

        for k in chaves_para_remover:
            del self.buffer[k]
