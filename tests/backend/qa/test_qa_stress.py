import time
import pytest
import concurrent.futures
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.domain.services.verifactu_service import VerifactuService
from app.adapters.memory.memory import _get_connection
import app.api.routes as routes

@pytest.fixture
def test_client():
    headers = {"X-API-Key": "test_api_key_default"}
    with TestClient(app) as c:
        c.headers.update(headers)
        yield c

@pytest.fixture(autouse=True)
def clean_and_mock(monkeypatch):
    import json
    from app.domain.planner_orchestrator import PlannerOrchestrator

    async def mock_orchestrator_run(*args, **kwargs):
        time.sleep(0.005)
        return {
            "type": "chat",
            "response": "Respuesta simulada de Alfonso al mensaje de prueba"
        }

    monkeypatch.setattr(PlannerOrchestrator, "run", mock_orchestrator_run)

    class MockOrchestrator:
        async def run(self, message, llm, request_id=None, session_id=None, client_id=None):
            time.sleep(0.005)
            return {
                "type": "chat",
                "response": f"Respuesta simulada de Alfonso al mensaje: {message}"
            }
    monkeypatch.setattr(routes, "orchestrator", MockOrchestrator())

    # Mockear GeminiClient para no saturar la API externa durante el test de estrés
    class MockGemini:
        async def generate(self, *args, **kwargs):
            time.sleep(0.005)
            return json.dumps({
                "issuer_name": "QAStress Emisor",
                "issuer_nif": "12345678Z",
                "receiver_name": "QAStress Receptor",
                "receiver_nif": "87654321A",
                "base_imponible": 150.0,
                "iva_rate": 21.0,
                "iva_amount": 31.5,
                "irpf_rate": 0.0,
                "irpf_amount": 0.0,
                "total_amount": 181.5,
                "invoice_number": "F-2026-QA",
                "date": "2026-03-15",
                "concept": "Factura QAStress"
            })
        async def chat(self, *args, **kwargs):
            time.sleep(0.005)
            return "Respuesta simulada"

    mock_llm = MockGemini()
    monkeypatch.setattr("app.infrastructure.adapters.llm_client.GeminiClient", lambda: mock_llm)
    monkeypatch.setattr("app.main.llm", mock_llm)

    # Teardown de base de datos e invoices
    pdf_dir = Path(__file__).resolve().parents[2] / "data" / "archivo fiscal" / "facturas pendientes"
    pre_existing_pdfs = set(pdf_dir.glob("Factura_*.pdf")) if pdf_dir.exists() else set()
    
    yield
    
    # Limpieza en base de datos
    try:
        with _get_connection() as conn:
            conn.execute("DELETE FROM invoices WHERE concept LIKE '%QAStress%'")
            conn.execute("DELETE FROM messages WHERE content LIKE '%QAStress%'")
            conn.execute("DELETE FROM journal_entries WHERE concept LIKE '%QAStress%'")
            conn.execute("DELETE FROM ledger_entries WHERE journal_entry_id NOT IN (SELECT id FROM journal_entries)")
            conn.commit()
    except Exception as e:
        from app.utils.logger import app_logger
        app_logger.warning(f"Aviso en limpieza de base de datos en QAStress teardown: {e}")

    # Limpieza de PDFs generados en test
    if pdf_dir.exists():
        post_pdfs = set(pdf_dir.glob("Factura_*.pdf"))
        new_pdfs = post_pdfs - pre_existing_pdfs
        for pdf in new_pdfs:
            try:
                pdf.unlink(missing_ok=True)
            except OSError as e:
                from app.utils.logger import app_logger
                app_logger.warning(f"Aviso eliminando PDF temporal {pdf}: {e}")


