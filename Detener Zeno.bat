@echo off
rem Apaga la API y la pagina web de Zeno Investments.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\detener.ps1"
