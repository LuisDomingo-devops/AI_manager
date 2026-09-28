"""
Test de Regresión: Contratos del Arnés de Estrés (Spec 001 - TDD)
Verifica que los escenarios de estrés no silencien fallos con 'return' o 'pass'
y que fallen ruidosamente con AssertionError ante cualquier colapso o degradación.
"""

import pytest

def evaluate_stress_stage(stage_name: str, crashed: bool, crash_exception: Exception | None, error_rate: float, max_latency: float, latency_threshold: float = 3.0):
    """
    Función de validación contractual para fases de estrés.
    Invariante: Si crashed es True, o error_rate > 5%, o latencia > umbral, DEBE lanzar AssertionError.
    """
    if crashed:
        raise AssertionError(f"Colapso en fase de estrés '{stage_name}': {crash_exception}")
    if error_rate > 0.05:
        raise AssertionError(f"Tasa de error inaceptable en fase '{stage_name}': {error_rate * 100:.1f}% > 5%")
    if max_latency > latency_threshold:
        raise AssertionError(f"Degradación de latencia en fase '{stage_name}': {max_latency:.2f}s > {latency_threshold}s")
    return True


def test_stress_harness_fails_on_crashed():
    """Verifica que un colapso en el arnés de estrés lanza AssertionError y no termina silenciosamente."""
    with pytest.raises(AssertionError) as exc_info:
        evaluate_stress_stage(
            stage_name="Carga alta",
            crashed=True,
            crash_exception=RuntimeError("SQLite lock error"),
            error_rate=0.0,
            max_latency=0.5
        )
    assert "Colapso en fase de estrés 'Carga alta'" in str(exc_info.value)
    assert "SQLite lock error" in str(exc_info.value)


def test_stress_harness_fails_on_excessive_error_rate():
    """Verifica que una tasa de error > 5% falla ruidosamente."""
    with pytest.raises(AssertionError) as exc_info:
        evaluate_stress_stage(
            stage_name="Carga media",
            crashed=False,
            crash_exception=None,
            error_rate=0.10,
            max_latency=1.2
        )
    assert "Tasa de error inaceptable" in str(exc_info.value)


def test_stress_harness_fails_on_latency_degradation():
    """Verifica que latencias superiores al umbral rompen la prueba."""
    with pytest.raises(AssertionError) as exc_info:
        evaluate_stress_stage(
            stage_name="Carga extrema",
            crashed=False,
            crash_exception=None,
            error_rate=0.0,
            max_latency=4.2,
            latency_threshold=3.0
        )
    assert "Degradación de latencia" in str(exc_info.value)


def test_stress_harness_passes_on_healthy_execution():
    """Verifica que la ejecución saludable completa sin excepciones."""
    assert evaluate_stress_stage(
        stage_name="Carga normal",
        crashed=False,
        crash_exception=None,
        error_rate=0.0,
        max_latency=0.4,
        latency_threshold=3.0
    ) is True
