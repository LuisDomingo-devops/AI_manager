import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from app.utils.encryption import encryptor
from app.infrastructure.database.connection_manager import _get_connection
from app.infrastructure.database.repositories.certificate_repository import CertificateRepository

def load_certificates():
    cert_path = Path("data/certificados_prueba/certificado_pruebas.pem")
    key_path = Path("data/certificados_prueba/clave_pruebas.pem")
    
    if not cert_path.exists() or not key_path.exists():
        print(f"Error: No se encontraron los certificados en {cert_path} o {key_path}")
        sys.exit(1)
        
    cert_data = cert_path.read_text(encoding="utf-8")
    key_data = key_path.read_text(encoding="utf-8")
    
    # In order to store them in 'encrypted_p12', we can just store the PEMs concatenated or something 
    # since we are refactoring app/utils/signature.py to read them.
    # We will just concatenate them for now, or just save key_data and cert_data. Wait, the DB only has `encrypted_p12` and `encrypted_password`.
    # We can store them as JSON or concatenated PEM string in encrypted_p12, and leave password empty.
    
    combined_pem = cert_data + "\n" + key_data
    
    encrypted_payload = encryptor.encrypt(combined_pem)
    
    # We use 'default' tenant
    conn = _get_connection("default")
    repo = CertificateRepository(conn)
    
    # Check if there is an existing one to avoid duplicates
    existing = repo.get_by_tenant("default")
    if existing:
        print("Certificados ya existen para el tenant 'default'.")
        return
        
    cert_id = repo.save(
        tenant_id="default",
        cert_type="AEAT_PRUEBA",
        encrypted_p12=encrypted_payload,
        encrypted_password=None,
        subject_name="Pruebas AEAT",
        valid_from="2023-01-01",
        valid_to="2030-01-01"
    )
    
    print(f"Certificados cargados con ID: {cert_id}")

if __name__ == "__main__":
    load_certificates()
