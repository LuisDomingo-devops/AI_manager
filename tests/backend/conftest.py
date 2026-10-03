import pytest

@pytest.fixture
def sample_valid_nif():
    return "12345678Z"

@pytest.fixture
def sample_invalid_nif():
    return "12345678A"  # Letra incorrecta para ese número (12345678 % 23 = 14 -> Z)

@pytest.fixture
def sample_valid_nie():
    return "X1234567L"  # X0 -> 01234567 % 23 = 10 -> L

@pytest.fixture
def sample_valid_cif():
    return "B12345674"

@pytest.fixture
def sample_valid_iban():
    return "ES9121000418401234567891"

@pytest.fixture
def sample_sensitive_text():
    return (
        "El cliente Juan Pérez con NIF 12345678Z y teléfono 600123456 "
        "debe pagar 1.500,00 € a la cuenta ES9121000418401234567891 en Calle Mayor 12, 28013."
    )


@pytest.fixture
def sample_inmueble_arrendado_comun():
    from app.domain.models.billing import InmuebleArrendadoDTO
    return InmuebleArrendadoDTO(
        situacion_inmueble=1,
        referencia_catastral="9872023VH5797S0001WX",
        tipo_via="CL",
        nombre_via="GRAN VIA",
        numero="28",
        municipio="MADRID",
        codigo_postal="28013",
        codigo_provincia="28"
    )


@pytest.fixture
def sample_inmueble_arrendado_sin_ref():
    from app.domain.models.billing import InmuebleArrendadoDTO
    return InmuebleArrendadoDTO(
        situacion_inmueble=3,
        referencia_catastral=None,
        tipo_via="CL",
        nombre_via="CAMINO RUSTICO",
        numero="SN",
        municipio="CHINCHON",
        codigo_postal="28370",
        codigo_provincia="28"
    )


@pytest.fixture
def sample_declarant_info():
    from app.domain.models.billing import DeclarantInfoDTO
    return DeclarantInfoDTO(
        nif="B87654321",
        name="INNOVACIONES TECNOLOGICAS SL",
        phone="912345678",
        contact_person="CARLOS MENDEZ",
        is_complementary=False
    )


@pytest.fixture
def sample_model_347_purchase_declared():
    from app.domain.models.billing import Model347DeclaredDTO
    return Model347DeclaredDTO(
        nif="B12345674",
        name="SUMINISTROS INDUSTRIALES SA",
        province_code="28",
        operation_key="A",
        total_annual_amount=12000.00,
        quarter_1_amount=3000.00,
        quarter_2_amount=3000.00,
        quarter_3_amount=3000.00,
        quarter_4_amount=3000.00,
        cash_amount=0.0,
        is_cash_basis_recc=False,
        is_reverse_charge=False
    )


@pytest.fixture
def sample_model_347_sales_declared():
    from app.domain.models.billing import Model347DeclaredDTO
    return Model347DeclaredDTO(
        nif="12345678Z",
        name="GARCIA LOPEZ ANTONIO",
        province_code="08",
        operation_key="B",
        total_annual_amount=25000.00,
        quarter_1_amount=5000.00,
        quarter_2_amount=7000.00,
        quarter_3_amount=6000.00,
        quarter_4_amount=7000.00,
        cash_amount=8500.00,
        is_cash_basis_recc=False,
        is_reverse_charge=False
    )


@pytest.fixture
def sample_model_347_result(sample_model_347_purchase_declared, sample_model_347_sales_declared):
    from app.domain.models.billing import Model347ResultDTO
    records = [sample_model_347_purchase_declared, sample_model_347_sales_declared]
    return Model347ResultDTO(
        fiscal_year=2026,
        declarant_nif="B87654321",
        declarant_name="INNOVACIONES TECNOLOGICAS SL",
        total_declared_records=len(records),
        total_operations_amount=37000.00,
        total_cash_amount=8500.00,
        declared_records=records,
        is_complementary=False
    )

