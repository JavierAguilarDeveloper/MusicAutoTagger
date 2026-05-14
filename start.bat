@echo off
cd /d "%~dp0"

echo.
echo  Music Auto Tagger
echo ================================

:: Verificar que Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no encontrado. Instalalo desde https://python.org
    pause
    exit /b 1
)

:: Crear entorno virtual si no existe
if not exist ".venv" (
    echo Creando entorno virtual...
    python -m venv .venv
)

:: Activar entorno virtual
call .venv\Scripts\activate.bat

:: Instalar dependencias
echo Instalando dependencias...
pip install -q -r requirements.txt

echo.
echo  Abre tu navegador en: http://localhost:8000
echo  Presiona Ctrl+C para detener el servidor
echo ================================
echo.

uvicorn main:app --host 0.0.0.0 --port 8000

pause
