#!/usr/bin/env bash
set -e

echo "=================================================================="
echo "   DET DRILL PRO - Instalador Rápido (Linux & macOS M1/M2/M3/M4)"
echo "=================================================================="

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Erro: python3 não encontrado. Instale o Python 3.9+ primeiro."
    exit 1
fi

# No macOS, sugere instalar ffmpeg via Homebrew caso não esteja presente
if [[ "$OSTYPE" == "darwin"* ]]; then
    if ! command -v ffmpeg >/dev/null 2>&1; then
        echo "[macOS] Dica: para gravação de voz no Speaking, instale o ffmpeg com: brew install ffmpeg"
    fi
    export PATH="$HOME/.local/bin:$PATH"
    if ! grep -q '.local/bin' "$HOME/.zshrc" 2>/dev/null; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc"
        echo "✓ ~/.local/bin adicionado ao seu ~/.zshrc"
    fi
fi

python3 install.py
