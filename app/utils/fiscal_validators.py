import re
from typing import Tuple, Optional, List

# Tabla oficial módulo 23 para NIF y NIE
NIF_CONTROL_CHARS = "TRWAGMYFPDXBNJZSQVHLCKE"

# Tipos de entidad CIF
CIF_LETTER_MAP = {
    'A': 'NUMERIC', 'B': 'NUMERIC', 'C': 'NUMERIC', 'D': 'NUMERIC', 'E': 'NUMERIC',
    'F': 'NUMERIC', 'G': 'NUMERIC', 'H': 'NUMERIC', 'J': 'NUMERIC', 'U': 'NUMERIC', 'V': 'NUMERIC',
    'P': 'LETTER', 'Q': 'LETTER', 'S': 'LETTER', 'R': 'LETTER', 'W': 'LETTER', 'N': 'LETTER', 'K': 'LETTER'
}
CIF_CONTROL_LETTERS = "JABCDEFGHI"

def clean_alphanumeric(value: str) -> str:
    """Elimina puntos, guiones y espacios en blanco."""
    if not value:
        return ""
    return re.sub(r'[\s\.\-_]', '', value).strip().upper()

def validate_nif(nif: str) -> bool:
    """
    Valida un NIF español de persona física.
    8 dígitos + 1 letra correspondiente a (dígitos % 23).
    """
    cleaned = clean_alphanumeric(nif)
    if len(cleaned) != 9:
        return False

    digits_part = cleaned[:8]
    control_char = cleaned[8]

    if not digits_part.isdigit() or not control_char.isalpha():
        return False

    expected_char = NIF_CONTROL_CHARS[int(digits_part) % 23]
    return control_char == expected_char

def validate_nie(nie: str) -> bool:
    """
    Valida un NIE de residente extranjero (X, Y o Z seguido de 7 dígitos y letra de control).
    X se convierte a 0, Y a 1 y Z a 2 para el cálculo módulo 23.
    """
    cleaned = clean_alphanumeric(nie)
    if len(cleaned) != 9:
        return False

    prefix = cleaned[0]
    digits_part = cleaned[1:8]
    control_char = cleaned[8]

    if prefix not in ('X', 'Y', 'Z') or not digits_part.isdigit() or not control_char.isalpha():
        return False

    prefix_num = {'X': '0', 'Y': '1', 'Z': '2'}[prefix]
    full_digits = prefix_num + digits_part

    expected_char = NIF_CONTROL_CHARS[int(full_digits) % 23]
    return control_char == expected_char

def validate_cif(cif: str) -> bool:
    """
    Valida un CIF de persona jurídica española.
    1 letra de entidad + 7 dígitos + 1 carácter de control (dígito o letra).
    """
    cleaned = clean_alphanumeric(cif)
    if len(cleaned) != 9:
        return False

    first_letter = cleaned[0]
    central_digits = cleaned[1:8]
    control_code = cleaned[8]

    if first_letter not in CIF_LETTER_MAP and first_letter not in ('A','B','C','D','E','F','G','H','J','N','P','Q','R','S','U','V','W'):
        return False

    if not central_digits.isdigit():
        return False

    # Algoritmo de control CIF
    even_sum = int(central_digits[1]) + int(central_digits[3]) + int(central_digits[5])
    odd_sum = 0
    for idx in (0, 2, 4, 6):
        doubled = int(central_digits[idx]) * 2
        odd_sum += (doubled // 10) + (doubled % 10)

    total_sum = even_sum + odd_sum
    control_digit = (10 - (total_sum % 10)) % 10

    expected_letter = CIF_CONTROL_LETTERS[control_digit]

    rule = CIF_LETTER_MAP.get(first_letter, 'BOTH')
    if rule == 'NUMERIC':
        return control_code == str(control_digit)
    elif rule == 'LETTER':
        return control_code == expected_letter
    else: # Ambos admitidos
        return control_code == str(control_digit) or control_code == expected_letter

def is_valid_spanish_id(value: str) -> Tuple[Optional[str], bool]:
    """
    Determina si un identificador es un NIF, NIE o CIF válido según su algoritmo.
    Retorna (tipo, es_valido).
    """
    cleaned = clean_alphanumeric(value)
    if not cleaned or len(cleaned) != 9:
        return None, False

    if cleaned[0] in ('X', 'Y', 'Z'):
        if validate_nie(cleaned):
            return "NIE", True
        return None, False

    if cleaned[0].isalpha():
        if validate_cif(cleaned):
            return "CIF", True
        return None, False

    if cleaned[:8].isdigit() and cleaned[8].isalpha():
        if validate_nif(cleaned):
            return "NIF", True
        return None, False

    return None, False

def validate_iban(iban: str) -> bool:
    """
    Valida un IBAN internacional o español según la norma ISO 7064 Módulo 97-10.
    """
    cleaned = clean_alphanumeric(iban)
    if len(cleaned) < 15 or len(cleaned) > 34:
        return False

    country = cleaned[:2]
    if not country.isalpha():
        return False

    # Para España debe tener 24 caracteres exactamente
    if country == "ES" and len(cleaned) != 24:
        return False

    # Reordenar IBAN: mover los 4 primeros caracteres al final
    reordered = cleaned[4:] + cleaned[:4]

    # Convertir letras a números (A=10 ... Z=35)
    numeric_str = []
    for ch in reordered:
        if ch.isdigit():
            numeric_str.append(ch)
        elif ch.isalpha():
            numeric_str.append(str(ord(ch) - ord('A') + 10))
        else:
            return False

    # Calcular módulo 97 sobre el número entero largo
    try:
        mod = int("".join(numeric_str)) % 97
        return mod == 1
    except ValueError:
        return False

def validate_spanish_ccc(bank: str, branch: str, control: str, account: str) -> bool:
    """Valida los dígitos de control del Código Cuenta Cliente (CCC) español."""
    if len(bank) != 4 or len(branch) != 4 or len(control) != 2 or len(account) != 10:
        return False
    weights_first = [4, 8, 5, 10, 9, 7, 3, 6]
    weights_second = [1, 2, 4, 8, 5, 10, 9, 7, 3, 6]

    s1 = sum(int(d) * w for d, w in zip(bank + branch, weights_first))
    c1 = 11 - (s1 % 11)
    c1 = 0 if c1 == 11 else (1 if c1 == 10 else c1)

    s2 = sum(int(d) * w for d, w in zip(account, weights_second))
    c2 = 11 - (s2 % 11)
    c2 = 0 if c2 == 11 else (1 if c2 == 10 else c2)

    return control == f"{c1}{c2}"

# Regex estricto de cantidades monetarias (evita años como 2026 o números de factura)
AMOUNT_CONTEXT_REGEX = re.compile(
    r'(?<![A-Za-z0-9\-_])'
    r'('
    r'\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?\s*(?:€|\b(?:EUR|euros?)\b)|'
    r'(?:€|\b(?:EUR|euros?)\b)\s*\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?'
    r')',
    re.IGNORECASE
)

def extract_amounts_with_context(text: str) -> List[Tuple[str, str]]:
    """
    Extrae cantidades monetarias requiriendo obligatoriamente contexto monetario (€, EUR, euros)
    para evitar falsos positivos con años fiscales (ej. 2026) o identificadores numéricos.
    Retorna lista de (valor_limpio, valor_crudo).
    """
    results = []
    if not text:
        return results

    for match in AMOUNT_CONTEXT_REGEX.finditer(text):
        raw = match.group(1).strip()
        results.append((raw, raw))
    return results
