import re

def validate_nif_nie_cif(doc: str) -> bool:
    """
    Valida si un NIF, NIE o CIF español es válido formalmente.
    """
    doc = doc.strip().upper()
    if not doc or len(doc) != 9:
        return False

    # 1. NIF/NIE (Personas Físicas)
    # NIF estándar: 8 dígitos + letra
    # NIE: X, Y o Z + 7 dígitos + letra
    # Especiales: K, L o M + 7 dígitos + letra
    nif_nie_pattern = re.compile(r'^[XYZKLM\d]\d{7}[A-Z]$')
    if nif_nie_pattern.match(doc):
        calc_doc = doc
        if calc_doc[0] == 'X':
            calc_doc = '0' + calc_doc[1:]
        elif calc_doc[0] == 'Y':
            calc_doc = '1' + calc_doc[1:]
        elif calc_doc[0] == 'Z':
            calc_doc = '2' + calc_doc[1:]
        elif calc_doc[0] in ('K', 'L', 'M'):
            # Los especiales se calculan omitiendo la primera letra
            calc_doc = calc_doc[1:]
        
        try:
            num = int(calc_doc[:-1])
            letters = "TRWAGMYFPDXBNJZSQVHLCKE"
            correct_letter = letters[num % 23]
            return doc[-1] == correct_letter
        except ValueError:
            return False

    # 2. CIF (Personas Jurídicas)
    # CIF estándar: Letra + 7 dígitos + Control (letra o dígito)
    cif_pattern = re.compile(r'^[ABCDEFGHJNPQRSTUVW]\d{7}[A-J\d]$')
    if cif_pattern.match(doc):
        first_letter = doc[0]
        digits = [int(d) for d in doc[1:8]]
        control = doc[8]

        even_sum = sum(digits[1::2]) # posiciones pares del bloque de 7 dígitos (índices 1, 3, 5)
        odd_sum = 0
        for d in digits[0::2]: # posiciones impares (índices 0, 2, 4, 6)
            prod = d * 2
            odd_sum += (prod // 10) + (prod % 10)

        total = even_sum + odd_sum
        last_digit_total = total % 10
        control_value = 0 if last_digit_total == 0 else 10 - last_digit_total

        # Control esperado en base al tipo de entidad (primera letra)
        # Letra obligatoria para N, P, Q, R, S, W
        if first_letter in "NPQRSW":
            letter_control = "JABCDEFGHI"[control_value]
            return control == letter_control
        # Dígito obligatorio para A, B, E, H
        elif first_letter in "ABEH":
            return control == str(control_value)
        # Para el resto (C, D, F, G, J, U, V) se permite letra o dígito
        else:
            letter_control = "JABCDEFGHI"[control_value]
            return control == str(control_value) or control == letter_control

    return False
