#!/usr/bin/env python3
"""
Instalador Universal Multiplataforma — DET Drill Pro (Linux, macOS Apple Silicon M4 & Windows)
Configura dependências Python, diretórios de dados, acervos iniciais e atalhos de execução.
"""

import os
import sys
import shutil
import stat
import subprocess

IS_MACOS = (sys.platform == "darwin")
IS_WINDOWS = (os.name == "nt" or sys.platform.startswith("win"))
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.expanduser("~/.config/det-drill")
SEED_DATA_DIR = os.path.join(PROJECT_DIR, "data")


def step(msg):
    print(f"\n==> {msg}")


def install_python_deps():
    step("1/4: Instalando pacotes Python (google-genai, Pillow)...")
    req_file = os.path.join(PROJECT_DIR, "requirements.txt")
    cmd = [sys.executable, "-m", "pip", "install", "-r", req_file]
    res = subprocess.run(cmd, check=False)
    if res.returncode != 0 and not IS_WINDOWS:
        # Em sistemas Linux modernos (PEP 668), tentar com --user ou --break-system-packages
        subprocess.run(cmd + ["--user"], check=False)


def sync_seed_data():
    step(f"2/4: Configurando diretório de dados em {DATA_DIR}...")
    os.makedirs(DATA_DIR, exist_ok=True)
    photos_dst = os.path.join(DATA_DIR, "photos")
    os.makedirs(photos_dst, exist_ok=True)

    if os.path.exists(SEED_DATA_DIR):
        for item in os.listdir(SEED_DATA_DIR):
            if item == "gemini_key.txt":
                continue
            src = os.path.join(SEED_DATA_DIR, item)
            dst = os.path.join(DATA_DIR, item)
            if os.path.isdir(src) and item == "photos":
                for p in os.listdir(src):
                    ps = os.path.join(src, p)
                    pd = os.path.join(photos_dst, p)
                    if os.path.isfile(ps) and not os.path.exists(pd):
                        shutil.copy2(ps, pd)
            elif os.path.isfile(src) and not os.path.exists(dst):
                shutil.copy2(src, dst)
    print("✓ Acervo inicial e estruturas de dados prontos.")


def install_executables():
    step("3/4: Instalando executáveis (det-drill & det-photo-viewer)...")
    src_drill = os.path.join(PROJECT_DIR, "det_drill.py")
    src_viewer = os.path.join(PROJECT_DIR, "det_photo_viewer.py")

    if IS_WINDOWS:
        bin_dir = os.path.join(os.path.expanduser("~"), ".local", "bin")
        os.makedirs(bin_dir, exist_ok=True)
        shutil.copy2(src_drill, os.path.join(bin_dir, "det_drill.py"))
        shutil.copy2(src_viewer, os.path.join(bin_dir, "det_photo_viewer.py"))

        bat_wrapper = os.path.join(bin_dir, "det-drill.cmd")
        with open(bat_wrapper, "w", encoding="utf-8") as f:
            f.write(f'@echo off\r\n"{sys.executable}" "{os.path.join(bin_dir, "det_drill.py")}" %*\r\n')

        local_bat = os.path.join(PROJECT_DIR, "run-det-drill.bat")
        with open(local_bat, "w", encoding="utf-8") as f:
            f.write(f'@echo off\r\n"{sys.executable}" "{src_drill}" %*\r\n')
        print(f"✓ Wrapper Windows criado em: {local_bat} e {bat_wrapper}")
    else:
        bin_dir = os.path.expanduser("~/.local/bin")
        os.makedirs(bin_dir, exist_ok=True)
        dst_drill = os.path.join(bin_dir, "det-drill")
        dst_viewer = os.path.join(bin_dir, "det-photo-viewer")

        shutil.copy2(src_drill, dst_drill)
        shutil.copy2(src_viewer, dst_viewer)

        for p in [dst_drill, dst_viewer]:
            st = os.stat(p)
            os.chmod(p, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

        print(f"✓ Executáveis instalados em {bin_dir}/det-drill")
        shell_rc = os.path.expanduser("~/.zshrc" if IS_MACOS else "~/.bashrc")
        print(f"  (Certifique-se de que ~/.local/bin está no seu PATH em {shell_rc})")


def check_gemini_key():
    step("4/4: Verificando chave da API Google Gemini...")
    key_file = os.path.join(DATA_DIR, "gemini_key.txt")
    if os.path.exists(key_file) and os.path.getsize(key_file) > 10:
        print("✓ Chave do Google Gemini já está configurada!")
        return
    try:
        key = input("Cole sua Google Gemini API Key (ou pressione [ENTER] para configurar depois no menu S): ").strip()
        if key:
            with open(key_file, "w", encoding="utf-8") as f:
                f.write(key)
            print("✓ Chave salva com sucesso!")
    except (KeyboardInterrupt, EOFError):
        pass


def main():
    os_name = "macOS (Apple Silicon / Intel)" if IS_MACOS else ("Windows" if IS_WINDOWS else "Linux")
    print("=" * 72)
    print(f"   DET DRILL PRO — INSTALADOR MULTIPLATAFORMA ({os_name})")
    print("=" * 72)
    install_python_deps()
    sync_seed_data()
    install_executables()
    check_gemini_key()
    print("\n" + "=" * 72)
    print("🎉 INSTALAÇÃO CONCLUÍDA COM SUCESSO!")
    if IS_WINDOWS:
        print("Para iniciar agora, execute: python det_drill.py (ou clique em run-det-drill.bat)")
    else:
        print("Para iniciar agora no terminal, digite: det-drill")
    print("=" * 72)


if __name__ == "__main__":
    main()
