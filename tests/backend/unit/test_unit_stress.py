import time
import random
import pytest
from typing import Dict, Any, List

# --- UTILIDADES DE ESTRÉS BAJO PRUEBA (IMPLEMENTACIÓN EN EL PROPIO TEST PARA UNIDAD) ---

class StressPerformanceMonitor:
    """Monitorea el rendimiento del sistema durante las pruebas de estrés."""
    def __init__(self, latency_threshold_seconds: float = 5.0):
        self.latency_threshold = latency_threshold_seconds
        self.latencies: List[float] = []
        self.errors_count = 0
        self.success_count = 0

    def record_request(self, elapsed_time: float, status_code: int):
        self.latencies.append(elapsed_time)
        if status_code >= 400:
            self.errors_count += 1
        else:
            self.success_count += 1

    @property
    def avg_latency(self) -> float:
        if not self.latencies:
            return 0.0
        return sum(self.latencies) / len(self.latencies)

    @property
    def max_latency(self) -> float:
        if not self.latencies:
            return 0.0
        return max(self.latencies)

    @property
    def error_rate(self) -> float:
        total = self.success_count + self.errors_count
        if total == 0:
            return 0.0
        return self.errors_count / total

    def is_broken(self) -> bool:
        """Determina si Alfonso se ha 'roto' debido a la latencia o errores."""
        if self.error_rate > 0.05:  # Más del 5% de errores
            return True
        if self.max_latency > self.latency_threshold:  # Latencia máxima superior al umbral
            return True
        return False


class StressDataGenerator:
    """Genera datos simulados y variados para consultas y facturas."""
    
    @staticmethod
    def generate_random_invoice(index: int) -> Dict[str, Any]:
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        nif_letter = random.choice(letters)
        client_nif = f"{random.randint(10000000, 99999999)}{nif_letter}"
        
        return {
            "client_name": f"Cliente Stress Test {index}",
            "client_nif": client_nif,
            "amount": round(random.uniform(10.0, 10000.0), 2),
            "concept": f"Servicios de consultoria de estres y pruebas de carga numero {index}",
            "iva_rate": 21.0,
            "irpf_rate": 0.0,
            "confirmed_by_user": True
        }

    @staticmethod
    def generate_random_query(index: int) -> str:
        queries = [
            f"Hola Alfonso, listame las ultimas facturas del ejercicio {index}",
            f"Calcula los impuestos devengados del trimestre {index % 4 + 1}",
            f"Crea un informe rapido de perdidas y ganancias para el ano {2020 + index % 10}",
            f"Muestrame el estado contable de mi empresa para el cliente numero {index}",
            f"Genera una consulta sobre el estado fiscal del periodo de prueba {index}"
        ]
        return random.choice(queries)


# --- PRUEBAS UNITARIAS ---

def test_performance_monitor_initial_state():
    monitor = StressPerformanceMonitor()
    assert monitor.avg_latency == 0.0
    assert monitor.max_latency == 0.0
    assert monitor.error_rate == 0.0
    assert not monitor.is_broken()


def test_performance_monitor_recording():
    monitor = StressPerformanceMonitor(latency_threshold_seconds=2.0)
    
    # Simular peticiones exitosas rápidas
    monitor.record_request(0.1, 200)
    monitor.record_request(0.2, 201)
    monitor.record_request(0.15, 200)
    
    assert monitor.success_count == 3
    assert monitor.errors_count == 0
    assert monitor.avg_latency == pytest.approx(0.15)
    assert monitor.max_latency == 0.2
    assert monitor.error_rate == 0.0
    assert not monitor.is_broken()


def test_performance_monitor_breaks_on_errors():
    monitor = StressPerformanceMonitor(latency_threshold_seconds=5.0)
    
    # 19 peticiones exitosas, 2 peticiones fallidas (más del 5% de error)
    for _ in range(19):
        monitor.record_request(0.1, 200)
    monitor.record_request(0.1, 500)
    monitor.record_request(0.15, 400)
    
    assert monitor.error_rate > 0.05
    assert monitor.is_broken()


def test_performance_monitor_breaks_on_latency():
    monitor = StressPerformanceMonitor(latency_threshold_seconds=1.5)
    
    monitor.record_request(0.5, 200)
    monitor.record_request(1.8, 200)  # Pasa el umbral de 1.5s
    
    assert monitor.max_latency == 1.8
    assert monitor.error_rate == 0.0
    assert monitor.is_broken()


def test_stress_data_generator_invoice():
    invoice = StressDataGenerator.generate_random_invoice(42)
    assert invoice["client_name"] == "Cliente Stress Test 42"
    assert len(invoice["client_nif"]) == 9
    assert invoice["client_nif"][:-1].isdigit()
    assert invoice["client_nif"][-1].isalpha()
    assert 10.0 <= invoice["amount"] <= 10000.0
    assert "42" in invoice["concept"]
    assert invoice["confirmed_by_user"] is True


def test_stress_data_generator_query():
    query = StressDataGenerator.generate_random_query(99)
    assert isinstance(query, str)
    assert len(query) > 10
    # Al menos uno de los patrones esperados con "99" (trimestre, año o index) debe estar
    assert any(str(x) in query for x in [99, 99 % 4 + 1, 2020 + 99 % 10])
