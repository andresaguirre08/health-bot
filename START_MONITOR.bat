@echo off
REM Script para iniciar el monitor de auto-commit en Windows
REM Coloca este archivo en la raíz del proyecto para facilitar su uso

cd /d "%~dp0"
python watch_and_commit.py
pause
