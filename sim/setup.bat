@echo off
REM Installation sans Docker (Windows). Python 3.10 a 3.12 recommande.
cd /d "%~dp0"
python -m venv .venv
if errorlevel 1 (echo Python introuvable ou erreur venv & exit /b 1)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (echo Erreur d'installation & exit /b 1)
echo.
echo Installation terminee. Lancez : run.bat --zone "Agdal, Rabat, Maroc"