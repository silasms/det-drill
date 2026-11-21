@echo off
title DET Drill Pro - Instalador Windows
echo ==================================================================
echo    DET DRILL PRO - Instalador Automatico para Windows 10 / 11
echo ==================================================================
cd /d "%~dp0"

where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERRO] Python nao encontrado no PATH.
    echo Instale o Python 3.10+ em https://www.python.org/downloads/ marcando "Add Python to PATH".
    pause
    exit /b 1
)

python install.py
pause
