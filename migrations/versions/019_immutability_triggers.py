import sqlite3

VERSION = "019"
DESCRIPTION = "Triggers de inmutabilidad fiscal para verifactu_invoices y sif_event_log"

def upgrade(conn: sqlite3.Connection):
    cursor = conn.cursor()
    
    # 1. Bloquear borrado de facturas Veri*Factu consolidadas
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_verifactu
    BEFORE DELETE ON verifactu_invoices
    BEGIN
        SELECT RAISE(ABORT, 'Inmutabilidad fiscal: No se permite eliminar facturas consolidadas en Veri*Factu.');
    END;
    """)
    
    # 2. Bloquear actualización de campos fiscales en facturas Veri*Factu
    # Campos que SÍ pueden actualizarse (metadatos): delivery_status, retry_count, etc.
    # Campos que NO pueden actualizarse: id, invoice_number, base_imponible, iva_amount, total_amount, date_of_issue, status
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_prevent_update_verifactu
    BEFORE UPDATE ON verifactu_invoices
    WHEN 
        NEW.id != OLD.id OR 
        NEW.invoice_number != OLD.invoice_number OR
        NEW.base_imponible != OLD.base_imponible OR
        NEW.iva_amount != OLD.iva_amount OR
        NEW.total_amount != OLD.total_amount OR
        NEW.date_of_issue != OLD.date_of_issue
    BEGIN
        SELECT RAISE(ABORT, 'Inmutabilidad fiscal: No se permite alterar importes ni datos clave de facturas ya emitidas.');
    END;
    """)

    # 3. Bloquear borrado de logs del SIF (Sistema Informático de Facturación)
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_sif
    BEFORE DELETE ON sif_event_log
    BEGIN
        SELECT RAISE(ABORT, 'Inmutabilidad fiscal: No se permite eliminar registros de auditoría del SIF.');
    END;
    """)
    
    # 4. Bloquear alteración de cualquier log del SIF
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_prevent_update_sif
    BEFORE UPDATE ON sif_event_log
    BEGIN
        SELECT RAISE(ABORT, 'Inmutabilidad fiscal: Los registros de auditoría del SIF son de solo lectura.');
    END;
    """)

    conn.commit()
