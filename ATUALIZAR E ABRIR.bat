@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo ==========================================
echo   PAINEL DE FECHAMENTO CONTABIL - LaraFy
echo ==========================================
echo.
echo [1/3] Baixando do Acessorias (leva uns 15 minutos)...
py coletar.py
if errorlevel 1 goto erro
echo.
echo [2/3] Calculando os indicadores...
py processar.py
if errorlevel 1 goto erro
echo.
echo [3/3] Abrindo o painel...
py servir.py
goto fim
:erro
echo.
echo *** Algo falhou. Leia a mensagem acima. ***
pause
:fim
