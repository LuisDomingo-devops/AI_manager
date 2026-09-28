import time
import pytest
import concurrent.futures
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.adapters.memory.memory import _get_connection
from app.utils.logger import app_logger

@pytest.fixture
def test_client():
    headers = {"X-API-Key": "test_api_key_default"}
    with TestClient(app) as c:
        c.headers.update(headers)
        yield c

@pytest.fixture(autouse=True)
def cleanup_pdfs_and_db():
    # Registrar archivos PDF antes de correr la prueba
    pdf_dir = Path(__file__).resolve().parents[2] / "data" / "archivo fiscal" / "facturas pendientes"
    pre_existing_pdfs = set(pdf_dir.glob("Factura_*.pdf")) if pdf_dir.exists() else set()
    
    yield
    
    # Limpiar base de datos de test
    try:
        with _get_connection() as conn:
            conn.execute("DELETE FROM invoices WHERE client_name LIKE 'StressIntegration%'")
            conn.execute("DELETE FROM journal_entries WHERE concept LIKE '%StressIntegration%'")
            conn.execute("DELETE FROM ledger_entries WHERE journal_entry_id NOT IN (SELECT id FROM journal_entries)")
            conn.commit()
    except Exception as e:
        from app.utils.logger import app_logger
        app_logger.warning(f"Aviso en limpieza de base de datos en StressIntegration teardown: {e}")

    # Borrar PDFs que hayan sido creados durante esta prueba
    if pdf_dir.exists():
        post_pdfs = set(pdf_dir.glob("Factura_*.pdf"))
        new_pdfs = post_pdfs - pre_existing_pdfs
        for pdf in new_pdfs:
            try:
                pdf.unlink(missing_ok=True)
            except OSError as e:
                from app.utils.logger import app_logger
                app_logger.warning(f"Aviso eliminando PDF temporal {pdf}: {e}")


def test_sqlite_concurrent_writes_stress():
    """
    Prueba de integración directa sobre la base de datos SQLite para encontrar el punto
    de saturación o bloqueo por concurrencia de escritura.
    """
    errors = []
    success_count = 0
    total_workers = 15  # Elevada concurrencia para estresar el bloqueo de base de datos
    
    def write_worker(worker_id):
        nonlocal success_count
        try:
            # Intentar abrir conexión e insertar factura directamente
            with _get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO invoices (
                        invoice_id, date, issuer_name, issuer_nif, receiver_name, receiver_nif,
                        base_imponible, iva_rate, iva_amount, total_amount, category, quarter, year, concept
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"INV-STR-INT-{worker_id}", "2026-08-27", "Emisor Stress", "12345678Z",
                        "StressIntegration Client", "87654321A", 100.0, 21.0, 21.0, 121.0,
                        "ingresos", 3, 2026, f"Asiento de stress de integracion {worker_id}"
                    )
                )
                conn.commit()
            success_count += 1
        except Exception as e:
            errors.append(e)

    # Lanzamos en hilos simultáneos
    with concurrent.futures.ThreadPoolExecutor(max_workers=total_workers) as executor:
        futures = [executor.submit(write_worker, i) for i in range(total_workers)]
        concurrent.futures.wait(futures)

    # Reportar resultados
    from app.utils.logger import app_logger
    app_logger.info(f"Concurrencia SQLite: {success_count} exitos, {len(errors)} bloqueos de {total_workers} workers.")
    if errors:
        # En SQLite ordinario sin WAL, concurrencias altas arrojaran "database is locked"
        assert all("locked" in str(err).lower() for err in errors), f"Errores no esperados en concurrencia SQLite: {errors}"
    else:
        assert success_count == total_workers, f"Discrepancia en workers exitosos: {success_count}/{total_workers}"


def test_api_concurrent_invoice_creation(test_client):
    """
    Prueba de integración de API para comprobar que las peticiones concurrentes de creación
    de factura en /api/v1/billing/invoices/create se procesan correctamente sin fallos encubiertos.
    """
    results = []
    total_requests = 10
    
    def post_invoice(request_id):
        payload = {
            "client_name": "StressIntegration Client",
            "client_nif": "12345678Z",
            "amount": 250.0 + request_id,
            "concept": f"Facturacion de prueba de integracion concurrente {request_id}",
            "iva_rate": 21.0,
            "irpf_rate": 0.0,
            "confirmed_by_user": True
        }
        start_time = time.time()
        try:
            # Instanciar TestClient directamente sin el bloque 'with' (sin re-ejecutar lifespan)
            local_client = TestClient(app)
            local_client.headers.update({"X-API-Key": "test_api_key_default"})
            response = local_client.post("/api/v1/billing/invoices/create", json=payload)
            elapsed = time.time() - start_time
            results.append((response.status_code, elapsed, response.text))
        except Exception as e:
            results.append((500, time.time() - start_time, str(e)))

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(post_invoice, i) for i in range(total_requests)]
        concurrent.futures.wait(futures)

    # Validar respuestas obtenidas
    successful_calls = [r for r in results if r[0] == 200]
    failed_calls = [r for r in results if r[0] != 200]
    
    app_logger.info(f"Concurrencia API factura: {len(successful_calls)} exitos, {len(failed_calls)} fallos de {total_requests} peticiones.")
    if failed_calls:
        app_logger.error(f"Detalle de llamadas fallidas en concurrencia: {failed_calls}")
        
    # Validación estricta del 100% de llamadas exitosas
    assert len(failed_calls) == 0, f"Fallaron {len(failed_calls)} llamadas concurrentes: {failed_calls}"
    assert len(successful_calls) == total_requests, f"Se esperaba exito en el 100% de peticiones ({len(successful_calls)}/{total_requests})"



