@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Abrindo o painel com os dados da ultima atualizacao...
py servir.py
