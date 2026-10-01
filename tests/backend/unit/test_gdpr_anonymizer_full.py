import pytest
from app.utils.anonymizer import DataAnonymizer
from app.domain.schemas import AnonymizationSession

def test_anonymize_and_detokenize_bidirectional():
    anonymizer = DataAnonymizer()
    text = (
        "El cliente Juan Pérez con NIF 12345678Z debe transferir 1.500,00 € "
        "a la cuenta ES6621000418401234567891 antes del fin de mes."
    )
    anon_text, mapping = anonymizer.anonymize(text)

    # Verificar presencia de tokens y ausencia de datos en claro
    assert "[NIF_1]" in anon_text
    assert "[IBAN_1]" in anon_text
    assert "[IMPORTE_1]" in anon_text
    assert "[NOMBRE_1]" in anon_text
    assert "12345678Z" not in anon_text
    assert "ES6621000418401234567891" not in anon_text
    assert "1.500,00 €" not in anon_text
    assert "Juan Pérez" not in anon_text

    # Reconstrucción inversa
    restored = anonymizer.detokenize(anon_text, mapping)
    assert restored == text

def test_anonymize_reuse_tokens_for_same_entity():
    anonymizer = DataAnonymizer()
    text = "Juan Pérez emitió la factura. Juan Pérez confirmó el cobro con NIF 12345678Z y NIF 12345678Z."
    anon_text, mapping = anonymizer.anonymize(text)

    # El token [NOMBRE_1] debe reutilizarse para ambas menciones de Juan Pérez
    assert anon_text.count("[NOMBRE_1]") == 2
    assert "[NOMBRE_2]" not in anon_text

    # El token [NIF_1] debe reutilizarse para ambas menciones del NIF
    assert anon_text.count("[NIF_1]") == 2
    assert "[NIF_2]" not in anon_text

def test_anonymize_empty_and_no_sensitive_data():
    anonymizer = DataAnonymizer()
    assert anonymizer.anonymize("") == ("", {})
    clean_text = "El balance del ejercicio muestra resultados operativos normales."
    anon_text, mapping = anonymizer.anonymize(clean_text)
    assert anon_text == clean_text
    assert len(mapping) == 0
