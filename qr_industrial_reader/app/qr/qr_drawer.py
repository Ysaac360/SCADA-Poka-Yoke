# app/qr/qr_drawer.py
import cv2


class QRDrawer:
    def draw(self, frame, qr, is_new=False):
        if "bbox" not in qr or not qr["bbox"]:
            return

        # ==========================================================
        # 1. PALETA SOFT SCADA E ESTILO (Padrão OpenCV é BGR)
        # Amarelo/Âmbar para "Lendo" e Verde Esmeralda para "Validado"
        # ==========================================================
        color = (38, 162, 255) if is_new else (106, 187, 102)
        thickness = 2

        # Extrai os minimos e maximos da Bounding Box forcada
        pts = qr["bbox"][0]
        x_coords = [int(p[0]) for p in pts]
        y_coords = [int(p[1]) for p in pts]

        x, y = min(x_coords), min(y_coords)
        x_max, y_max = max(x_coords), max(y_coords)
        w, h = x_max - x, y_max - y

        h_frame, w_frame = frame.shape[:2]

        # ==========================================================
        # 2. MIRA DE ALTA TECNOLOGIA (Apenas as quinas)
        # Evita poluição visual quando há 5 QR Codes próximos
        # ==========================================================
        line_len = max(5, min(w, h) // 4)  # Tamanho da linha da quina

        # Quina Superior Esquerda
        cv2.line(frame, (x, y), (x + line_len, y),
                 color, thickness, cv2.LINE_AA)
        cv2.line(frame, (x, y), (x, y + line_len),
                 color, thickness, cv2.LINE_AA)
        # Quina Superior Direita
        cv2.line(frame, (x_max, y), (x_max - line_len, y),
                 color, thickness, cv2.LINE_AA)
        cv2.line(frame, (x_max, y), (x_max, y + line_len),
                 color, thickness, cv2.LINE_AA)
        # Quina Inferior Esquerda
        cv2.line(frame, (x, y_max), (x + line_len, y_max),
                 color, thickness, cv2.LINE_AA)
        cv2.line(frame, (x, y_max), (x, y_max - line_len),
                 color, thickness, cv2.LINE_AA)
        # Quina Inferior Direita
        cv2.line(frame, (x_max, y_max), (x_max - line_len, y_max),
                 color, thickness, cv2.LINE_AA)
        cv2.line(frame, (x_max, y_max), (x_max, y_max - line_len),
                 color, thickness, cv2.LINE_AA)

        # ==========================================
        # 3. HUD LIMPO COM ANTI-ALIASING
        # ==========================================
        texto_completo = str(qr.get("data", ""))
        texto_hud = texto_completo[:25] + \
            "..." if len(texto_completo) > 25 else texto_completo

        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.55
        padding = 6

        (tw, th), _ = cv2.getTextSize(texto_hud, font, scale, 1)

        # Proteções contra vazamento de tela
        text_y_base = y if (y - th - padding *
                            2) > 0 else y + th + (padding * 2)
        text_x_base = x
        if text_x_base + tw + (padding * 2) > w_frame:
            text_x_base = max(0, w_frame - tw - (padding * 2))

        # Fundo do texto suave
        cv2.rectangle(
            frame,
            (text_x_base, text_y_base - th - (padding * 2)),
            (text_x_base + tw + (padding * 2), text_y_base),
            color,
            -1,
            cv2.LINE_AA
        )

        # Texto sempre escuro para gerar o melhor contraste com os fundos
        # pastéis
        cv2.putText(
            frame,
            texto_hud,
            (text_x_base + padding, text_y_base - padding),
            font,
            scale,
            (25, 25, 25),  # Quase preto
            1,
            cv2.LINE_AA
        )
