import json
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from admin_tools_private.license_issuer import PrivateLicenseIssuer
from app.utils.license_validator import (
    is_tool_allowed_for_tier,
    get_active_license_tier,
    check_license_status,
    install_license,
    get_machine_fingerprint,
    LICENSE_PATH,
    CLOCK_INTEGRITY_PATH
)
from app.domain.planner_orchestrator import ToolExecutionEngine

@pytest.fixture(autouse=True)
def clean_env():
    """Limpia los archivos de prueba antes y después."""
    for p in (LICENSE_PATH, CLOCK_INTEGRITY_PATH):
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass
    yield
    for p in (LICENSE_PATH, CLOCK_INTEGRITY_PATH):
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass

@pytest.fixture
def master_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    pub_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return private_key, pub_pem

def test_basic_tier_allowed_and_blocked_tools(master_keypair):
    """
    Verifica que el Plan Basic (15€) permita facturación y modelos AEAT,
    pero bloquee Open Banking, presupuestos con firma, tesorería y tools de IA.
    """
    private_key, pub_pem = master_keypair
    local_fp = get_machine_fingerprint()

    # 1. Emitir e instalar licencia Basic
    basic_lic = PrivateLicenseIssuer.issue_paid_license(
        holder="Autónomo Básico",
        client_id="basic_01",
        machine_fingerprint=local_fp,
        months=1,
        license_type="basic",
        private_key=private_key
    )
    install_license(basic_lic)

    with patch("app.utils.license_validator.PUBLIC_KEY_PEM", pub_pem):
        with patch.dict("os.environ", {"ALFONSO_IS_TESTING": "False"}):
            tier = get_active_license_tier()
            assert tier == "basic"

            # A. Herramientas Permitidas en Basic
            ok_inv, _ = is_tool_allowed_for_tier("create_invoice", tier="basic")
            assert ok_inv is True

            ok_tax, _ = is_tool_allowed_for_tier("get_tax_estimate", tier="basic")
            assert ok_tax is True

            ok_diario, _ = is_tool_allowed_for_tier("get_libro_diario", tier="basic")
            assert ok_diario is True

            # B. Herramientas Bloqueadas en Basic (requieren Pro o Advisor)
            ok_bank, msg_bank = is_tool_allowed_for_tier("run_bank_reconciliation", tier="basic")
            assert ok_bank is False
            assert "requiere el Plan Pro" in msg_bank

            ok_quote, msg_quote = is_tool_allowed_for_tier("create_quote", tier="basic")
            assert ok_quote is False

            ok_send, msg_send = is_tool_allowed_for_tier("send_to_advisor", tier="basic")
            assert ok_send is False

            ok_req, msg_req = is_tool_allowed_for_tier("request_document", tier="basic")
            assert ok_req is False

            ok_cash, msg_cash = is_tool_allowed_for_tier("get_cash_flow_forecast_tool", tier="basic")
            assert ok_cash is False

def test_pro_tier_allowed_and_blocked_tools(master_keypair):
    """
    Verifica que el Plan Pro (29€) permita Open Banking, Quotes, Tesorería,
    send_to_advisor y request_document, pero bloquee B2B avanzada.
    """
    private_key, pub_pem = master_keypair
    local_fp = get_machine_fingerprint()

    # 1. Emitir e instalar licencia Pro
    pro_lic = PrivateLicenseIssuer.issue_paid_license(
        holder="Autónomo Profesional",
        client_id="pro_01",
        machine_fingerprint=local_fp,
        months=1,
        license_type="pro",
        private_key=private_key
    )
    install_license(pro_lic)

    with patch("app.utils.license_validator.PUBLIC_KEY_PEM", pub_pem):
        with patch.dict("os.environ", {"ALFONSO_IS_TESTING": "False"}):
            tier = get_active_license_tier()
            assert tier == "pro"

            # A. Herramientas Permitidas en Pro
            assert is_tool_allowed_for_tier("create_invoice", tier="pro")[0] is True
            assert is_tool_allowed_for_tier("run_bank_reconciliation", tier="pro")[0] is True
            assert is_tool_allowed_for_tier("create_quote", tier="pro")[0] is True
            assert is_tool_allowed_for_tier("send_to_advisor", tier="pro")[0] is True
            assert is_tool_allowed_for_tier("request_document", tier="pro")[0] is True
            assert is_tool_allowed_for_tier("get_cash_flow_forecast_tool", tier="pro")[0] is True

            # B. Herramientas Bloqueadas en Pro (requieren Advisor)
            ok_b2b, msg_b2b = is_tool_allowed_for_tier("export_einvoice_tool", tier="pro")
            assert ok_b2b is False
            assert "requiere el Plan Asesoría" in msg_b2b

def test_advisor_tier_full_power(master_keypair):
    """
    Verifica que el Plan Asesoría (69€) tenga desbloqueado el 100% de capacidades.
    """
    private_key, pub_pem = master_keypair
    local_fp = get_machine_fingerprint()

    advisor_lic = PrivateLicenseIssuer.issue_paid_license(
        holder="Gestoría y Asesoría Fiscal",
        client_id="asesoria_01",
        machine_fingerprint=local_fp,
        months=12,
        license_type="advisor",
        private_key=private_key
    )
    install_license(advisor_lic)

    with patch("app.utils.license_validator.PUBLIC_KEY_PEM", pub_pem):
        with patch.dict("os.environ", {"ALFONSO_IS_TESTING": "False"}):
            tier = get_active_license_tier()
            assert tier == "advisor"

            # Todo autorizado al 100%
            assert is_tool_allowed_for_tier("create_invoice", tier="advisor")[0] is True
            assert is_tool_allowed_for_tier("run_bank_reconciliation", tier="advisor")[0] is True
            assert is_tool_allowed_for_tier("create_quote", tier="advisor")[0] is True
            assert is_tool_allowed_for_tier("send_to_advisor", tier="advisor")[0] is True
            assert is_tool_allowed_for_tier("request_document", tier="advisor")[0] is True
            assert is_tool_allowed_for_tier("export_einvoice_tool", tier="advisor")[0] is True
            assert is_tool_allowed_for_tier("get_projects_wip", tier="advisor")[0] is True

@pytest.mark.asyncio
async def test_orchestrator_execution_intercepted_on_basic_tier(master_keypair):
    """
    Verifica que si el LLM intenta ejecutar una tool Pro en una licencia Basic,
    el ToolExecutionEngine intercepte y retorne 'tier_upgrade_required'.
    """
    private_key, pub_pem = master_keypair
    local_fp = get_machine_fingerprint()

    basic_lic = PrivateLicenseIssuer.issue_paid_license(
        holder="Usuario Basic Test",
        client_id="basic_user",
        machine_fingerprint=local_fp,
        months=1,
        license_type="basic",
        private_key=private_key
    )
    install_license(basic_lic)

    mock_memory = MagicMock()
    mock_bridge = MagicMock()
    mock_logger = MagicMock()
    mock_error = MagicMock()
    engine = ToolExecutionEngine(memory=mock_memory, bridge=mock_bridge)

    with patch("app.utils.license_validator.PUBLIC_KEY_PEM", pub_pem):
        with patch("app.utils.license_validator.get_active_license_tier", return_value="basic"):
            res = await engine.execute_tool(
                tool_name="run_bank_reconciliation",
                args={},
                session_id="session_test",
                client_id="basic_user",
                request_id="req_test",
                logger=mock_logger,
                error=mock_error
            )
            assert res["status"] == "tier_upgrade_required"
            assert "requiere el Plan Pro" in res["message"]
