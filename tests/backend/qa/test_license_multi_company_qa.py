import pytest
import threading
from app.infrastructure.database.tenant_context import (
    tenant_scope,
    get_current_tenant,
    set_current_tenant,
    sanitize_tenant_id,
)
from app.core.license_validator import OfflineLicenseValidator

def test_tenant_id_sanitization_qa():
    assert sanitize_tenant_id("normal_tenant_1") == "normal_tenant_1"
    assert sanitize_tenant_id("../../../etc/passwd") == "etcpasswd"
    assert sanitize_tenant_id("company; DROP TABLE users;--") == "companydroptableusers--"
    assert sanitize_tenant_id("") == "default"
    assert sanitize_tenant_id("   ") == "default"

def test_thread_safety_multi_tenant_concurrency_qa():
    errors = []
    
    def worker(tenant_name: str, iterations: int):
        try:
            for _ in range(iterations):
                with tenant_scope(tenant_name):
                    current = get_current_tenant()
                    if current != tenant_name:
                        errors.append(f"Fuga de contexto: esperado {tenant_name}, obtenido {current}")
        except Exception as e:
            errors.append(str(e))
            
    threads = []
    for i in range(10):
        t_name = f"tenant_{i}"
        t = threading.Thread(target=worker, args=(t_name, 50))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    assert len(errors) == 0, f"Errores en concurrencia multi-tenant: {errors}"

def test_corrupted_license_file_resilience_qa(tmp_path):
    license_file = tmp_path / "corrupted.lic"
    license_file.write_text("ESTO NO ES UN JSON VALIDO {;;;}", encoding="utf-8")
    
    validator = OfflineLicenseValidator(
        license_path=license_file,
    )
    res = validator.validate()
    assert res.is_operational is False
    assert res.status in ("invalid_signature", "missing", "corrupted")
