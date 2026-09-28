"""
Test de Integración: Contrato de Concurrencia y Aserciones Estrictas (Spec 001 - TDD)
Verifica que las escrituras concurrentes evalúan aserciones deterministas y rechazan
placebos tipo 'assert len(successful_calls) > 0' ante fallos masivos.
"""

import pytest

def validate_concurrent_batch_results(total_requests: int, successful_calls: list, failed_calls: list):
    """
    Validador contractual para ejecuciones concurrentes.
    Prohíbe placebos: Si hay fallos no controlados, no se acepta simplemente tener len(successful) > 0.
    """
    assert len(successful_calls) + len(failed_calls) == total_requests, "Discrepancia en el total de llamadas procesadas"
    
    # En una prueba de integración estándar, la tasa de éxito debe ser del 100%
    if failed_calls:
        errores_resumen = [str(f) for f in failed_calls[:3]]
        raise AssertionError(f"Fallo en llamadas concurrentes ({len(failed_calls)}/{total_requests} fallaron): {errores_resumen}")
    
    assert len(successful_calls) == total_requests, "No todas las peticiones concurrentes completaron con éxito"
    return True


def test_rejects_placebo_assertion_when_mostly_failed():
    """Demuestra que 9 fallos de 10 peticiones deben lanzar AssertionError, a pesar de que successful_calls > 0."""
    total = 10
    successful = [{"id": 1, "status": 200}]
    failed = [{"id": i, "status": 500, "error": "Database locked"} for i in range(2, 11)]
    
    with pytest.raises(AssertionError) as exc_info:
        validate_concurrent_batch_results(total, successful, failed)
    assert "Fallo en llamadas concurrentes (9/10 fallaron)" in str(exc_info.value)


def test_accepts_all_successful_concurrent_batch():
    """Valida que una tanda 100% exitosa pasa limpiamente el contrato."""
    total = 5
    successful = [{"id": i, "status": 200} for i in range(1, 6)]
    failed = []
    
    assert validate_concurrent_batch_results(total, successful, failed) is True