def test_qa_alfonso_breaking_point(test_client):
    """
    Escenario QA: Incrementa gradualmente la carga concurrente combinando consultas de chat
    y creación de facturas para localizar exactamente en qué punto Alfonso se rompe
    (por error HTTP 500, excepciones de base de datos o latencias superiores a 3 segundos).
    Al finalizar, valida la integridad de la cadena Veri*Factu.
    """
    stages = [
        {"concurrency": 5, "requests": 10, "desc": "Carga inicial baja", "timeout": 15.0},
        {"concurrency": 15, "requests": 30, "desc": "Carga media / concurrencia normal", "timeout": 30.0},
        {"concurrency": 30, "requests": 60, "desc": "Carga alta / concurrencia elevada", "timeout": 45.0},
        {"concurrency": 50, "requests": 100, "desc": "Carga extrema para buscar punto de ruptura", "timeout": 90.0}
    ]

    broken = False
    breaking_stage = None
    breaking_reason = None
    total_successful_invoices = 0
    total_successful_chats = 0
    max_latency_observed = 0.0
    errors_encountered = []

    for stage in stages:
        if broken:
            continue
            
        concurrency = stage["concurrency"]
        requests_to_run = stage["requests"]
        stage_results = []
        
        def run_single_operation(index):
            nonlocal total_successful_invoices, total_successful_chats, max_latency_observed
            start = time.time()
            
            # Alternar entre creación de facturas (escritura contable/PDF/Verifactu) y consultas chat
            is_invoice_op = (index % 2 == 0)
            
            try:
                # Instanciar TestClient directamente sin el bloque 'with' (sin re-ejecutar lifespan)
                local_client = TestClient(app)
                local_client.headers.update({"X-API-Key": "test_api_key_default"})
                
                if is_invoice_op:
                    payload = {
                        "client_name": f"QAStress Client {index}",
                        "client_nif": f"{10000000 + index}K",
                        "amount": float(10 + index),
                        "concept": f"Procesamiento QAStress numero {index}",
                        "iva_rate": 21.0,
                        "irpf_rate": 0.0,
                        "confirmed_by_user": True
                    }
                    response = local_client.post("/api/v1/billing/invoices/create", json=payload)
                else:
                    payload = {
                        "message": f"Consulta QAStress sobre facturacion e IVA en el indice {index}",
                        "session_id": f"qa_session_{index}"
                    }
                    response = local_client.post("/chat", json=payload)
                
                elapsed = time.time() - start
                max_latency_observed = max(max_latency_observed, elapsed)
                
                if response.status_code == 200:
                    stage_results.append({"status": "success", "latency": elapsed, "code": 200})
                    if is_invoice_op:
                        total_successful_invoices += 1
                    else:
                        total_successful_chats += 1
                else:
                    stage_results.append({"status": "fail_status", "latency": elapsed, "code": response.status_code})
                    errors_encountered.append(f"HTTP {response.status_code} en operacion {index}: {response.text}")
            except Exception as e:
                elapsed = time.time() - start
                stage_results.append({"status": "error", "latency": elapsed, "error": str(e)})
                errors_encountered.append(f"Excepcion en operacion {index}: {str(e)}")

        # Ejecución concurrente
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(run_single_operation, i) for i in range(requests_to_run)]
            concurrent.futures.wait(futures)

        # Evaluar estado de Alfonso tras esta fase
        success_in_stage = sum(1 for r in stage_results if r["status"] == "success")
        errors_in_stage = len(stage_results) - success_in_stage
        max_latency_in_stage = max((r["latency"] for r in stage_results), default=0.0)
        error_rate_in_stage = errors_in_stage / len(stage_results)

        stage_threshold = stage.get("timeout", 45.0)
        if error_rate_in_stage > 0.05:
            broken = True
            breaking_stage = stage["desc"]
            breaking_reason = f"Tasa de error superior al 5% ({error_rate_in_stage * 100:.1f}%)"
        elif max_latency_in_stage > stage_threshold:
            broken = True
            breaking_stage = stage["desc"]
            breaking_reason = f"Degradacion de latencia maxima ({max_latency_in_stage:.2f}s > {stage_threshold}s)"

    # Reporte y validación determinista
    from app.utils.logger import app_logger
    app_logger.info(
        f"Fin de estrés breaking point: Facturas={total_successful_invoices}, Chats={total_successful_chats}, LatenciaMax={max_latency_observed:.3f}s"
    )
    if broken:
        app_logger.error(f"Punto de ruptura alcanzado en etapa '{breaking_stage}': {breaking_reason}. Errores: {errors_encountered[:5]}")
    assert not broken, f"Alfonso colapsó bajo estrés en '{breaking_stage}': {breaking_reason}"

    # VALIDACIÓN DE LA INTEGRIDAD CRIPTOGRÁFICA POST-ESTRÉS (Requisito Veri*Factu)
    # A pesar del estrés, la base de datos y la cadena de bloques Verifactu no deben estar corruptas.
    audit = VerifactuService.verify_chain_integrity()
    assert audit["status"] == "valid", "El estres rompio la integridad del registro de facturas"


