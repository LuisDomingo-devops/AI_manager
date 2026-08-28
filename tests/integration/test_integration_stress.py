import time
import pytest
import concurrent.futures
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.adapters.memory.memory import _get_connection

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
    except Exception:
        pass

    # Borrar PDFs que hayan sido creados durante esta prueba
    if pdf_dir.exists():
        post_pdfs = set(pdf_dir.glob("Factura_*.pdf"))
        new_pdfs = post_pdfs - pre_existing_pdfs
        for pdf in new_pdfs:
            try:
                pdf.unlink()
            except Exception:
                pass


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
    print(f"\n[SQLite Stress] {success_count} escrituras exitosas de {total_workers} concurrentes.")
    if errors:
        print(f"[SQLite Stress] Primer error detectado: {errors[0]}")
        # En SQLite ordinario sin WAL, concurrencias altas arrojarán "database is locked"
        assert any("locked" in str(err).lower() for err in errors)


def test_api_concurrent_invoice_creation(test_client):
    """
    Prueba de integración de API para comprobar cuántas peticiones concurrentes de creación
    de factura tolera el endpoint /api/v1/billing/invoices/create antes de fallar o degradarse.
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
    
    print(f"\n[API Invoice Stress] Exitosas: {len(successful_calls)}, Fallidas: {len(failed_calls)}")
    if failed_calls:
        print(f"[API Invoice Stress] Ejemplo de fallo: Código {failed_calls[0][0]}, Mensaje: {failed_calls[0][2] if len(failed_calls[0]) > 2 else ''}")
        
    # Asegurar que al menos algunas llamadas logran completarse exitosamente bajo condiciones normales de test
    assert len(successful_calls) > 0


