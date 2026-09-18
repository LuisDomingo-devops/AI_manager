$ErrorActionPreference = "Stop"

Write-Host "Iniciando empaquetado de Alfonso Autónomo con PyInstaller..." -ForegroundColor Cyan

# Asegurar que pyinstaller está instalado
pip install pyinstaller

# Crear carpeta data si no existe (PyInstaller necesita origen)
if (-not (Test-Path "data")) {
    New-Item -ItemType Directory -Path "data" | Out-Null
}

# Generar el ejecutable
Write-Host "Ejecutando PyInstaller..." -ForegroundColor Yellow
pyinstaller --noconfirm --onedir --windowed --add-data "data;data" --hidden-import="uvicorn" --hidden-import="fastapi" --exclude-module "dotenv" app/main.py

Write-Host "¡Empaquetado completado! El ejecutable está en la carpeta 'dist/main'" -ForegroundColor Green
