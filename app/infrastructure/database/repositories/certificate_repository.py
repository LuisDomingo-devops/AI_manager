import sqlite3
import uuid
from typing import Dict, Any, Optional

class CertificateRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        
    def save(self, tenant_id: str, cert_type: str, encrypted_p12: Optional[bytes], encrypted_password: Optional[str], subject_name: str, valid_from: str, valid_to: str) -> str:
        cert_id = str(uuid.uuid4())
        self.conn.execute("""
            INSERT INTO certificates (id, tenant_id, cert_type, encrypted_p12, encrypted_password, subject_name, valid_from, valid_to)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (cert_id, tenant_id, cert_type, encrypted_p12, encrypted_password, subject_name, valid_from, valid_to))
        self.conn.commit()
        return cert_id
        
    def get_by_tenant(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM certificates WHERE tenant_id = ? ORDER BY created_at DESC LIMIT 1", (tenant_id,))
        row = cursor.fetchone()
        if not row:
            return None
        columns = [col[0] for col in cursor.description]
        return dict(zip(columns, row))
