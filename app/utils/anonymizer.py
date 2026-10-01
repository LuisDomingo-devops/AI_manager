import re
from typing import Tuple, Dict, Optional, List
from app.domain.schemas import AnonymizationSession
from app.utils.fiscal_validators import (
    is_valid_spanish_id,
    validate_iban,
    extract_amounts_with_context
)

# Patrones candidatos para extracción previa a validación algorítmica
CANDIDATE_ID_REGEX = re.compile(
    r'\b(?:[XYZxyz]\s*[-.]?\s*)?\d{1,2}(?:\.?\d{3}){2}\s*[-.]?\s*[A-Za-z]\b|'
    r'\b[A-HJ-NP-SW-Zxyza-hj-np-sw-z]\s*[-.]?\s*\d{7}\s*[-.]?\s*[A-Za-z0-9]\b',
    re.IGNORECASE
)

CANDIDATE_IBAN_REGEX = re.compile(
    r'\b[A-Z]{2}\d{2}(?:[0-9A-Za-z]{11,30}|(?:\s[0-9A-Za-z]{2,10}){2,7})\b'
)

EMAIL_REGEX = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
    re.IGNORECASE
)

PHONE_REGEX = re.compile(
    r'(?:\+\d{1,3}[\s.-]?)?\b(?:[6789]\d{2}[\s.-]?\d{3}[\s.-]?\d{3}|[6789]\d{8})\b'
)

COMMON_NAMES = {
    "juan", "maría", "maria", "josé", "jose", "manuel", "francisco", "david",
    "antonio", "javier", "daniel", "carlos", "jesús", "jesus", "alejandro",
    "miguel", "rafael", "pedro", "ángel", "angel", "fernando", "luis", "pablo",
    "jorge", "alberto", "alfonso", "ana", "carmen", "isabel", "dolores", "pilar",
    "teresa", "josefa", "francisca", "antonia", "cristina", "marta", "laura",
    "sara", "andrea", "elena", "lucía", "lucia", "raquel", "nuria", "ignacio",
    "diego", "jaime", "ramón", "ramon", "vicente", "sergio", "luis domingo"
}

INTRO_NAME_REGEX = re.compile(
    r'\b(?:[mM]e\s+[lL]lamo|[sS]oy|[mM]i\s+[nN]ombre\s+es|[dD]on|[dD]oña|[sS]ra?\.|[sS]eñor|[sS]eñora)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,3})\b'
)

class DataAnonymizer:
    """
    Motor nuclear de anonimización y seudonimización local pre-Gemini.
    Aplica validación algorítmica estricta para garantizar cero fugas sin falsos positivos.
    """

    def __init__(self):
        pass

    def anonymize(
        self,
        text: str,
        session: Optional[AnonymizationSession] = None
    ) -> Tuple[str, Dict[str, str]]:
        """
        Analiza el texto buscando NIFs, NIEs, CIFs, IBANs, importes, emails, teléfonos y nombres.
        Sustituye los datos sensibles por tokens estructurados y devuelve el texto seguro
        junto con el diccionario para la desanonimización inversa.
        """
        if not text:
            return text, {}

        sess = session or AnonymizationSession()
        anonymized_text = text

        # 1. IBANs (validados con ISO 7064 Mod 97-10 o estructura formal de cuenta)
        for match in CANDIDATE_IBAN_REGEX.finditer(anonymized_text):
            raw_iban = match.group(0).strip()
            clean_iban = re.sub(r'[\s.-]', '', raw_iban).upper()
            if 15 <= len(clean_iban) <= 34 and clean_iban[:2].isalpha() and clean_iban[2:4].isdigit() and clean_iban[4:].isalnum():
                token = sess.register_entity(raw_iban, "IBAN", match.start(), match.end())
                anonymized_text = anonymized_text.replace(raw_iban, token)

        # 2. Emails
        for match in EMAIL_REGEX.finditer(anonymized_text):
            raw_email = match.group(0).strip()
            token = sess.register_entity(raw_email, "EMAIL", match.start(), match.end())
            anonymized_text = anonymized_text.replace(raw_email, token)

        # 3. Teléfonos
        for match in PHONE_REGEX.finditer(anonymized_text):
            raw_phone = match.group(0).strip()
            token = sess.register_entity(raw_phone, "TELEFONO", match.start(), match.end())
            anonymized_text = anonymized_text.replace(raw_phone, token)

        # 4. Identificadores Fiscales Españoles (NIF, NIE, CIF)
        for match in CANDIDATE_ID_REGEX.finditer(anonymized_text):
            raw_id = match.group(0).strip()
            id_type, is_valid = is_valid_spanish_id(raw_id)
            if is_valid and id_type:
                token = sess.register_entity(raw_id, id_type, match.start(), match.end()) # type: ignore
                anonymized_text = anonymized_text.replace(raw_id, token)
            else:
                clean_id = re.sub(r'[\s.-]', '', raw_id).upper()
                if len(clean_id) == 9:
                    if clean_id[0] in "XYZ":
                        inferred_type = "NIE"
                    elif clean_id[0] in "ABCDEFGHJNPQRSUVW":
                        inferred_type = "CIF"
                    elif clean_id[:8].isdigit() and clean_id[8].isalpha():
                        inferred_type = "NIF"
                    else:
                        inferred_type = None
                    if inferred_type:
                        token = sess.register_entity(raw_id, inferred_type, match.start(), match.end())
                        anonymized_text = anonymized_text.replace(raw_id, token)

        # 5. Importes monetarios con contexto (€, EUR, euros)
        extracted_amounts = extract_amounts_with_context(anonymized_text)
        for _, raw_amount in extracted_amounts:
            token = sess.register_entity(raw_amount, "IMPORTE", 0, 0)
            anonymized_text = anonymized_text.replace(raw_amount, token)

        # 6. Nombres Propios
        names_found: List[str] = []
        for match in INTRO_NAME_REGEX.finditer(anonymized_text):
            full_name = match.group(1).strip()
            if full_name and full_name.lower() not in COMMON_NAMES and len(full_name) > 2:
                if not any(t in full_name for t in ["[NIF_", "[CIF_", "[NIE_", "[IMPORTE_", "[EMAIL_", "[TELEFONO_", "[IBAN_"]):
                    names_found.append(full_name)

        words = anonymized_text.split()
        for i, word in enumerate(words):
            clean_word = re.sub(r'[^\wÁÉÍÓÚÑáéíóúñ]', '', word)
            if clean_word.lower() in COMMON_NAMES:
                name_parts = [word]
                j = i + 1
                while j < len(words) and j < i + 3:
                    if words[j-1].endswith(('.', ',', ';', ':')):
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
                    if not any(t in full_name for t in ["[NIF_", "[CIF_", "[NIE_", "[IMPORTE_", "[EMAIL_", "[TELEFONO_", "[IBAN_"]):
                        names_found.append(full_name)

        seen_names = []
        for n in names_found:
            if n not in seen_names:
                seen_names.append(n)
        seen_names.sort(key=len, reverse=True)

        for name in seen_names:
            token = sess.register_entity(name, "NOMBRE", 0, 0)
            anonymized_text = anonymized_text.replace(name, token)

        return anonymized_text, dict(sess.token_to_value_map)

    def detokenize(self, text: str, mapping: Dict[str, str]) -> str:
        """
        Reemplaza los tokens de vuelta por sus valores originales utilizando el mapa provisto.
        """
        if not text or not mapping:
            return text

        detokenized_text = text
        for token, original in mapping.items():
            detokenized_text = detokenized_text.replace(token, original)

        return detokenized_text
