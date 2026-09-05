import pytest
from app.utils.anonymizer import DataAnonymizer

def test_anonymizer_nif():
    anonymizer = DataAnonymizer()
    text = "El cliente con NIF 12345678Z y CIF A1234567B ha solicitado la devolución."
    anon, mapping = anonymizer.anonymize(text)
    
    assert "[NIF_1]" in anon
    assert "[NIF_2]" in anon
    assert "12345678Z" in mapping.values()
    assert "A1234567B" in mapping.values()
    
    # Detokenización
    recovered = anonymizer.detokenize(anon, mapping)
    assert recovered == text

def test_anonymizer_amount():
    anonymizer = DataAnonymizer()
    text = "El total de la factura es de 1.250,50€ más 150 EUR de gastos de envío."
    anon, mapping = anonymizer.anonymize(text)
    
    assert "[IMPORTE_1]" in anon
    assert "[IMPORTE_2]" in anon
    assert "1.250,50€" in mapping.values()
    assert "150 EUR" in mapping.values()
    
    recovered = anonymizer.detokenize(anon, mapping)
    assert recovered == text

def test_anonymizer_email():
    anonymizer = DataAnonymizer()
    text = "Por favor envíe el justificante a juan.perez@empresa.com o info@correo.es"
    anon, mapping = anonymizer.anonymize(text)
    
    assert "[EMAIL_1]" in anon
    assert "[EMAIL_2]" in anon
    assert "juan.perez@empresa.com" in mapping.values()
    assert "info@correo.es" in mapping.values()
    
    recovered = anonymizer.detokenize(anon, mapping)
    assert recovered == text

def test_anonymizer_phone():
    anonymizer = DataAnonymizer()
    text = "Llámenos al +34 612345678 o al 918273645 para confirmar."
    anon, mapping = anonymizer.anonymize(text)
    
    assert "[TELEFONO_1]" in anon
    assert "[TELEFONO_2]" in anon
    assert "+34 612345678" in mapping.values() or "612345678" in mapping.values()
    assert "918273645" in mapping.values()
    
    recovered = anonymizer.detokenize(anon, mapping)
    assert recovered == text

def test_anonymizer_iban():
    anonymizer = DataAnonymizer()
    text = "Mi cuenta es ES21 1465 0100 72 2030856251 y la de ahorro es ES9922223333444455556666"
    anon, mapping = anonymizer.anonymize(text)
    
    assert "[IBAN_1]" in anon
    assert "[IBAN_2]" in anon
    assert "ES21 1465 0100 72 2030856251" in mapping.values()
    assert "ES9922223333444455556666" in mapping.values()
    
    recovered = anonymizer.detokenize(anon, mapping)
    assert recovered == text

def test_anonymizer_names():
    anonymizer = DataAnonymizer()
    text = "Mi nombre es Juan Perez y soy amigo de Maria Rodriguez."
    anon, mapping = anonymizer.anonymize(text)
    
    assert "[NOMBRE_1]" in anon
    assert "[NOMBRE_2]" in anon
    
    recovered = anonymizer.detokenize(anon, mapping)
    assert recovered == text

def test_anonymizer_full_roundtrip():
    anonymizer = DataAnonymizer()
    text = (
        "Hola, me llamo Luis Domingo. Mi NIF es 44555666A y mi teléfono es +34 600111222. "
        "El importe a transferir al IBAN ES1234567890123456789012 es de 340,50€, por favor enviar confirmación a luis@correo.com."
    )
    anon, mapping = anonymizer.anonymize(text)
    
    assert "[NOMBRE_1]" in anon
    assert "[NIF_1]" in anon
    assert "[TELEFONO_1]" in anon
    assert "[IBAN_1]" in anon
    assert "[IMPORTE_1]" in anon
    assert "[EMAIL_1]" in anon
    
    recovered = anonymizer.detokenize(anon, mapping)
    assert recovered == text
