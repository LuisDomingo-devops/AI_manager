import re

# Expresiones regulares robustas
# 1. NIF / NIE / CIF
NIF_REGEX = re.compile(
    r'\b(?:[XYZxyz]\s*-?\s*)?\d{1,2}(?:\.?\d{3}){2}\s*-?\s*[A-Za-z]\b|'  # DNI/NIE con/sin puntos/guiones
    r'\b[A-HJKNPQRSUVWxyza-hjknpqrsuvw]\s*-?\s*\d{7}\s*-?\s*[A-Za-z0-9]\b', # CIF con/sin puntos/guiones
    re.IGNORECASE
)

# 2. Importes y cantidades monetarias (e.g. 150€, 3.400,20 euros, EUR 50)
AMOUNT_REGEX = re.compile(
    r'\b\d{1,3}(?:\.\d{3})*(?:,\d{2})?\s*(?:€|euros?\b|EUR\b)|'
    r'(?:€|EUR)\s*\d{1,3}(?:\.\d{3})*(?:,\d{2})?\b',
    re.IGNORECASE
)

# 3. Emails
EMAIL_REGEX = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
    re.IGNORECASE
)

# 4. Teléfonos (españoles e internacionales)
PHONE_REGEX = re.compile(
    r'(?:\+\d{1,3}[-.\s]?)?\b(?:[6789]\d{2}[-.\s]?\d{3}[-.\s]?\d{3}|[6789]\d{8})\b'
)

# 5. IBAN / Cuentas Bancarias
IBAN_REGEX = re.compile(
    r'\b[A-Z]{2}\d{2}(?:\s*\d){20}\b|\b[A-Z]{2}\d{22}\b|\b[A-Z]{2}\d{2}[-.\s]?(?:\d{4}[-.\s]?){5}\d{4}\b',
    re.IGNORECASE
)

# 6. Nombres (Heurística e introducción de nombres comunes)
COMMON_NAMES = {
    "juan", "maría", "maria", "josé", "jose", "manuel", "francisco", "david",
    "antonio", "javier", "daniel", "carlos", "jesús", "jesus", "alejandro",
    "miguel", "rafael", "pedro", "ángel", "angel", "fernando", "luis", "pablo",
    "jorge", "alberto", "alfonso", "ana", "carmen", "isabel", "dolores", "pilar",
    "teresa", "josefa", "francisca", "antonia", "cristina", "marta", "laura",
    "sara", "andrea", "elena", "lucía", "lucia", "raquel", "nuria", "ignacio",
    "diego", "jaime", "ramón", "ramon", "vicente", "sergio", "luis domingo"
}

# Expresión regular para capturar nombres propios basados en palabras con mayúscula inicial
INTRO_NAME_REGEX = re.compile(
    r'\b(?:[mM]e\s+[lL]lamo|[sS]oy|[mM]i\s+[nN]ombre\s+es|[dD]on|[dD]oña|[sS]ra?\.|[sS]eñor|[sS]eñora)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,3})\b'
)

