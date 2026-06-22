# Poka-Yoke Industrial Híbrido (SCADA + Visão Computacional) 🏭👁️

Este é um Sistema SCADA corporativo focado no conceito **Poka-Yoke (Prevenção de Erros)** em linhas de montagem industriais. O sistema utiliza Visão Computacional Avançada para escanear kits de peças em movimento, validando-as matematicamente através de Códigos QR e Data Matrix.

A solução atua como um supervisor **Edge Computing** enviando pacotes em tempo real para Controladores Lógicos Programáveis (CLP) via **Modbus TCP/IP**, controlando a automação da esteira de montagem sem atrasos.

## 🌟 Funcionalidades Principais
* **Arquitetura Assíncrona Multi-Thread:** Leitura simultânea de Múltiplas Câmeras (RTSP e HTTP/MJPEG) rodando em background sem travar a renderização da interface HMI.
* **Inteligência de Pós-Processamento:** Integração de ampliação via **Interpolação Cúbica (Super Resolução)** para garantir leituras precisas de QR Codes microscópicos a uma distância de até 1.5 metros na linha.
* **Malha Fechada (CLP Modbus TCP):** Manipulação direta de Bobinas (Coils) industriais, travando a linha se houver a introdução de uma "Peça Intrusa" e ligando a esteira ao validar o lote (Master Data Matrix).
* **Deep Dark Mode Industrial UI:** Uma interface feita em puro Python (Tkinter) usando o conceito de painéis industriais de sala de controle, proporcionando baixo uso de RAM (sem o peso dos navegadores web).

## 🚀 Instalação e Execução

### 1. Clonar o Repositório
```bash
git clone https://github.com/SEU-USUARIO/qr_industrial_reader.git
cd qr_industrial_reader
```

### 2. Criar Ambiente Virtual e Instalar Dependências
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configurar as Variáveis (IPs e Conexões)
Faça uma cópia do ficheiro de configuração padrão e coloque os endereços das suas Câmeras IP e do seu CLP.
```bash
copy .env.example .env
```
*(Edite o ficheiro `.env` com um editor de texto)*

### 4. Executar o SCADA
```bash
python main.py
```

## 🛠️ Tecnologias Utilizadas
- **Python 3.10+** (Núcleo)
- **OpenCV & PyZbar / PyLibDMTX** (Visão Computacional e Decodificadores)
- **PyModbusTCP** (Mestre Modbus Integrado)
- **Tkinter** (Interface UI Nativa)
- **SQLite3** (Motor de Banco de Dados Local para Rastreabilidade)
- **YOLOv8** (Disponível, mas desativável via `.env` para hardware ultraleve)

## 🌿 Versões e Distribuição
- **QR Industrial Reader (Produção)**: Software proprietário completo, exigindo licenciamento comercial ativo.
- **Demo (PYTHON-TESTE)**: Se você deseja apenas testar a funcionalidade de Visão Computacional, utilize a pasta/versão `PYTHON-TESTE`, que é distribuída gratuitamente para fins de avaliação e desenvolvimento.

## 📄 Licença e Uso Comercial
O **QR Industrial Reader** é um software proprietário fechado. O uso deste sistema requer o pagamento de uma **Assinatura Mensal** (Licença Comercial). 
A distribuição, cópia, ou modificação deste código fonte sem autorização expressa é estritamente proibida.

Veja o ficheiro [LICENSE](LICENSE) para os termos completos de uso.
