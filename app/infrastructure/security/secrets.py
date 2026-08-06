import keyring

NAMESPACE = "AlfonsoAutonomo"

def set_secret(key: str, value: str) -> None:
    """Guarda un secreto en el almacenamiento seguro de credenciales del sistema."""
    keyring.set_password(NAMESPACE, key, value)

def get_secret(key: str) -> str:
    """Recupera un secreto del almacenamiento seguro. Retorna cadena vacía si no existe."""
    val = keyring.get_password(NAMESPACE, key)
    return val if val is not None else ""
