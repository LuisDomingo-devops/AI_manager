import pytest
import re
from app.utils.anonymizer import DataAnonymizer

# 50 casos de prueba fiscales sintéticos con identificadores españoles reales
SPANISH_FISCAL_CORPUS = [
    f"Factura emitida por Juan Pérez {i} con NIF {10000000+i}{'TRWAGMYFPDXBNJZSQVHLCKE'[(10000000+i)%23]} por importe de {i * 100},00 € con IBAN ES6621000418401234567891 a Calle Sol {i}, 2800{i%10}."
    for i in range(1, 51)
]

def test_qa_50_spanish_invoices_anonymization_completeness():
    anonymizer = DataAnonymizer()
    nif_regex = re.compile(r'\b\d{8}[TRWAGMYFPDXBNJZSQVHLCKE]\b')
    iban_regex = re.compile(r'\bES\d{22}\b')

    for raw_invoice in SPANISH_FISCAL_CORPUS:
        anon_text, mapping = anonymizer.anonymize(raw_invoice)

        # 1. Comprobar que ningún NIF real sobrevive en el texto anonimizado
        assert not nif_regex.search(anon_text), f"Fuga de NIF en: {anon_text}"

        # 2. Comprobar que ningún IBAN real sobrevive
        assert not iban_regex.search(anon_text), f"Fuga de IBAN en: {anon_text}"

        # 3. Comprobar que la desanonimización es 100% fiel al original
        restored = anonymizer.detokenize(anon_text, mapping)
        assert restored == raw_invoice
