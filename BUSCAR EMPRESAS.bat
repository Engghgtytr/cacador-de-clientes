@echo off
rem Atualiza a lista de barbearias e restaurantes (OpenStreetMap) e confere os sites. Leva alguns minutos.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" cacador.py buscar
".venv\Scripts\python.exe" cacador.py analisar
pause
