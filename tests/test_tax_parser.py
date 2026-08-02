import pytest
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.config import settings
from app.adapters.memory.memory import _get_connection, DB_PATH
from app.domain.services.tax_parser_service import TaxParserService, extract_text_from_file
from app.tools.server.tax_parser_tools import parse_invoice, parse_tax_model, get_quarterly_aggregates


@pytest.fixture(autouse=True)
def clean_db():
    """Limpia la tabla de facturas antes de cada test."""
    with _get_connection() as conn:
        conn.execute("DELETE FROM invoices")
        conn.commit()
    yield


def test_parse_invoice_text_income():
    text = """
    Factura nº: F-2026-001
    Fecha: 15/02/2026
    Emisor: Mi Empresa S.L.
    NIF Emisor: 12345678Z
    Receptor: Cliente Feliz S.A.
    NIF Receptor: B98765432
    Concepto: Servicios de consultoría de IA
    Base Imponible: 1.000,00 €
    IVA 21%: 210,00 €
    Total Factura: 1.210,00 €
    """
    # 12345678Z es el NIF del usuario (settings.ALFONSO_USER_NIF)
    result = TaxParserService.parse_invoice_text(text, user_nif="12345678Z")
    
    assert result["invoice_id"] == "F-2026-001"
    assert result["date"] == "2026-02-15"
    assert result["issuer_nif"] == "12345678Z"
    assert result["receiver_nif"] == "B98765432"
    assert result["base_imponible"] == 1000.0
    assert result["iva_amount"] == 210.0
    assert result["total_amount"] == 1210.0
    assert result["category"] == "income"
    assert result["quarter"] == 1
    assert result["year"] == 2026


def test_parse_invoice_text_expense():
    text = """
    FACTURA RECEPTOR
    Número: FAC-88992
    Fecha de emisión: 2026-05-20
    Proveedor de Internet S.A.U.
    NIF: A55555555
    Cliente: Luis Domingo (Autónomo)
    NIF Cliente: 12345678Z
    Cuota Mensual Fibra Óptica
    Subtotal: 50.00
    IVA (21%): 10.50
    Total: 60.50 €
    """
    result = TaxParserService.parse_invoice_text(text, user_nif="12345678Z")
    
    assert result["invoice_id"] == "FAC-88992"
    assert result["date"] == "2026-05-20"
    assert result["issuer_nif"] == "A55555555"
    assert result["receiver_nif"] == "12345678Z"
    assert result["base_imponible"] == 50.0
    assert result["iva_amount"] == 10.5
    assert result["total_amount"] == 60.5
    assert result["category"] == "expense"
    assert result["quarter"] == 2
    assert result["year"] == 2026


def test_parse_invoice_text_with_irpf():
    text = """
    Factura de Luis Domingo
    NIF: 12345678Z
    Para: Gran Corporacion
    NIF: B44444444
    Fecha: 10/11/2026
    Honorarios: 2.000,00 €
    IVA (21%): 420,00 €
    Retencion IRPF (-15%): -300,00 €
    Total Neto a Recibir: 2.120,00 €
    """
    result = TaxParserService.parse_invoice_text(text, user_nif="12345678Z")
    
    assert result["invoice_id"] == "LUIS DOMINGO" # Heurística primer ID
    assert result["date"] == "2026-11-10"
    assert result["base_imponible"] == 2000.0
    assert result["iva_amount"] == 420.0
    assert result["irpf_amount"] == 300.0
    assert result["total_amount"] == 2120.0
    assert result["category"] == "income"
    assert result["quarter"] == 4
    assert result["year"] == 2026