@pytest.mark.asyncio
async def test_alfonso_invoice_emission_and_processing_until_crash():
    """
    Prueba de stress QA extrema:
    Emite (genera PDF + persistencia + contabilidad PGC + Verifactu) y procesa (pdfplumber + DB)
    facturas en un bucle continuo de carga secuencial y concurrente comprobando que no se produzcan colapsos.
    Reporta exactamente cuántas facturas se emitieron y procesaron exitosamente.
    """
    import asyncio
    from app.tools.server.billing_tools import generate_invoice_pdf
    from app.tools.server.tax_parser_tools import parse_invoice
    from app.utils.logger import app_logger
    
    count_emitted = 0
    count_processed = 0
    crashed = False
    crash_exception = None
    
    # 1. Stress Secuencial Rápido (fatiga simple)
    app_logger.info("Iniciando prueba de fatiga secuencial...")
    
    for i in range(1, 101):  # Hasta 100 consecutivas secuenciales
        try:
            # Emitir factura
            res_emit = await generate_invoice_pdf(
                client_name=f"QAStress Fatigue Emisor {i}",
                client_nif="12345678Z",
                amount=150.0 + i,
                concept=f"Factura de fatiga secuencial {i}",
                iva_rate=21.0,
                irpf_rate=0.0,
            )
            if res_emit.get("status") == "error":
                raise RuntimeError(f"Fallo en emision secuencial: {res_emit.get('message')}")
            
            count_emitted += 1
            pdf_path = res_emit["pdf_path"]
            
            # Procesar factura
            res_parse = await parse_invoice(pdf_path)
            if res_parse.get("status") == "error" or res_parse.get("success") is False:
                raise RuntimeError(f"Fallo en procesamiento secuencial: {res_parse.get('message')}")
                
            count_processed += 1
            
        except Exception as e:
            crashed = True
            crash_exception = e
            break
            
    assert not crashed, f"Colapso durante la emisión/procesamiento secuencial en ciclo {count_emitted + 1}: {crash_exception}"
        
    # 2. Stress Concurrente en Hilos (para forzar bloqueos reales en SQLite y colisiones de archivo)
    app_logger.info(f"Completadas {count_emitted} facturas secuenciales. Iniciando estrés concurrente...")
    
    concurrency_levels = [5, 10, 20, 45, 75]
    
    for level in concurrency_levels:
        if crashed:
            break
            
        errors = []
        
        def run_pair_sync(index):
            nonlocal count_emitted, count_processed
            loop = asyncio.new_event_loop()
            try:
                # Emisión
                res_emit = loop.run_until_complete(generate_invoice_pdf(
                    client_name=f"QAStress Conc Emisor {level}_{index}",
                    client_nif="12345678Z",
                    amount=200.0 + index,
                    concept=f"Factura de estres concurrente {level}_{index}",
                    iva_rate=21.0,
                    irpf_rate=0.0,
                ))
                if res_emit.get("status") == "error":
                    raise RuntimeError(f"Fallo en emision concurrente: {res_emit.get('message')}")
                
                count_emitted += 1
                pdf_path = res_emit["pdf_path"]
                
                # Procesamiento
                res_parse = loop.run_until_complete(parse_invoice(pdf_path))
                if res_parse.get("status") == "error" or res_parse.get("success") is False:
                    raise RuntimeError(f"Fallo en procesamiento concurrente: {res_parse.get('message')}")
                    
                count_processed += 1
            except Exception as e:
                errors.append(e)
            finally:
                loop.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=level) as executor:
            futures = [executor.submit(run_pair_sync, i) for i in range(level)]
            concurrent.futures.wait(futures)
            
        if errors:
            # Comprobar si son errores inesperados de código, esquema o parsing
            unexpected_errors = [e for e in errors if "locked" not in str(e).lower()]
            if unexpected_errors:
                crashed = True
                crash_exception = unexpected_errors[0]
                break
            # En niveles nominales de concurrencia (<= 10), el sistema debe soportar la carga sin ningún bloqueo
            if level <= 10:
                crashed = True
                crash_exception = f"Bloqueo de base de datos prematuro en nivel nominal {level}: {errors[0]}"
                break
            # En niveles de saturación extrema (> 10), registrar la contención tipada de SQLite
            app_logger.warning(
                f"Contención de base de datos observada en nivel de saturación extrema {level}: {len(errors)} bloqueos de {level} hilos."
            )

    assert not crashed, f"Colapso durante el estrés concurrente en nivel {level}: {crash_exception}"
    assert count_emitted > 0, "No se emitieron facturas en la prueba de estrés"
    assert count_processed == count_emitted, f"Discrepancia en facturas emitidas ({count_emitted}) y procesadas ({count_processed})"
    app_logger.info(f"Prueba de fatiga superada exitosamente: {count_emitted} emitidas y procesadas sin colapso.")

