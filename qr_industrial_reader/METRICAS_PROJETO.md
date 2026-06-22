# Relatório de Avaliação e Métricas do Projeto (ROI)
**Projeto:** SCADA Poka-Yoke Híbrido (Visão Computacional & IoT)

## 1. Escopo e Tamanho do Projeto
* **Ficheiros Estruturais (Python):** 29
* **Linhas de Código Escritas:** 2.593 linhas de código útil puro (excluindo linhas em branco)
* **Padrões Adotados:** Clean Architecture, Padrão MVC (Model-View-Controller) modificado, Programação Assíncrona, Padrão Produtor-Consumidor.

## 2. Componentes de Alta Complexidade Desenvolvidos
O projeto transcende o conceito de um simples script, abraçando tecnologias da Indústria 4.0:

1. **Visão Computacional Multi-Câmera Assíncrona:** 
   O sistema processa e renderiza múltiplas fontes de vídeo simultâneas (RTSP/HTTP e Câmeras Web) sem bloqueio da Thread principal da Interface (GIL bypass parcial).
2. **Inteligência Artificial (YOLOv8):** 
   O sistema inclui camadas de inferência nativa usando Redes Neurais para detecção de ROI.
3. **Pós-Processamento Avançado (Super Resolução):** 
   Interpoladores Cúbicos em tempo real (`cv2.resize` Inter Cubic) injetados antes da decodificação ZBar para leitura de alta distância, poupando extrema necessidade de processamento local (Edge Computing).
4. **Comunicação Industrial Direta (PyModbusTCP):** 
   Atua como Mestre Modbus, lendo e escrevendo dados em tempo real nas bobinas e memórias de um Controlador Lógico Programável (CLP/PLC) externo.
5. **UI Reativa Dark Mode (SCADA HMI):** 
   Uma Interface Gráfica interativa de alta performance responsiva usando Tkinter nativo (evitando overhead de navegadores web).
6. **Armazenamento e Rastreabilidade:** 
   Base de Dados incorporada localmente usando SQLite, mapeando serial de peças lidas em tabelas com timestamps absolutos, vital para conformidade industrial (Quality Assurance).

## 3. Estimativa de Custo de Desenvolvimento (Avaliação de Mercado)
A criação deste sistema exige a colaboração ou o domínio de múltiplas áreas de engenharia:
- **Engenharia de Software & Interface:** ~40 horas
- **Engenharia de Visão Computacional e IA:** ~30 horas
- **Engenharia de Automação (Integração Modbus/PLC):** ~20 horas
- **Arquitetura, Testes, Bugfixes em Edge Devices:** ~20 horas

**Total Estimado:** ~110 horas de Engenharia Sênior Full-Stack Industrial.
* Num mercado consultivo (taxa horária de ~$100 a $150/h USD), um projeto sob demanda desta escala seria orçado entre **$11.000,00 e $16.500,00**. 

## 4. Retorno de Investimento (ROI) para a Indústria
A implementação de um sistema Poka-Yoke através da Visão Computacional não intrusiva como este permite:
- **Prevenção de Recalls:** Reduz virtualmente a zero as peças misturadas nas caixas de kits, poupando perdas com frete logístico de retorno.
- **Redução de Custo Fixo Operacional:** Diminui a necessidade de "Dupla Checagem" humana e de auditores físicos na ponta da linha.
- **Escalabilidade:** Capaz de rodar em Mini PCs (Edge Devices) de baixo custo na linha de produção, sem depender de nuvens pagas (Cloud APIs).
