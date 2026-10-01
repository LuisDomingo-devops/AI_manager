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
