@echo off
REM Lance l'extraction puis la verification. Exemple :
REM   run.bat --zone "Agdal, Rabat, Maroc" --half-side 750
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python extract_zone.py %*
if errorlevel 1 exit /b 1
python check_output.py