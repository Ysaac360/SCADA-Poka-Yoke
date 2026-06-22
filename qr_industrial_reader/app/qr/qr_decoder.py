# app/qr/qr_decoder.py
import cv2
import logging
import numpy as np
import pyzbar.pyzbar as pyzbar
from pyzbar.pyzbar import ZBarSymbol

try:
    from pylibdmtx.pylibdmtx import decode as dmtx_decode
except ImportError:
    dmtx_decode = None
    logging.warning(
        "[SISTEMA] Biblioteca 'pylibdmtx' não instalada. Leitura de Data Matrix desativada.")


class QRDecoder:
    def __init__(self):
        # OTIMIZAÇÃO: Definir símbolos na inicialização economiza alocação de
        # memória a cada frame
        self.simbolos = [
            ZBarSymbol.QRCODE, ZBarSymbol.CODE128, ZBarSymbol.CODE39,
            ZBarSymbol.EAN13, ZBarSymbol.EAN8, ZBarSymbol.I25
        ]

    def decode(self, frame, max_codes=5, boxes=None):
        results = []
        seen_data = set()

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        def extrair_zbar(imagem_base, offset_x=0, offset_y=0):
            codes = pyzbar.decode(imagem_base, symbols=self.simbolos)
            for code in codes:
                if len(results) >= max_codes:
                    break
                try:
                    data = code.data.decode("utf-8")
                    if data not in seen_data:
                        seen_data.add(data)
                        x, y, w, h = code.rect
                        x += offset_x
                        y += offset_y
                        bbox = [[[x, y], [x + w, y], [x + w, y + h], [x, y + h]]]
                        results.append({"data": data, "bbox": bbox})
                except Exception as e:
                    logging.error(f"[DECODER] Erro ZBAR: {e}")

        def extrair_dmtx(imagem_base, offset_x=0, offset_y=0):
            if not dmtx_decode or len(results) >= max_codes:
                return
            try:
                vagas = max_codes - len(results)
                dm_codes = dmtx_decode(
                    imagem_base, max_count=vagas, timeout=50)
                img_h, _ = imagem_base.shape
                for code in dm_codes:
                    if len(results) >= max_codes:
                        break
                    data = code.data.decode("utf-8")
                    if data not in seen_data:
                        seen_data.add(data)
                        x, y_inverted, w, h = code.rect.left, code.rect.top, code.rect.width, code.rect.height
                        y_cv = max(0, img_h - y_inverted - h)
                        x += offset_x
                        y_cv += offset_y
                        bbox = [[[x, y_cv], [x + w, y_cv],
                                 [x + w, y_cv + h], [x, y_cv + h]]]
                        results.append({"data": data, "bbox": bbox})
            except Exception as e:
                logging.error(f"[DECODER] Falha critica DMTX: {e}")

        if boxes is not None and len(boxes) > 0:
            kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
            for box in boxes:
                x1, y1, x2, y2 = map(int, box)
                h_img, w_img = gray.shape
                x1, y1 = max(0, x1 - 10), max(0, y1 - 10)
                x2, y2 = min(w_img, x2 + 10), min(h_img, y2 + 10)

                roi = gray[y1:y2, x1:x2]
                if roi.size == 0:
                    continue

                # CORRECAO CRITICA: Aplica nitidez dentro da Bounding Box da
                # YOLO!
                roi_nitida = cv2.filter2D(roi, -1, kernel)

                blurred = cv2.GaussianBlur(roi_nitida, (5, 5), 0)
                _, thresh = cv2.threshold(
                    blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

                # Prioridade ZBAR
                extrair_zbar(thresh, offset_x=x1, offset_y=y1)
                if len(results) < max_codes:
                    extrair_zbar(roi, offset_x=x1, offset_y=y1)
                if len(results) < max_codes:
                    extrair_zbar(roi_nitida, offset_x=x1, offset_y=y1)

                # Tenta Data Matrix
                if len(results) < max_codes:
                    extrair_dmtx(thresh, offset_x=x1, offset_y=y1)
                if len(results) < max_codes:
                    extrair_dmtx(roi, offset_x=x1, offset_y=y1)
        else:
            # SUPER RESOLUÇÃO: Como a IA está desligada, temos CPU livre para dobrar
            # a resolução da imagem, permitindo que o ZBar enxergue QRs
            # minúsculos a 1.5m
            try:
                ampliada = cv2.resize(
                    gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            except Exception:
                ampliada = gray

            # Filtro de nitidez 1.5m na imagem ampliada
            kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
            nitida = cv2.filter2D(ampliada, -1, kernel)

            blurred = cv2.GaussianBlur(nitida, (5, 5), 0)
            _, thresh = cv2.threshold(
                blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # Para manter as coordenadas Bounding Box compatíveis com a imagem
            # original
            def extrair_zbar_ampliado(img_amp):
                codes = pyzbar.decode(img_amp, symbols=self.simbolos)
                for code in codes:
                    if len(results) >= max_codes:
                        break
                    try:
                        data = code.data.decode("utf-8")
                        if data not in seen_data:
                            seen_data.add(data)
                            x, y, w, h = code.rect
                            x, y, w, h = x // 2, y // 2, w // 2, h // 2
                            bbox = [[[x, y], [x + w, y],
                                     [x + w, y + h], [x, y + h]]]
                            results.append({"data": data, "bbox": bbox})
                    except Exception:
                        pass

            def extrair_dmtx_ampliado(img_amp):
                if not dmtx_decode or len(results) >= max_codes:
                    return
                try:
                    vagas = max_codes - len(results)
                    dm_codes = dmtx_decode(
                        img_amp, max_count=vagas, timeout=50)
                    img_h, _ = img_amp.shape
                    for code in dm_codes:
                        if len(results) >= max_codes:
                            break
                        data = code.data.decode("utf-8")
                        if data not in seen_data:
                            seen_data.add(data)
                            x, y_inv, w, h = code.rect.left, code.rect.top, code.rect.width, code.rect.height
                            y_cv = max(0, img_h - y_inv - h)
                            x, y_cv, w, h = x // 2, y_cv // 2, w // 2, h // 2
                            bbox = [[[x, y_cv], [x + w, y_cv],
                                     [x + w, y_cv + h], [x, y_cv + h]]]
                            results.append({"data": data, "bbox": bbox})
                except Exception:
                    pass

            extrair_zbar_ampliado(thresh)
            if len(results) < max_codes:
                extrair_zbar_ampliado(ampliada)
            if len(results) < max_codes:
                extrair_zbar_ampliado(nitida)

            if len(results) < max_codes:
                extrair_dmtx_ampliado(thresh)
            if len(results) < max_codes:
                extrair_dmtx_ampliado(ampliada)

        return results
