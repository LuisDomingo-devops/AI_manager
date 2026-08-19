"""
TEST RUNNER PILOTO EN VIVO CONTRA EL SANDBOX OFICIAL DE LA AEAT (VERI*FACTU)
Endpoint: https://prewww10.aeat.es/wlpl/PORT-SSII/ws/fe/RegFactuSistemaFacturacionSOAP
Certificado: FNMT eIDAS de Pruebas (data/certificados_prueba/certificado_pruebas.pem)
NIF Emisor: 99999972C (EIDAS CERTIFICADO PRUEBAS)
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime

# Asegurar que el directorio raíz está en el path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Configurar variables de entorno con el certificado de prueba de la FNMT
CERT_PATH = PROJECT_ROOT / "data" / "certificados_prueba" / "certificado_pruebas.pem"
KEY_PATH = PROJECT_ROOT / "data" / "certificados_prueba" / "clave_pruebas.pem"

os.environ["ALFONSO_AEAT_CERT"] = str(CERT_PATH)
os.environ["ALFONSO_AEAT_KEY"] = str(KEY_PATH)
os.environ["ALFONSO_SIF_PRODUCER_NIF"] = "99999972C"

from app.domain.services.verifactu_service import VerifactuService
from app.domain.services.fiscal_validator import validate_invoice_for_sif
from app.adapters.memory.memory import _get_connection


def print_banner(title: str):
    print("\n" + "=" * 75)
    print(f"  {title}")
    print("=" * 75)


def run_live_tests():
    print_banner("INICIANDO BATERÍA DE PRUEBAS EN VIVO CONTRA LA AEAT (SANDBOX)")
    print(f"[*] Certificado mTLS: {CERT_PATH}")
    print(f"[*] Clave Privada:   {KEY_PATH}")
    print(f"[*] NIF Emisor:      99999972C (EIDAS CERTIFICADO PRUEBAS)")
    print(f"[*] Endpoint AEAT:   https://prewww1.aeat.es/wlpl/TIKE-CONT/ws/SistemaFacturacion/VerifactuSOAP")

    # Inicializar base de datos
    VerifactuService.init_verifactu_schema()

    timestamp = int(time.time())
    inv_num_1 = f"LIVE-F26-{timestamp % 10000:04d}"
    today_str = datetime.now().strftime("%d-%m-%Y")

    # =========================================================================
    # PRUEBA 1: FACTURA ORDINARIA F1 (RegistroFacturacionAlta)
    # =========================================================================
    print_banner(f"PRUEBA 1: Registro de Factura Ordinaria F1 ({inv_num_1})")

    invoice_1 = {
        "invoice_number": inv_num_1,
        "date_of_issue": today_str,
        "issuer_nif": "99999972C",
        "receiver_nif": "12345678Z",
        "receiver_name": "CLIENTE DE PRUEBAS S.L.",
        "base_imponible": 150.00,
        "iva_amount": 31.50,
        "total_amount": 181.50,
        "iva_rate": 21.0,
        "tipo_factura": "F1"
    }

    # 1. Validación Fiscal Determinista previa
    val_res = validate_invoice_for_sif(invoice_1)
    print(f"[*] 1. Validador Determinista: {'CONFORME' if val_res.is_valid else 'FALLIDO'}")
    if not val_res.is_valid:
        print(f"    [!] Errores: {val_res.errors}")
        return

    # 2. Registro, Firma XMLDSig y Envío mTLS
    print(f"[*] 2. Calculando huella SHA-256, firmando XMLDSig y conectando con la AEAT...")
    res_1 = VerifactuService.register_invoice(invoice_1)

    print("\n" + "-" * 50)
    print(f"  RESULTADO ENTREGA AEAT - FACTURA {inv_num_1}")
    print("-" * 50)
    print(f"  Estado Local:          {res_1.get('status')}")
    print(f"  Estado Entrega SIF:    {res_1.get('delivery_status')}")
    print(f"  CSV Oficial AEAT:      {res_1.get('csv') or 'No asignado / Pendiente de apertura del servicio'}")
    print(f"  Huella Criptográfica:  {res_1.get('current_hash')}")
    print(f"  Huella Anterior:       {res_1.get('prev_hash') or 'Primera factura de la serie'}")
    
    aeat_raw = res_1.get("aeat_delivery", {})
    print(f"  Código HTTP AEAT:      {aeat_raw.get('http_code') or aeat_raw.get('code')}")
    print(f"  Estado Registro SOAP:  {aeat_raw.get('estado_registro') or aeat_raw.get('estado_envio')}")
    if aeat_raw.get("error_code") or aeat_raw.get("error_desc"):
        print(f"  Aviso / Error AEAT:    [{aeat_raw.get('error_code')}] {aeat_raw.get('error_desc')}")
    print(f"  Mensaje:               {aeat_raw.get('message')}")

    # =========================================================================
    # PRUEBA 2: FACTURA RECTIFICATIVA R1 (Por Diferencias)
    # =========================================================================
    inv_num_rect = f"LIVE-R26-{timestamp % 10000:04d}"
    print_banner(f"PRUEBA 2: Registro de Factura Rectificativa R1 ({inv_num_rect})")

    invoice_rect = {
        "invoice_number": inv_num_rect,
        "date_of_issue": today_str,
        "issuer_nif": "99999972C",
        "receiver_nif": "12345678Z",
        "receiver_name": "CLIENTE DE PRUEBAS S.L.",
        "base_imponible": -50.00,
        "iva_amount": -10.50,
        "total_amount": -60.50,
        "iva_rate": 21.0,
        "tipo_factura": "R1",
        "tipo_rectificativa": "I",
        "rectified_invoice_number": inv_num_1,
        "rectified_invoice_date": today_str
    }

    print(f"[*] 1. Validando rectificativa contra factura origen {inv_num_1}...")
    val_rect = validate_invoice_for_sif(invoice_rect)
    print(f"[*]    Validador Determinista: {'CONFORME' if val_rect.is_valid else 'FALLIDO'}")

    print(f"[*] 2. Calculando huella encadenada con {inv_num_1} y enviando a AEAT...")
    res_rect = VerifactuService.register_invoice(invoice_rect)

    print("\n" + "-" * 50)
    print(f"  RESULTADO ENTREGA AEAT - RECTIFICATIVA {inv_num_rect}")
    print("-" * 50)
    print(f"  Estado Entrega SIF:    {res_rect.get('delivery_status')}")
    print(f"  CSV Oficial AEAT:      {res_rect.get('csv') or 'No asignado'}")
    print(f"  Huella Criptográfica:  {res_rect.get('current_hash')}")
    print(f"  Huella Anterior:       {res_rect.get('prev_hash')}")
    print(f"  ¿Encadenó con P1?:     {'SÍ (Correcto)' if res_rect.get('prev_hash') == res_1.get('current_hash') else 'NO'}")

    # =========================================================================
    # PRUEBA 3: ANULACIÓN DE FACTURA (RegistroFacturacionAnulacion)
    # =========================================================================
    print_banner(f"PRUEBA 3: Anulación Reglamentaria de Factura ({inv_num_rect})")

    print(f"[*] Anulando factura {inv_num_rect} en la cadena criptográfica...")
    res_anul = VerifactuService.cancel_invoice(inv_num_rect)

    print("\n" + "-" * 50)
    print(f"  RESULTADO ANULACIÓN AEAT - FACTURA {inv_num_rect}")
    print("-" * 50)
    print(f"  Estado Entrega SIF:    {res_anul.get('delivery_status')}")
    print(f"  CSV Oficial AEAT:      {res_anul.get('csv') or 'No asignado'}")
    print(f"  Huella de Anulación:   {res_anul.get('current_hash')}")
    print(f"  Huella Anterior:       {res_anul.get('prev_hash')}")

    # =========================================================================
    # PRUEBA 4: AUDITORÍA Y VERIFICACIÓN DE INTEGRIDAD DE LA CADENA
    # =========================================================================
    print_banner("PRUEBA 4: Verificación Integral de la Cadena SHA-256")
    audit = VerifactuService.verify_chain_integrity()
    print(f"[*] Estado de la Cadena:   {audit.get('status').upper()}")
    print(f"[*] Facturas Auditadas:    {audit.get('total_invoices')}")
    print(f"[*] Integridad Garantizada: {'100% CONFORME (Sin manipulaciones)' if audit.get('status') == 'valid' else 'CORRUPCIÓN DETECTADA'}")

    print_banner("BATERÍA DE PRUEBAS COMPLETADA")


if __name__ == "__main__":
    run_live_tests()