class DataAnonymizer:
    def __init__(self):
        pass

    def anonymize(self, text: str) -> tuple[str, dict[str, str]]:
        """
        Analiza el texto buscando NIFs, importes, nombres, emails, teléfonos e IBANs.
        Devuelve el texto anonimizado y un diccionario para realizar la de-tokenización inversa.
        """
        if not text:
            return text, {}

        mapping = {}
        anonymized_text = text

        # 1. Anonimizar IBANs
        ibans = IBAN_REGEX.findall(anonymized_text)
        seen_ibans = []
        for iban in ibans:
            if iban not in seen_ibans:
                seen_ibans.append(iban)
        for idx, iban in enumerate(seen_ibans, 1):
            token = f"[IBAN_{idx}]"
            mapping[token] = iban
            anonymized_text = re.sub(re.escape(iban), token, anonymized_text)

        # 2. Anonimizar Emails
        emails = EMAIL_REGEX.findall(anonymized_text)
        seen_emails = []
        for email in emails:
            if email not in seen_emails:
                seen_emails.append(email)
        for idx, email in enumerate(seen_emails, 1):
            token = f"[EMAIL_{idx}]"
            mapping[token] = email
            anonymized_text = re.sub(re.escape(email), token, anonymized_text)

        # 3. Anonimizar Teléfonos
        phones = PHONE_REGEX.findall(anonymized_text)
        seen_phones = []
        for phone in phones:
            if phone not in seen_phones:
                seen_phones.append(phone)
        for idx, phone in enumerate(seen_phones, 1):
            token = f"[TELEFONO_{idx}]"
            mapping[token] = phone
            anonymized_text = re.sub(re.escape(phone), token, anonymized_text)

        # 4. Anonimizar NIFs
        nifs = NIF_REGEX.findall(anonymized_text)
        seen_nifs = []
        for nif in nifs:
            if nif not in seen_nifs:
                seen_nifs.append(nif)
        
        for idx, nif in enumerate(seen_nifs, 1):
            token = f"[NIF_{idx}]"
            mapping[token] = nif
            anonymized_text = re.sub(re.escape(nif), token, anonymized_text)

        # 5. Anonimizar Importes
        amounts = AMOUNT_REGEX.findall(anonymized_text)
        seen_amounts = []
        for amt in amounts:
            if amt not in seen_amounts:
                seen_amounts.append(amt)

        for idx, amt in enumerate(seen_amounts, 1):
            token = f"[IMPORTE_{idx}]"
            mapping[token] = amt
            anonymized_text = re.sub(re.escape(amt), token, anonymized_text)

        # 6. Anonimizar Nombres
        names_found = []
        for match in INTRO_NAME_REGEX.finditer(anonymized_text):
            full_name = match.group(1).strip()
            if full_name and full_name.lower() not in COMMON_NAMES and len(full_name) > 2:
                if not any(token in full_name for token in ["[NIF_", "[IMPORTE_", "[EMAIL_", "[TELEFONO_", "[IBAN_"]):
                    names_found.append(full_name)

        words = anonymized_text.split()
        for i, word in enumerate(words):
            clean_word = re.sub(r'[^\wÁÉÍÓÚÑáéíóúñ]', '', word)
            if clean_word.lower() in COMMON_NAMES:
                name_parts = [word]
                j = i + 1
                while j < len(words) and j < i + 3:
                    if words[j-1].endswith('.') or words[j-1].endswith(',') or words[j-1].endswith(';') or words[j-1].endswith(':'):
                        break
                    next_word = words[j]
                    clean_next = re.sub(r'[^\wÁÉÍÓÚÑáéíóúñ]', '', next_word)
                    if clean_next and clean_next[0].isupper() and clean_next.lower() not in COMMON_NAMES:
                        name_parts.append(next_word)
                        j += 1
                    else:
                        break
                full_name = " ".join(name_parts)
                full_name = re.sub(r'[^\w\sÁÉÍÓÚÑáéíóúñ]$', '', full_name).strip()
                if full_name and len(full_name) > 2:
                    if not any(token in full_name for token in ["[NIF_", "[IMPORTE_", "[EMAIL_", "[TELEFONO_", "[IBAN_"]):
                        names_found.append(full_name)

        seen_names = []
        for name in names_found:
            if name not in seen_names:
                seen_names.append(name)
        seen_names.sort(key=len, reverse=True)

        for idx, name in enumerate(seen_names, 1):
            token = f"[NOMBRE_{idx}]"
            mapping[token] = name
            anonymized_text = re.sub(re.escape(name), token, anonymized_text)

        return anonymized_text, mapping

    def detokenize(self, text: str, mapping: dict[str, str]) -> str:
        """
        Reemplaza los tokens de vuelta por sus valores originales utilizando el mapa provisto.
        """
        if not text or not mapping:
            return text

        detokenized_text = text
        for token, original in mapping.items():
            detokenized_text = detokenized_text.replace(token, original)

        return detokenized_text
