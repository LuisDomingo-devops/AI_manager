import os
import sys
import asyncio
from datetime import datetime
from dotenv import load_dotenv

# Ensure the app module can be found
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.domain.services.verifactu_service import VerifactuService
from app.infrastructure.database.memory.memory import tenant_context

def print_banner():
    print("="*60)
    print("=  TEST DE PRODUCCIÓN REAL AEAT VERI*FACTU - ALFONSO  =")
    print("="*60)

async def run_test():
    print_banner()

    # Forzar el entorno a production
    os.environ["ALFONSO_AEAT_ENV"] = "production"
    
    cert_path = os.environ.get("ALFONSO_AEAT_CERT")
    key_path = os.environ.get("ALFONSO_AEAT_KEY")

    if not cert_path or not key_path:
        print("\n[ERROR] Faltan las credenciales.")
        print("Asegúrate de definir las variables de entorno antes de ejecutar:")
        print("  $env:ALFONSO_AEAT_CERT=\"C:\\ruta\\a\\tu_certificado.pem\"")
        print("  $env:ALFONSO_AEAT_KEY=\"C:\\ruta\\a\\tu_clave.key\"")
        sys.exit(1)

    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        print(f"\n[ERROR] No se encuentra el archivo de certificado o la clave en las rutas especificadas.")
        sys.exit(1)

    print(f"\n[*] Certificado detectado: {cert_path}")
    print(f"[*] Entorno destino configurado: PRODUCTION (www1.agenciatributaria.gob.es)")

    # Creamos un payload de prueba inofensivo
    # Utilizamos un NIF emisor inventado y enviamos una factura de 0.00 euros
    # El objetivo es que la AEAT nos autentique con nuestro certificado TLS,
    # pero que el registro sea rechazado por el XML (ej. NIF inválido).
    print("\n[*] Generando payload de prueba inofensivo (Base 0.00, NIF Emisor: 99999999R)...")
    
    test_invoice = {
        "invoice_number": f"TEST-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "date_of_issue": datetime.now().strftime("%d-%m-%Y"),
        "issuer_nif": "99999999R", # NIF inventado
        "receiver_nif": "00000000T",
        "base_imponible": 0.0,
        "iva_amount": 0.0,
        "total_amount": 0.0,
        "iva_rate": 0.0,
        "tipo_factura": "F1"
    }

    print("\n[*] Iniciando conexión SOAP mTLS cualificada con la AEAT...")
    
    # Mockear el tenant temporal para que VerifactuService pueda guardar en base de datos en memoria o saltar
    tenant_context.set("test_tenant")
    
    try:
        res = VerifactuService.register_invoice(test_invoice)
        
        print("\n" + "="*60)
        print("RESULTADO DE LA CONEXIÓN")
        print("="*60)
        
        if res.get("status") == "success" or res.get("delivery_status") == "ACEPTADO":
            print("\n[!] ALERTA EXTRAÑA: La factura de prueba ha sido ACEPTADA.")
            print(f"CSV de la operación: {res.get('csv')}")
            print("Aunque es extraño que acepte un NIF falso, confirma que la comunicación de producción funciona.")
        elif res.get("status") == "rejected":
            print("\n[OK] ÉXITO EN LA PRUEBA DE CONEXIÓN.")
            print("La AEAT ha autenticado correctamente nuestro certificado, ha recibido la factura y la ha procesado.")
            print("Como era de esperar, la ha RECHAZADO por contener datos ficticios/inválidos.")
            print(f"Detalle del rechazo: Error {res.get('error_code')} - {res.get('error_desc')}")
        else:
            print(f"\n[?] RESPUESTA INESPERADA: {res}")
            
    except Exception as e:
        print("\n[ERROR CRÍTICO] Hubo un fallo en la comunicación o ejecución:")
        import traceback
        traceback.print_exc()
        print("\nSi el error es un problema de Handshake SSL (ConnectError, SSLError), el certificado es inválido o no es aceptado por el endpoint de producción.")

if __name__ == "__main__":
    asyncio.run(run_test())
