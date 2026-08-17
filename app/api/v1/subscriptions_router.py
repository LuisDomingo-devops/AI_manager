import os
import json
import uuid
import hmac
import hashlib
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Header, Request, Depends
from pydantic import BaseModel, Field

from app.domain.services.tenant_provisioner import TenantProvisioningService
from app.api.routes import verify_api_key
import logging

logger = logging.getLogger("subscriptions_router")
router = APIRouter(prefix="/subscriptions")

class CheckoutSessionRequest(BaseModel):
    client_id: str = Field(..., description="Identificador único del tenant/empresa")
    company_name: str = Field(..., description="Razón Social o Nombre del Autónomo")
    nif: str = Field(..., description="NIF/NIE/CIF fiscal")
    email: str = Field(..., description="Correo electrónico de contacto y facturación")
    plan_tier: str = Field("pro", description="Nivel de suscripción: basic, pro, advisor_pack")
    success_url: Optional[str] = "https://app.alfonsoautonomo.com/success"
    cancel_url: Optional[str] = "https://app.alfonsoautonomo.com/cancel"

class WebhookSimulationRequest(BaseModel):
    event_type: str = "checkout.session.completed"
    client_id: str
    company_name: str
    nif: str
    email: str
    plan_tier: str = "pro"
    stripe_customer_id: Optional[str] = "cus_mock123"
    stripe_subscription_id: Optional[str] = "sub_mock123"

@router.post("/checkout-session", summary="Generar sesión de pago en Stripe")
async def create_checkout_session(payload: CheckoutSessionRequest):
    """
    Crea una sesión de checkout de Stripe para la suscripción de un nuevo autónomo o asesoría.
    """
    stripe_api_key = os.getenv("STRIPE_SECRET_KEY")
    client_id = TenantProvisioningService.sanitize_client_id(payload.client_id)

    if not stripe_api_key or stripe_api_key.startswith("sk_test_mock"):
        # Modo simulado / sandbox local para pruebas y desarrollo
        session_id = f"cs_test_{uuid.uuid4().hex}"
        checkout_url = f"https://checkout.stripe.com/pay/{session_id}?client_id={client_id}"
        return {
            "status": "ok",
            "mode": "sandbox",
            "session_id": session_id,
            "checkout_url": checkout_url,
            "client_id": client_id,
            "plan_tier": payload.plan_tier,
            "message": "Sesión de checkout creada en modo sandbox. Completa el pago simulado para activar."
        }

    try:
        import stripe
        stripe.api_key = stripe_api_key
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            customer_email=payload.email,
            client_reference_id=client_id,
            metadata={
                "client_id": client_id,
                "company_name": payload.company_name,
                "nif": payload.nif,
                "plan_tier": payload.plan_tier
            },
            success_url=f"{payload.success_url}?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=payload.cancel_url,
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "product_data": {
                        "name": f"Alfonso Autónomo - Plan {payload.plan_tier.upper()}",
                        "description": "Asistente contable y fiscal autónomo con homologación Veri*factu",
                    },
                    "unit_amount": 1900 if payload.plan_tier == "basic" else 3900,
                    "recurring": {"interval": "month"}
                },
                "quantity": 1
            }]
        )
        return {
            "status": "ok",
            "mode": "live",
            "session_id": session.id,
            "checkout_url": session.url,
            "client_id": client_id,
            "plan_tier": payload.plan_tier
        }
    except Exception as e:
        logger.exception("Error al crear sesión en Stripe: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Error al conectar con Stripe: {str(e)}")

@router.post("/webhook", summary="Procesar webhook de eventos de Stripe")
async def stripe_webhook(request: Request, stripe_signature: Optional[str] = Header(None, alias="stripe-signature")):
    """
    Webhook que recibe los eventos de cobro y alta de suscripción de Stripe.
    Aprovisiona automáticamente el tenant cuando el pago es confirmado.
    """
    body_bytes = await request.body()
    try:
        data = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Cuerpo de webhook inválido")

    event_type = data.get("type") or data.get("event_type")
    logger.info("Recibido evento de webhook Stripe: %s", event_type)

    if event_type in ("checkout.session.completed", "invoice.payment_succeeded"):
        session_obj = data.get("data", {}).get("object", data)
        metadata = session_obj.get("metadata", {})
        
        client_id = metadata.get("client_id") or session_obj.get("client_id") or session_obj.get("client_reference_id", "default")
        company_name = metadata.get("company_name") or session_obj.get("company_name", "Empresa Cliente")
        nif = metadata.get("nif") or session_obj.get("nif", "B00000000")
        email = session_obj.get("customer_email") or metadata.get("email") or session_obj.get("email", "cliente@ejemplo.com")
        plan_tier = metadata.get("plan_tier") or session_obj.get("plan_tier", "pro")
        customer_id = session_obj.get("customer") or session_obj.get("stripe_customer_id", "")
        subscription_id = session_obj.get("subscription") or session_obj.get("stripe_subscription_id", "")

        provision_result = TenantProvisioningService.provision_new_tenant(
            client_id=client_id,
            company_name=company_name,
            nif=nif,
            email=email,
            plan_tier=plan_tier,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id
        )

        return {
            "status": "processed",
            "event": event_type,
            "provision": provision_result
        }

    return {"status": "ignored", "event": event_type}

@router.get("/status/{client_id}", summary="Consultar estado de suscripción del tenant", dependencies=[Depends(verify_api_key)])
async def get_subscription_status(client_id: str):
    """
    Consulta el estado de suscripción y perfil de un cliente/tenant.
    """
    try:
        status = TenantProvisioningService.get_tenant_status(client_id)
        return {"status": "ok", "data": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/machine-fingerprint", summary="Obtener huella digital de hardware del equipo actual")
async def get_local_machine_fingerprint():
    """
    Retorna el identificador único del hardware (Machine Fingerprint) del ordenador local.
    Se utiliza para emitir y activar licencias con Machine Binding.
    """
    from app.utils.license_validator import get_machine_fingerprint
    fp = get_machine_fingerprint()
    return {
        "status": "ok",
        "machine_fingerprint": fp
    }

@router.get("/license-status", summary="Consultar estado de licencia local y período de gracia de 5 días")
async def get_local_license_status():
    """
    Verifica criptográficamente el archivo de licencia local en el equipo del cliente.
    Informa si está activa, en período de gracia de 5 días (sigue operativa), enlazado de hardware o expirada.
    """
    from app.utils.license_validator import check_license_status
    result = check_license_status()
    return {
        "status": "ok",
        "license": result.to_dict()
    }

class LicenseActivationRequest(BaseModel):
    license_data: Dict[str, Any] = Field(..., description="Diccionario con datos de licencia y firma RSA")

@router.post("/activate-license", summary="Instalar y activar archivo de licencia local")
async def activate_local_license(payload: LicenseActivationRequest):
    """
    Instala un nuevo archivo de licencia criptográfico en el almacenamiento local (data/license.lic).
    """
    from app.utils.license_validator import install_license, check_license_status
    success = install_license(payload.license_data)
    if not success:
        raise HTTPException(status_code=500, detail="No se pudo escribir el archivo de licencia local.")

    result = check_license_status()
    return {
        "status": "ok" if result.is_operational else "warning",
        "installed": True,
        "license": result.to_dict()
    }
