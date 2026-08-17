import os
import json
import base64
import uuid
import platform
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import hashes, serialization

# Clave pública RSA por defecto para validar firmas de licencias de Alfonso Autónomo
# En producción, esto corresponde a la clave privada en posesión de Alfonso S.L.
PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA4vxqcQyYeJuz3wEr1IRZ
QJ70ygRTchcOqNroZYZRSEM0ngBLl8S/J24Vy0Me/j4mjmWJo75NO7UsDXCTll9E
GBDD+PEYoSsIIre1l6RNqI31iBTetaIcbjKiQ9P7ExYWflhPH8N0Xm5ESPktQw7W
Q8NJHdR1/ovUdEC3EC1hjac3HcNtEgcpwc3HZtIds7+QuQTFaHxyMFCpovUnmddY
sEVP8t0jwc9TiXc3BcnCIqJyx3ymvIyEM23wMrl1mpG07PQkn0jO0sY8ThwyXqM0
Oum6lYfIVVrzBeciDHky82Q60xyqpaArkXRu2zqBnXaa0/FHzRAuGUn38NN58W4x
lwIDAQAB
-----END PUBLIC KEY-----"""

LICENSE_PATH = Path(__file__).resolve().parents[2] / "data" / "license.lic"
CLOCK_INTEGRITY_PATH = Path(__file__).resolve().parents[2] / "data" / "clock_integrity.json"
DEFAULT_GRACE_PERIOD_DAYS = 5

# --- MATRIZ DE PERMISOS DE HERRAMIENTAS POR MEMBRESÍA (FEATURE GATING) ---

# Herramientas utilitarias y estándar del asistente IA disponibles en todos los planes
COMMON_ASSISTANT_TOOLS = {
    # Correo y comunicaciones
    "read_emails", "mail_receive_mock_emails", "mail_classify_emails", "mail_get_unread_summary",
    "mail_list_emails", "mail_get_email", "mail_open_ui", "mail_close_ui", "mail_send_email",
    "mail_delete_email", "mail_reply_email", "mail_forward_email", "mail_generate_draft",
    "mail_set_invoice_folder", "send_invoice_email", "send_quote_email",
    # Sistema de archivos
    "create_file", "read_file", "list_directory", "create_directory", "append_file",
    "delete_file", "delete_directory", "move_file", "rename_file", "replace_file_content", "view_file",
    # Calendario y eventos
    "calendar_create_event", "calendar_list_events", "calendar_delete_event",
    "calendar_open_ui", "calendar_close_ui", "calendar_update_event",
    # Memoria y utilidades
    "save_user_preference", "forget_user_fact", "get_user_profile",
    "parse_invoice", "parse_tax_model", "get_quarterly_aggregates", "get_cash_flow_forecast",
    "cancel_invoice", "no_op", "get_current_time", "get_current_datetime"
}

BASIC_ALLOWED_TOOLS = COMMON_ASSISTANT_TOOLS | {
    # Facturación Verifactu y Rectificativas
    "create_invoice", "get_invoices", "list_invoices", "get_invoice", "generate_invoice_pdf",
    "generate_invoice_qr", "create_rectificativa_invoice",
    # Catálogo básico
    "get_clients", "create_client", "update_client", "delete_client",
    "get_products", "create_product", "update_product", "delete_product",
    # Contabilidad básica y modelos fiscales
    "get_libro_diario", "get_balance_situacion", "get_pgc_accounts",
    "get_tax_estimate", "get_fiscal_deadlines", "get_fiscal_deadlines_tool",
    "fill_modelo_303_playwright", "fill_modelo_130_playwright",
    "fill_modelo_111_playwright", "fill_modelo_115_playwright"
}

PRO_ALLOWED_TOOLS = BASIC_ALLOWED_TOOLS | {
    # Open Banking y Conciliación
    "run_bank_reconciliation", "get_unreconciled_report_tool", "get_bank_balance",
    "import_bank_statement", "add_manual_bank_movement", "initiate_transfer",
    "check_consent_status_tool",
    # Previsión de Tesorería
    "get_cash_flow_forecast_tool", "get_liquidity_alerts_tool",
    # Presupuestos y Cobros
    "create_quote", "get_quotes", "convert_quote_to_invoice", "sign_quote", "verify_quote_signature",
    "register_payment", "get_invoice_payment_summary", "get_pending_payments_report",
    # Asistente IA Proactivo y Cierre Contable
    "request_document", "send_to_advisor", "export_advisor_pack", "export_advisor_pack_tool",
    "get_profit_and_loss_report", "close_fiscal_year_tool"
}

ADVISOR_ALLOWED_TOOLS = PRO_ALLOWED_TOOLS | {
    # Factura Electrónica B2B avanzada
    "export_einvoice_tool", "get_b2b_invoice_status_history_tool", "update_b2b_invoice_status_tool",
    # Multi-tenant / Asesoría completa
    "get_projects_wip", "update_project_status"
}

TIER_CAPABILITIES = {
    "basic": {
        "name": "Plan Autónomo Basic",
        "allowed_tools": BASIC_ALLOWED_TOOLS,
        "max_tenants": 1,
        "upgrade_message": "Esta funcionalidad (Open Banking, Presupuestos, Asistente IA o Tesorería) requiere el Plan Pro (29 €/mes) o Plan Asesoría (69 €/mes)."
    },
    "pro": {
        "name": "Plan Autónomo Pro",
        "allowed_tools": PRO_ALLOWED_TOOLS,
        "max_tenants": 1,
        "upgrade_message": "Esta funcionalidad (Gestión Multi-Empresa ilimitada o E-Factura B2B Avanzada) requiere el Plan Asesoría (69 €/mes)."
    },
    "advisor": {
        "name": "Plan Asesoría / Despacho",
        "allowed_tools": ADVISOR_ALLOWED_TOOLS,
        "max_tenants": 9999,
        "upgrade_message": None
    },
    "premium": {
        "name": "Plan Premium Completo",
        "allowed_tools": ADVISOR_ALLOWED_TOOLS,
        "max_tenants": 9999,
        "upgrade_message": None
    }
}

@dataclass
class LicenseStatusResult:
    status: str  # "active", "grace_period", "expired", "machine_mismatch", "invalid_signature", "clock_tampered", "missing"
    is_operational: bool
    holder: Optional[str] = None
    client_id: Optional[str] = None
    license_type: Optional[str] = None
    tier: Optional[str] = None
    expires_at: Optional[str] = None
    machine_fingerprint: Optional[str] = None
    grace_days_remaining: int = 0
    days_until_expiration: int = 0
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "is_operational": self.is_operational,
            "holder": self.holder,
            "client_id": self.client_id,
            "license_type": self.license_type,
            "tier": self.tier or self.license_type,
            "expires_at": self.expires_at,
            "machine_fingerprint": self.machine_fingerprint,
            "grace_days_remaining": self.grace_days_remaining,
            "days_until_expiration": self.days_until_expiration,
            "message": self.message,
        }

def get_machine_fingerprint() -> str:
    """
    Genera un identificador criptográfico único e inmutable del hardware del equipo (Machine Fingerprint).
    Combina UUID de placa/sistema, MAC address, hostname y arquitectura.
    """
    raw_components = []

    # 1. Windows MachineGuid o UUID del sistema
    if platform.system() == "Windows":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                if guid:
                    raw_components.append(f"win_guid:{guid.strip()}")
        except Exception:
            pass

    # 2. Linux Machine ID
    elif platform.system() == "Linux":
        for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            if os.path.exists(p):
                try:
                    raw_components.append(f"linux_id:{Path(p).read_text().strip()}")
                    break
                except Exception:
                    pass

    # 3. Fallbacks de hardware universales
    try:
        node_mac = hex(uuid.getnode())
        raw_components.append(f"mac:{node_mac}")
    except Exception:
        pass

    raw_components.append(f"host:{platform.node()}")
    raw_components.append(f"arch:{platform.machine()}")
    raw_components.append(f"proc:{platform.processor()}")

    joined = "|".join(raw_components)
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest().upper()
    return f"ALF-MACH-{digest[:16]}"

def check_clock_integrity(current_dt: Optional[datetime] = None) -> bool:
    """
    Verifica que el reloj del sistema no haya sido retrasado para burlar la expiración.
    Compara con el último timestamp persistido localmente.
    """
    now = current_dt or datetime.now()
    now_epoch = now.timestamp()

    if CLOCK_INTEGRITY_PATH.exists():
        try:
            data = json.loads(CLOCK_INTEGRITY_PATH.read_text(encoding="utf-8"))
            last_seen_epoch = data.get("last_seen_epoch", 0)
            # Permitir un margen de 300 segundos (5 min) por pequeños desajustes NTP
            if now_epoch < (last_seen_epoch - 300):
                return False
        except Exception:
            pass

    try:
        CLOCK_INTEGRITY_PATH.parent.mkdir(parents=True, exist_ok=True)
        CLOCK_INTEGRITY_PATH.write_text(
            json.dumps({
                "last_seen_epoch": now_epoch,
                "last_seen_iso": now.isoformat()
            }),
            encoding="utf-8"
        )
    except Exception:
        pass

    return True

def check_license_status(
    current_dt: Optional[datetime] = None,
    ignore_dev_bypass: bool = False,
    override_machine_fingerprint: Optional[str] = None
) -> LicenseStatusResult:
    """
    Evalúa el estado completo de la licencia local:
    - Activa (dentro del mes pagado)
    - Período de gracia (hasta 5 días después del vencimiento -> sigue operativo)
    - Expirada (más de 5 días de retraso)
    - Enlazado de hardware (Machine Binding mismatch)
    - Manipulación de reloj / Firma inválida / Ausente
    """
    now = current_dt or datetime.now()
    local_machine_fp = override_machine_fingerprint or get_machine_fingerprint()

    # 1. Bypass para desarrollo explícito
    if not ignore_dev_bypass:
        dev_bypass = os.getenv("ALFONSO_DEV_PREMIUM_BYPASS")
        if dev_bypass == "AlfonsoDevelopmentToken2026!":
            return LicenseStatusResult(
                status="active",
                is_operational=True,
                holder="Entorno de Pruebas",
                license_type="advisor",
                tier="advisor",
                expires_at="2099-12-31",
                machine_fingerprint=local_machine_fp,
                days_until_expiration=9999,
                grace_days_remaining=DEFAULT_GRACE_PERIOD_DAYS,
                message="Licencia activa en modo desarrollo/pruebas (Nivel Asesoría Máximo)."
            )

    # 2. Comprobar existencia del archivo de licencia
    if not LICENSE_PATH.exists():
        return LicenseStatusResult(
            status="missing",
            is_operational=False,
            machine_fingerprint=local_machine_fp,
            message="No se ha encontrado el archivo de licencia local (data/license.lic)."
        )

    try:
        license_data = json.loads(LICENSE_PATH.read_text(encoding="utf-8"))
        raw_type = str(license_data.get("license_type", "")).strip().lower()

        payload = {
            "license_type": license_data.get("license_type"),
            "holder": license_data.get("holder"),
            "expires_at": license_data.get("expires_at")
        }
        if "machine_fingerprint" in license_data and license_data["machine_fingerprint"]:
            payload["machine_fingerprint"] = license_data["machine_fingerprint"]

        client_id = license_data.get("client_id")
        signature_b64 = license_data.get("signature")

        if not signature_b64:
            return LicenseStatusResult(
                status="invalid_signature",
                is_operational=False,
                machine_fingerprint=local_machine_fp,
                message="El archivo de licencia no contiene firma digital válida."
            )

        # 3. Verificar firma criptográfica RSA con la clave pública maestra
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        signature = base64.b64decode(signature_b64.encode("utf-8"))
        public_key = serialization.load_pem_public_key(PUBLIC_KEY_PEM)

        public_key.verify(
            signature,
            payload_bytes,
            padding.PKCS1v15(),
            hashes.SHA256()
        )

        # 4. Comprobar tipo de licencia admitido
        if raw_type not in ("basic", "pro", "advisor", "premium"):
            return LicenseStatusResult(
                status="invalid_type",
                is_operational=False,
                holder=payload.get("holder"),
                license_type=raw_type,
                tier=raw_type,
                machine_fingerprint=local_machine_fp,
                message=f"Tipo de membresía '{raw_type}' no reconocido como operativo."
            )

        # Normalizar tier (premium -> advisor)
        normalized_tier = "advisor" if raw_type in ("advisor", "premium") else raw_type

        # 5. Comprobar vinculación de Hardware (Machine Binding) si la licencia lo especifica
        license_fp = payload.get("machine_fingerprint")
        if license_fp and license_fp != local_machine_fp:
            return LicenseStatusResult(
                status="machine_mismatch",
                is_operational=False,
                holder=payload.get("holder"),
                client_id=client_id,
                license_type=raw_type,
                tier=normalized_tier,
                machine_fingerprint=local_machine_fp,
                expires_at=payload.get("expires_at"),
                message=f"La licencia está vinculada a otro ordenador ({license_fp}) y no coincide con este equipo ({local_machine_fp})."
            )

        # 6. Comprobar integridad del reloj local
        if not check_clock_integrity(now):
            return LicenseStatusResult(
                status="clock_tampered",
                is_operational=False,
                holder=payload.get("holder"),
                license_type=raw_type,
                tier=normalized_tier,
                machine_fingerprint=local_machine_fp,
                message="Se ha detectado una alteración o retraso en la fecha/hora del sistema. Sincroniza la hora de tu equipo."
            )

        # 7. Comprobar fechas y período de gracia de 5 días
        expires_at_str = payload.get("expires_at")
        if not expires_at_str:
            return LicenseStatusResult(
                status="invalid_format",
                is_operational=False,
                license_type=raw_type,
                tier=normalized_tier,
                machine_fingerprint=local_machine_fp,
                message="La licencia no especifica fecha de expiración."
            )

        exp_date = datetime.strptime(expires_at_str, "%Y-%m-%d").date()
        today = now.date()

        tier_display_name = TIER_CAPABILITIES.get(normalized_tier, {}).get("name", normalized_tier.capitalize())

        if today <= exp_date:
            # Caso 1: Licencia plenamente activa
            days_left = (exp_date - today).days
            return LicenseStatusResult(
                status="active",
                is_operational=True,
                holder=payload.get("holder"),
                client_id=client_id,
                license_type=raw_type,
                tier=normalized_tier,
                expires_at=expires_at_str,
                machine_fingerprint=local_machine_fp,
                days_until_expiration=days_left,
                grace_days_remaining=DEFAULT_GRACE_PERIOD_DAYS,
                message=f"Suscripción '{tier_display_name}' activa. Vence el {expires_at_str} ({days_left} días restantes)."
            )

        days_overdue = (today - exp_date).days
        if days_overdue <= DEFAULT_GRACE_PERIOD_DAYS:
            # Caso 2: Período de gracia de 5 días (sigue operativo)
            grace_left = DEFAULT_GRACE_PERIOD_DAYS - days_overdue
            return LicenseStatusResult(
                status="grace_period",
                is_operational=True,
                holder=payload.get("holder"),
                client_id=client_id,
                license_type=raw_type,
                tier=normalized_tier,
                expires_at=expires_at_str,
                machine_fingerprint=local_machine_fp,
                days_until_expiration=0,
                grace_days_remaining=grace_left,
                message=f"Tu cuota mensual de '{tier_display_name}' venció el {expires_at_str}. Estás en período de gracia de 5 días ({grace_left} días restantes de cortesía) para regularizar el pago sin interrupción del servicio."
            )

        # Caso 3: Vencida definitivamente tras agotar los 5 días de gracia
        return LicenseStatusResult(
            status="expired",
            is_operational=False,
            holder=payload.get("holder"),
            client_id=client_id,
            license_type=raw_type,
            tier=normalized_tier,
            expires_at=expires_at_str,
            machine_fingerprint=local_machine_fp,
            days_until_expiration=0,
            grace_days_remaining=0,
            message=f"Tu suscripción '{tier_display_name}' y el período de cortesía de 5 días han expirado (venció el {expires_at_str}). Por favor, renueva tu suscripción mensual para continuar usando el asistente."
        )

    except Exception as e:
        return LicenseStatusResult(
            status="invalid_signature",
            is_operational=False,
            machine_fingerprint=local_machine_fp,
            message=f"Firma o archivo de licencia corrupto o no válido: {str(e)}"
        )

def get_active_license_tier() -> str:
    """Devuelve el tier normalizado activo ('basic', 'pro', 'advisor') o 'none' si no es válida."""
    status = check_license_status()
    if not status.is_operational:
        return "none"
    return status.tier or status.license_type or "basic"

def is_tool_allowed_for_tier(tool_name: str, tier: Optional[str] = None) -> Tuple[bool, str]:
    """
    Verifica si una herramienta específica está autorizada para el nivel de membresía activo.
    Retorna (is_allowed, reason_or_upgrade_message).
    """
    active_tier = tier or get_active_license_tier()
    if active_tier == "none":
        # Si estamos en entorno de testing general y no hay archivo de licencia, permitir advisor para tests de otros módulos
        is_testing = os.getenv("ALFONSO_IS_TESTING") == "True" or os.getenv("PYTEST_CURRENT_TEST") is not None
        if is_testing:
            active_tier = "advisor"
        else:
            return False, "No dispones de una licencia activa o en período de gracia. Activa tu suscripción para utilizar el asistente."

    tier_info = TIER_CAPABILITIES.get(active_tier, TIER_CAPABILITIES.get("basic"))
    allowed_tools = tier_info.get("allowed_tools", BASIC_ALLOWED_TOOLS)

    if tool_name in allowed_tools:
        return True, "Operación autorizada por tu nivel de suscripción."

    upgrade_msg = tier_info.get("upgrade_message") or "Esta funcionalidad requiere una membresía superior. Actualiza tu plan para desbloquearla."
    return False, f"La herramienta '{tool_name}' no está incluida en tu '{tier_info.get('name')}'. {upgrade_msg}"

def is_premium_license_valid() -> bool:
    """Compatibilidad: retorna True si la licencia local está operativa (activa o en período de gracia)."""
    return check_license_status().is_operational

def install_license(license_data: Dict[str, Any]) -> bool:
    """Guarda un nuevo archivo de licencia en el almacenamiento local."""
    try:
        LICENSE_PATH.parent.mkdir(parents=True, exist_ok=True)
        LICENSE_PATH.write_text(json.dumps(license_data, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False

def generate_signed_license(
    holder: str,
    expires_at: str,
    license_type: str = "premium",
    client_id: Optional[str] = None,
    machine_fingerprint: Optional[str] = None,
    private_key: Optional[rsa.RSAPrivateKey] = None
) -> Dict[str, Any]:
    """
    Genera un diccionario de licencia firmado criptográficamente con RSA-SHA256.
    Incluye opcionalmente la huella digital del hardware (Machine Binding).
    """
    if private_key is None:
        raise ValueError("Se requiere una clave privada RSA para firmar la licencia.")

    payload = {
        "license_type": license_type,
        "holder": holder,
        "expires_at": expires_at
    }
    if machine_fingerprint:
        payload["machine_fingerprint"] = machine_fingerprint

    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    signature = private_key.sign(
        payload_bytes,
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    signature_b64 = base64.b64encode(signature).decode("utf-8")

    result = {
        "license_type": license_type,
        "holder": holder,
        "expires_at": expires_at,
        "client_id": client_id or "default",
        "signature": signature_b64
    }
    if machine_fingerprint:
        result["machine_fingerprint"] = machine_fingerprint

    return result
