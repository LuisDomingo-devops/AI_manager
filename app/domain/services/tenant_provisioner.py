import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import logging

from app.adapters.memory.memory import _get_connection, tenant_context, IS_TESTING, DB_PATH
from app.infrastructure.database.migrations import MigrationRunner
from app.domain.services.verifactu_service import VerifactuService

logger = logging.getLogger("tenant_provisioner")

class TenantProvisioningService:
    """
    Servicio de auto-aprovisionamiento de nuevos inquilinos (tenants) para Alfonso Autónomo SaaS.
    Gestiona el ciclo de alta tras el pago en Stripe o registro:
    1. Aislamiento físico de la base de datos SQLite por tenant.
    2. Ejecución automática y secuencial de todas las migraciones versionadas.
    3. Generación y almacenamiento seguro de claves criptográficas RSA del SIF.
    4. Configuración del perfil fiscal inicial y suscripción activa.
    5. Emisión de API Key / token de acceso.
    """

    @classmethod
    def sanitize_client_id(cls, raw_id: str) -> str:
        """Sanitiza el identificador de cliente para su uso seguro como nombre de archivo."""
        clean = re.sub(r'[^a-zA-Z0-9_-]', '_', (raw_id or "").strip().lower())
        return clean or f"client_{uuid.uuid4().hex[:8]}"

    @classmethod
    def provision_new_tenant(
        cls,
        client_id: str,
        company_name: str,
        nif: str,
        email: str,
        plan_tier: str = "pro",
        stripe_customer_id: str = "",
        stripe_subscription_id: str = ""
    ) -> Dict[str, Any]:
        """
        Aprovisiona completamente un nuevo tenant de forma atómica y reproducible.
        """
        cid = cls.sanitize_client_id(client_id)
        logger.info("Iniciando aprovisionamiento para el tenant: %s (%s, NIF: %s)", cid, company_name, nif)

        # 1. Conexión e inicialización del archivo de base de datos
        with _get_connection(cid) as conn:
            # 2. Ejecutar todas las migraciones pendientes
            applied_migrations = MigrationRunner.run_pending_migrations(conn)

            # 3. Configurar perfil de usuario inicial en user_profile
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM user_profile")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO user_profile (user_type, nif, razon_social, direccion)
                    VALUES ('autonomo', ?, ?, 'Dirección pendiente de configurar')
                """, (nif, company_name))
            else:
                cursor.execute("""
                    UPDATE user_profile
                    SET nif = ?, razon_social = ?, updated_at = datetime('now')
                    WHERE id = 1
                """, (nif, company_name))

            # 4. Configurar estado de suscripción
            today_str = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("""
                UPDATE subscription_status
                SET tier = ?, billing_cycle_start = ?
            """, (plan_tier, today_str))

            conn.commit()

        # 5. Generar par de claves RSA aisladas para el SIF
        VerifactuService.get_or_create_private_key(client_id=cid)

        # 6. Generar API Key de acceso para el tenant
        api_key = f"alf_live_{cid}_{uuid.uuid4().hex}"

        logger.info("Tenant %s aprovisionado con éxito. Migraciones aplicadas: %d", cid, len(applied_migrations))

        return {
            "status": "provisioned",
            "client_id": cid,
            "company_name": company_name,
            "nif": nif,
            "email": email,
            "plan_tier": plan_tier,
            "stripe_customer_id": stripe_customer_id,
            "stripe_subscription_id": stripe_subscription_id,
            "api_key": api_key,
            "applied_migrations_count": len(applied_migrations),
            "provisioned_at": datetime.now().isoformat()
        }

    @classmethod
    def get_tenant_status(cls, client_id: str) -> Dict[str, Any]:
        """Consulta el estado del tenant y su base de datos."""
        cid = cls.sanitize_client_id(client_id)
        with _get_connection(cid) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT nif, razon_social FROM user_profile LIMIT 1")
            profile = cursor.fetchone()
            cursor.execute("SELECT tier, billing_cycle_start FROM subscription_status LIMIT 1")
            sub = cursor.fetchone()

        return {
            "client_id": cid,
            "profile": dict(profile) if profile else None,
            "subscription": dict(sub) if sub else None,
            "is_active": True
        }
