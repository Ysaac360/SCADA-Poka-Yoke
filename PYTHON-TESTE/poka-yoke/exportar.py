from ultralytics import YOLO

# Carrega o modelo padrão que você já tem
modelo = YOLO("yolov8n.pt")

# Converte e salva na mesma pasta como yolov8n.onnx
print("Exportando para ONNX...")
modelo.export(format="onnx", imgsz=320, dynamic=False)
print("Pronto! Arquivo gerado com sucesso.")