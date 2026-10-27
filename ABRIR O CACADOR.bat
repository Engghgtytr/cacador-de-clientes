@echo off
rem Abre o painel do Cacador de clientes no navegador. Deixe esta janela aberta enquanto usa.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" cacador.py painel
pause
