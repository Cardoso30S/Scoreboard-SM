"""
Script de build — gera executável standalone com PyInstaller.

Uso:
    pip install pyinstaller
    python build.py
"""

import subprocess
import sys
import shutil
from pathlib import Path

APP_NAME = "Rugby Scoreboard"
MAIN_SCRIPT = "scoreboard.py"

args = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm",          # sobrescreve build anterior sem perguntar
    "--clean",              # limpa cache antes de compilar
    "--onefile",            # tudo em um único arquivo executável
    "--windowed",           # sem janela de terminal (Windows/Mac)
    f"--name={APP_NAME}",
    MAIN_SCRIPT,
]

print("Compilando executável...")
result = subprocess.run(args)

if result.returncode == 0:
    exe_dir = Path("dist")
    files = list(exe_dir.glob("*"))
    print(f"\nSucesso! Executável gerado em: {files[0] if files else exe_dir}")
    print("Você pode distribuir esse arquivo sem precisar instalar nada.")
else:
    print("\nErro ao compilar. Verifique se o PyInstaller está instalado:")
    print("    pip install pyinstaller")
    sys.exit(1)
