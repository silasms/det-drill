# 🎯 DET Drill Pro — Duolingo English Test Complete Suite (B2/C1)

Suíte completa e multiplataforma (**Linux**, **macOS Apple Silicon M1/M2/M3/M4** e **Windows 10/11**) de treinamento intensivo para o **Duolingo English Test (DET)**, projetada com engenharia pedagógica para atingir e superar a faixa **95–125+ pontos (CEFR B2/C1 — Meta Pós-Graduação/UFRJ)**.

---

## ✨ Principais Recursos

1. **Geração 100% Dinâmica em Lotes via IA (Google Gemini 3.5 Flash-Lite / 3.8 Flash)**:
   * Nada é estático ou decorado. Todos os exercícios são gerados sob medida no nível acadêmico B2/C1 com controle de inéditos (`seen_history.json`) e **Pre-Fetching em segundo plano (`0ms` de latência)**.
2. **Simulador Oficial de Todas as Modalidades do DET**:
   * **`1) Read & Complete (C-Test / Fill in the Blanks)`**: Lacunas matemáticas oficiais, navegação livre (`>` pular, `<` voltar, `?` pista morfológica) e correção local instantânea.
   * **`3) Read & Select`**: Lotes dinâmicos de palavras acadêmicas reais vs. pseudo-palavras convincentes.
   * **`4) Listen & Type`**: Ditado com **voz humana natural** (Google TTS MP3 em cache), **Diff colorido palavra por palavra**, pontuação parcial oficial e ciclo de **Fixação Ativa (Memória Motora)**.
   * **`5) Interactive Writing (5 min + 3 min Follow-up)`**: Etapa 1 (5 min) seguida da Etapa 2 oficial de *Interactive Follow-up* (3 min) gerada sobre o seu argumento.
   * **`6) Interactive Reading (4 Etapas Encadeadas)`**: *Complete the Sentences*, *Complete the Passage*, *Identify the Idea* e *Title the Passage* em uma única sessão.
   * **`7) Vocab & Transitions`**: Questões inéditas de conectivos e vocabulário acadêmico C1.
   * **`8) Speaking Simulator (90s)`**: Suporte aos modos **Read, Then Speak** e **Listen, Then Speak** (pergunta cega apenas em áudio) com gravação real de microfone e avaliação multimodal da sua pronúncia e fluência.
   * **`9) Write About the Photo (60s)`**: Download automático em background de **fotografias documentais reais e inéditas** avaliadas por **Visão Computacional Multimodal** (a IA enxerga a foto real + seu texto).
   * **`L) Interactive Listening + Summarize the Conversation (75s)`**: Diálogo acadêmico falado em 3 turnos + treino do resumo cronometrado de 75 segundos.
3. **Neurociência & Didática Adaptativa**:
   * **IA Adaptativa**: Recicla automaticamente palavras que você errou recentemente dentro dos novos textos e ditados gerados.
   * **Missão de Ativação C1 & Radar Anti-Clichê Local (`0ms`)**: Desafia você a ativar vocabulário C1 na escrita/fala e detecta clichês básicos A2 (*"very important"*, *"I think"*, *"good"*, *"thing"*, *"people"*), sugerindo upgrades C1 imediatos.
4. **Integração Assíncrona com o Anki (`0ms`)**:
   * Todo erro gera automaticamente um flashcard no **Anki** (com áudio nativo `.mp3` anexado) através de uma fila em segundo plano que nunca trava o seu treino.

---

## 📂 Estrutura do Projeto

```text
det-drill-pro/
├── det_drill.py            # Motor principal multiplataforma do simulador DET
├── det_photo_viewer.py     # Visualizador gráfico de fotos com cronômetro de 60s (Tkinter/Pillow)
├── install.py              # Instalador universal multiplataforma (Python)
├── install-linux-mac.sh    # Script de instalação rápida para Linux e macOS (M1/M2/M3/M4)
├── install-windows.bat     # Instalador de duplo-clique para Windows 10/11
├── requirements.txt        # Dependências Python (google-genai, Pillow)
├── data/                   # Acervo inicial de questões, catálogo e fotografias
└── README.md               # Este guia de instalação e uso
```

---

## 🚀 Como Instalar em Cada Sistema Operacional

### 🍎 1. macOS (MacBook Air / Pro — Apple Silicon M1 / M2 / M3 / M4 ou Intel)

1. **Instale o FFmpeg** (usado para gravar o microfone no *Speaking* e reproduzir áudio):
   ```bash
   brew install ffmpeg python-tk
   ```
2. **Execute o instalador na pasta do projeto**:
   ```bash
   chmod +x install-linux-mac.sh
   ./install-linux-mac.sh
   ```
3. **Inicie o simulador de qualquer lugar no Terminal**:
   ```bash
   det-drill
   ```
   > 💡 *No macOS, o programa utiliza automaticamente o player nativo `afplay`, o sintetizador humano `say -v Samantha` como fallback offline, a captura de microfone via `AVFoundation` e a pasta oficial do Anki em `~/Library/Application Support/Anki2/User 1/collection.media`.*

---

### 🐧 2. Linux (Fedora / Ubuntu / Debian / Arch)

1. **Instale os pacotes multimídia e Tkinter do sistema**:
   * **Fedora**:
     ```bash
     sudo dnf install -y python3-tkinter python3-pip ffmpeg espeak-ng
     ```
   * **Ubuntu / Debian**:
     ```bash
     sudo apt update && sudo apt install -y python3-tk python3-pip ffmpeg espeak-ng
     ```
2. **Execute o instalador**:
   ```bash
   chmod +x install-linux-mac.sh
   ./install-linux-mac.sh
   ```
3. **Inicie o simulador**:
   ```bash
   det-drill
   ```

---

### 🪟 3. Windows 10 / 11

1. **Pré-requisitos**:
   * Instale o **Python 3.10+** em [python.org](https://www.python.org/downloads/) (marque a caixa **"Add Python to PATH"** na instalação).
   * Instale o **FFmpeg** via Winget no PowerShell:
     ```powershell
     winget install Gyan.FFmpeg
     ```
2. **Instalação**:
   * Dê dois cliques em **`install-windows.bat`** (ou rode `python install.py` no PowerShell/CMD).
3. **Como rodar**:
   * Dê dois cliques no atalho gerado **`run-det-drill.bat`** dentro da pasta ou digite no terminal:
     ```powershell
     python det_drill.py
     ```

---

## 🔗 Configurando a Chave do Google Gemini e o AnkiConnect

### 1. Chave do Google Gemini AI
* Crie sua chave gratuitamente no [Google AI Studio](https://aistudio.google.com/).
* Você pode colar a chave durante a instalação (`install.py`), definir a variável de ambiente `GEMINI_API_KEY`, ou abrir o `det-drill`, digitar **`S` (Configurações)** e escolher a opção **`3) Google Gemini AI Key`**.

### 2. Integração Automática com o Anki (AnkiConnect)
1. Abra o **Anki** no seu computador.
2. Vá em **Ferramentas (Tools) ➔ Extensões (Add-ons) ➔ Obter Extensões (Get Add-ons)**.
3. Insira o código oficial do **AnkiConnect**:
   ```text
   2055492159
   ```
4. Reinicie o Anki. Mesmo se você treinar com o Anki fechado, o `det-drill` salva todos os cards gerados em um buffer local (`pending_anki_cards.json`) e sincroniza automaticamente assim que o Anki for aberto!
