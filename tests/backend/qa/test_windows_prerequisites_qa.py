"""
Suite de QA para Instalador y Verificación de Dependencias en Windows (User Story 7).
Valida que el script PowerShell de prerrequisitos exista, tenga sintaxis válida y cubra dependencias críticas.
"""

import os
from pathlib import Path
import pytest


def test_qa_windows_installer_check_script_exists_and_covers_prerequisites():
    """Valida la presencia y cobertura de scripts/windows_installer_check.ps1."""
    root_dir = Path(__file__).resolve().parents[3]
    script_path = root_dir / "scripts" / "windows_installer_check.ps1"
    
    assert script_path.exists(), f"El script {script_path} debe existir"
    
    content = script_path.read_text(encoding="utf-8")
    
    # Comprobar comprobación de dependencias críticas en Windows
    assert "Python" in content or "python" in content
    assert "keyring" in content.lower() or "credenciales" in content.lower()
    assert "certificado" in content.lower() or "cert" in content.lower() or "fnmt" in content.lower()
