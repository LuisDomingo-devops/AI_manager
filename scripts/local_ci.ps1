$ErrorActionPreference = "Stop"

Write-Host "Iniciando Integración Continua Local (Local-First CI)..." -ForegroundColor Cyan

# 1. Análisis de Seguridad Estático (SAST)
Write-Host "`n[1/2] Ejecutando análisis de seguridad con Bandit..." -ForegroundColor Yellow
bandit -r app/ -ll -ii
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Se encontraron vulnerabilidades de seguridad bloqueantes." -ForegroundColor Red
    exit 1
} else {
    Write-Host "OK: Análisis de seguridad superado." -ForegroundColor Green
}

# 2. Pruebas Unitarias y de Integración
Write-Host "`n[2/2] Ejecutando suite de pruebas automatizadas (pytest)..." -ForegroundColor Yellow
pytest tests/
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Las pruebas han fallado. Revisa los logs." -ForegroundColor Red
    exit 1
} else {
    Write-Host "OK: Todas las pruebas han pasado." -ForegroundColor Green
}

Write-Host "`n¡Éxito! El código es seguro y estable para producción." -ForegroundColor Green
exit 0
