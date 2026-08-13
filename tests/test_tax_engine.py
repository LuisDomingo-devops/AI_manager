import pytest
import os
import json
from pathlib import Path
from app.domain.services.tax_engine import TaxEngine

def test_parse_number():
    assert TaxEngine.parse_number("1.234,56 €") == 1234.56
    assert TaxEngine.parse_number("123,45") == 123.45
    assert TaxEngine.parse_number(" 99 € ") == 99.0
    assert TaxEngine.parse_number("invalid") == 0.0

def test_resolve_dates():
    # ISO date
    date_str, year, quarter = TaxEngine.resolve_dates("La fecha de factura es 2026-08-15")
    assert date_str == "2026-08-15"
    assert year == 2026
    assert quarter == 3

    # Standard date DD/MM/YYYY
    date_str, year, quarter = TaxEngine.resolve_dates("Fecha: 05/12/2025")
    assert date_str == "2025-12-05"
    assert year == 2025
    assert quarter == 4

    # Fallback
    date_str, year, quarter = TaxEngine.resolve_dates("No hay fecha en este texto")
    assert date_str is not None
    assert year is not None
    assert quarter is not None

def test_resolve_rates():
    # Detects from text
    iva, irpf = TaxEngine.resolve_rates("Factura con IVA del 10% e IRPF de -15% de retención")
    assert iva == 10.0
    assert irpf == 15.0

    # Fallbacks to rules
    rules = TaxEngine.load_rules()
    iva, irpf = TaxEngine.resolve_rates("Factura sin mención a tasas")
    assert iva == rules.get("iva_general_rate", 21.0)
    assert irpf == 0.0

def test_extract_financials_and_recalculate():
    # Recalculates from base imponible
    base, iva, irpf, total = TaxEngine.extract_financials("Base imponible: 1000 EUR", "base imponible: 1000 eur", 21.0, 15.0)
    assert base == 1000.0
    assert iva == 210.0
    assert irpf == 150.0
    assert total == 1060.0

    # Recalculates from total
    base, iva, irpf, total = TaxEngine.extract_financials("Total factura: 121 EUR", "total factura: 121 eur", 21.0, 0.0)
    assert base == 100.0
    assert iva == 21.0
    assert irpf == 0.0
    assert total == 121.0

def test_update_tax_rules_workflow():
    rules_path = Path(__file__).resolve().parents[1] / "app" / "domain" / "services" / "tax_rules.json"
    
    # Hacer backup de las reglas actuales
    backup = {}
    if rules_path.exists():
        with open(rules_path, "r", encoding="utf-8") as f:
            backup = json.load(f)

    try:
        # 1. Intentar actualizar sin boe_link o boe_section
        res_fail = TaxEngine.update_tax_rules({"iva_general_rate": 22.0}, boe_link="", boe_section="Art 1")
        assert res_fail["status"] == "error"

        res_fail_section = TaxEngine.update_tax_rules({"iva_general_rate": 22.0}, boe_link="https://boe.es", boe_section="")
        assert res_fail_section["status"] == "error"

        # 2. Intentar actualizar con confirmed_by_user = False (Debe retornar pending_confirmation y no cambiar el archivo)
        res_pending = TaxEngine.update_tax_rules(
            {"iva_general_rate": 23.0},
            boe_link="https://www.boe.es/diario_boe/txt.php?id=BOE-A-2026-12345",
            boe_section="Artículo 2",
            confirmed_by_user=False
        )
        assert res_pending["status"] == "pending_confirmation"
        
        # Verificar que no cambió el archivo
        current = TaxEngine.load_rules()
        assert current.get("iva_general_rate") != 23.0

        # 3. Actualizar con confirmed_by_user = True (Debe aplicar el cambio)
        res_ok = TaxEngine.update_tax_rules(
            {"iva_general_rate": 23.0},
            boe_link="https://www.boe.es/diario_boe/txt.php?id=BOE-A-2026-12345",
            boe_section="Artículo 2",
            confirmed_by_user=True
        )
        assert res_ok["status"] == "ok"
        
        current_updated = TaxEngine.load_rules()
        assert current_updated.get("iva_general_rate") == 23.0
        assert "BOE-A-2026-12345" in current_updated.get("boe_reference")
        assert "Artículo 2" in current_updated.get("boe_reference")

    finally:
        # Restaurar backup
        if backup:
            with open(rules_path, "w", encoding="utf-8") as f:
                json.dump(backup, f, indent=2, ensure_ascii=False)
