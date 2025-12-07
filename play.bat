@echo off
start "RPG Engine" cmd /k "cd /d "%~dp0" && venv\Scripts\activate.bat && python ui.py && pause && exit"
