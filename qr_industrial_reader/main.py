# main.py
import sys
import logging
import threading
import tkinter as tk
from tkinter import ttk

# Inicia o sistema de logs industriais rotativos PRIMEIRO
from app.core.logger import setup_logger
setup_logger()

# ==============================================================
# OTIMIZAÇÃO PARA CPUS DE BAIXO CUSTO
# Limita o número de núcleos que o ONNX/PyTorch pode sequestrar
# ==============================================================
import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

def iniciar_com_splash():
    # 1. Cria a RAIZ ÚNICA do Tkinter
    root = tk.Tk()
    root.overrideredirect(True) # Remove a barra do Windows
    
    largura, altura = 500, 250
    x = (root.winfo_screenwidth() // 2) - (largura // 2)
    y = (root.winfo_screenheight() // 2) - (altura // 2)
    root.geometry(f"{largura}x{altura}+{x}+{y}")
    root.configure(bg="#2D2D30")
    
    # Cria um Frame temporário para segurar o texto e a barra
    splash_frame = tk.Frame(root, bg="#2D2D30")
    splash_frame.pack(expand=True, fill="both")
    
    tk.Label(splash_frame, text="SCADA POKA-YOKE 4.0", font=("Segoe UI", 24, "bold"), fg="#F5F5F5", bg="#2D2D30").pack(pady=(60, 10))
    lbl_status = tk.Label(splash_frame, text="Carregando Motores de Visão, IA e Modbus...", font=("Segoe UI", 11), fg="#4DA6FF", bg="#2D2D30")
    lbl_status.pack()
    
    style = ttk.Style()
    style.theme_use('default')
    style.configure("Horizontal.TProgressbar", background="#66BB6A", troughcolor="#1E1E1E", bordercolor="#2D2D30", lightcolor="#66BB6A", darkcolor="#66BB6A")
    progress = ttk.Progressbar(splash_frame, style="Horizontal.TProgressbar", mode="indeterminate", length=300)
    progress.pack(pady=20)
    
    # Inicia a animação da barra
    progress.start(15)

    # ==============================================================================
    # 2. CARREGAMENTO PESADO EM BACKGROUND (Usando Thread)
    # ==============================================================================
    def carregar_modulos():
        try:
            logging.info("[SYSTEM] Carregando módulos pesados de IA e Visão Computacional...")
            from app.ui.main_window import MainWindow
            
            # Avisa a Thread Principal (Tkinter) que terminou e manda construir a UI
            root.after(0, finalizar_splash_e_iniciar, MainWindow)
        except Exception as e:
            logging.exception("[ERRO CRITICO] Falha ao carregar dependências:")
            root.after(0, root.destroy) # Fecha o splash em caso de falha fatal

    # ==============================================================================
    # 3. TRANSIÇÃO SUAVE (Roda de volta na Thread Principal)
    # ==============================================================================
    def finalizar_splash_e_iniciar(MainWindowClass):
        progress.stop()         # Para a animação
        splash_frame.destroy()  # Destrói apenas o conteúdo do splash
        
        # Devolve o controle da janela ao Windows
        root.overrideredirect(False)
        
        logging.info("[SYSTEM] Construindo a Interface SCADA...")
        app = MainWindowClass(root=root)
        app.run()

    # Dispara o carregamento em uma Thread separada para não congelar a UI
    threading.Thread(target=carregar_modulos, daemon=True).start()
    
    # Mantém o loop do Tkinter vivo para a barra girar fluidamente
    root.mainloop()

def main():
    logging.info("="*50)
    logging.info("[SYSTEM] Solicitação de Inicialização do SCADA...")
    logging.info("="*50)
    
    try:
        iniciar_com_splash()
    except KeyboardInterrupt:
        logging.info("[SYSTEM] Aplicação encerrada manualmente pelo usuário (Ctrl+C).")
    except Exception as e:
        logging.exception("[ERRO CRITICO FATAL] O sistema encontrou uma falha não tratada:")
    finally:
        logging.info("[SYSTEM] Finalizando aplicação e devolvendo recursos ao SO...")
        sys.exit(0)

if __name__ == "__main__":
    main()