def test_save_and_aggregates():
    # Insertar algunas facturas manualmente
    inv1 = {
        "invoice_id": "INV-1",
        "date": "2026-01-10",
        "issuer_name": "Luis Domingo",
        "issuer_nif": "12345678Z",
        "receiver_name": "Cliente 1",
        "receiver_nif": "B11111111",
        "base_imponible": 1000.0,
        "iva_rate": 21.0,
        "iva_amount": 210.0,
        "irpf_rate": 0.0,
        "irpf_amount": 0.0,
        "total_amount": 1210.0,
        "category": "income",
        "quarter": 1,
        "year": 2026
    }
    inv2 = {
        "invoice_id": "INV-2",
        "date": "2026-02-15",
        "issuer_name": "Luis Domingo",
        "issuer_nif": "12345678Z",
        "receiver_name": "Cliente 2",
        "receiver_nif": "B22222222",
        "base_imponible": 2000.0,
        "iva_rate": 21.0,
        "iva_amount": 420.0,
        "irpf_rate": 15.0,
        "irpf_amount": 300.0,
        "total_amount": 2120.0,
        "category": "income",
        "quarter": 1,
        "year": 2026
    }
    inv3 = {
        "invoice_id": "INV-3",
        "date": "2026-03-20",
        "issuer_name": "Gasolinera",
        "issuer_nif": "A33333333",
        "receiver_name": "Luis Domingo",
        "receiver_nif": "12345678Z",
        "base_imponible": 100.0,
        "iva_rate": 21.0,
        "iva_amount": 21.0,
        "irpf_rate": 0.0,
        "irpf_amount": 0.0,
        "total_amount": 121.0,
        "category": "expense",
        "quarter": 1,
        "year": 2026
    }
    inv4 = {
        "invoice_id": "INV-4",
        "date": "2026-04-10",
        "issuer_name": "Luis Domingo",
        "issuer_nif": "12345678Z",
        "receiver_name": "Cliente 3",
        "receiver_nif": "B33333333",
        "base_imponible": 500.0,
        "iva_rate": 21.0,
        "iva_amount": 105.0,
        "irpf_rate": 0.0,
        "irpf_amount": 0.0,
        "total_amount": 605.0,
        "category": "income",
        "quarter": 2,
        "year": 2026
    }

    TaxParserService.save_invoice_to_db(inv1)
    TaxParserService.save_invoice_to_db(inv2)
    TaxParserService.save_invoice_to_db(inv3)
    TaxParserService.save_invoice_to_db(inv4)

    aggregates = TaxParserService.get_quarterly_aggregates(year=2026)
    
    # Debería haber Q2 y Q1 ordenados descendente
    assert len(aggregates) == 2
    
    # Q2
    assert aggregates[0]["quarter"] == 2
    assert aggregates[0]["income"]["total"] == 605.0
    assert aggregates[0]["expense"]["total"] == 0.0
    assert aggregates[0]["net_result"] == 605.0
    
    # Q1
    assert aggregates[1]["quarter"] == 1
    # total income Q1 = inv1 (1210) + inv2 (2120) = 3330
    assert aggregates[1]["income"]["total"] == 3330.0
    assert aggregates[1]["expense"]["total"] == 121.0
    assert aggregates[1]["net_result"] == 3209.0


def test_parse_tax_model_303():
    text = """
    MINISTERIO DE HACIENDA - AGENCIA TRIBUTARIA
    MODELO 303 - IMPUESTO SOBRE EL VALOR AÑADIDO
    EJERCICIO: 2026
    PERIODO: 1T (Primer Trimestre)
    Casilla 27: 1500,00
    Casilla 46: 500,00
    Casilla 71: 1000,00
    Resultado de la liquidacion: 1.000,00 €
    """
    result = TaxParserService.parse_tax_model_text(text)
    
    assert result["model"] == "Modelo 303"
    assert result["year"] == 2026
    assert result["quarter"] == 1
    assert result["resultado"] == 1000.0
    assert result["extracted_boxes"][27] == 1500.0
    assert result["extracted_boxes"][46] == 500.0
    assert result["extracted_boxes"][71] == 1000.0


def test_parse_tax_model_130():
    text = """
    AGENCIA TRIBUTARIA - AEAT
    MODELO 130 - IRPF PAGO FRACCIONADO
    AÑO: 2026
    TRIMESTRE: 2T
    [01] Ingresos: 10.000,00
    [02] Gastos deducibles: 4.000,00
    [03] Rendimiento neto: 6.000,00
    [19] Resultado a ingresar: 1.200,00 €
    """
    result = TaxParserService.parse_tax_model_text(text)
    
    assert result["model"] == "Modelo 130"
    assert result["year"] == 2026
    assert result["quarter"] == 2
    assert result["resultado"] == 1200.0
    assert result["extracted_boxes"][1] == 10000.0
    assert result["extracted_boxes"][2] == 4000.0
    assert result["extracted_boxes"][3] == 6000.0
    assert result["extracted_boxes"][19] == 1200.0


def test_extract_text_from_pdf_native_pdfplumber():
    # Simulamos el comportamiento de pdfplumber
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Contenido extraido con pdfplumber"
    
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    
    mock_pdfplumber = MagicMock()
    mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf
    
    with patch.dict("sys.modules", {"pdfplumber": mock_pdfplumber}):
        with patch("pathlib.Path.exists", return_value=True):
            result = extract_text_from_file("factura.pdf")
            assert "Contenido extraido con pdfplumber" in result


def test_extract_text_from_pdf_native_pypdf_fallback():
    # Simulamos fallo de pdfplumber (ImportError) y éxito de pypdf
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Contenido extraido con pypdf"
    
    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]
    
    with patch("pdfplumber.open", side_effect=ImportError):
        with patch("pypdf.PdfReader", return_value=mock_reader):
            with patch("pathlib.Path.exists", return_value=True):
                result = extract_text_from_file("factura.pdf")
                assert "Contenido extraido con pypdf" in result

