"""
Excepciones tipadas del dominio e infraestructura para Alfonso AI Konta.
Estandarizadas para erradicar el antipatrón de captura ciega de Exception.
"""

class AlfonsoBaseException(Exception):
    """Excepción raíz del sistema Alfonso AI Konta."""
    def __init__(self, message: str = "", details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

class InfrastructureError(AlfonsoBaseException):
    """Errores de infraestructura subyacente (I/O, SO, librerías)."""
    pass

class DatabasePersistenceError(InfrastructureError):
    """Errores durante operaciones de base de datos o repositorios SQL."""
    def __init__(self, message: str = "", operation: str = "", table: str = "", details: dict | None = None):
        super().__init__(message, details)
        self.operation = operation
        self.table = table

class CryptographicOperationError(InfrastructureError):
    """Errores en cifrado, descifrado o rotación de claves criptográficas."""
    def __init__(self, message: str = "", key_id: str = "", context: str = "", details: dict | None = None):
        super().__init__(message, details)
        self.key_id = key_id
        self.context = context

class RegulatoryAuditError(AlfonsoBaseException):
    """Errores críticos de auditoría contable o trazabilidad Veri*Factu / RGPD."""
    def __init__(self, message: str = "", event_type: str = "", entity_id: str = "", details: dict | None = None):
        super().__init__(message, details)
        self.event_type = event_type
        self.entity_id = entity_id

class HardwareFingerprintError(InfrastructureError):
    """Errores en la resolución de identificadores de hardware para licenciamiento."""
    def __init__(self, message: str = "", source: str = "", details: dict | None = None):
        super().__init__(message, details)
        self.source = source

class ExternalProviderError(InfrastructureError):
    """Errores al interactuar con servicios externos (Nordigen, RedSys, Gemini, Gmail)."""
    def __init__(self, message: str = "", provider_name: str = "", status_code: int | None = None, details: dict | None = None):
        super().__init__(message, details)
        self.provider_name = provider_name
        self.status_code = status_code

class DomainError(AlfonsoBaseException):
    """Errores de lógica de negocio o validación de dominio."""
    pass

class InvoiceValidationError(DomainError):
    """Errores en la validación de una factura."""
    pass

class XSDValidationError(InvoiceValidationError):
    """Errores al validar el documento XML contra el esquema verifactu.xsd."""
    def __init__(self, message: str = "", errors: list | None = None, details: dict | None = None):
        super().__init__(message, details)
        self.errors = errors or []

class InvoiceNumberGapError(DomainError):
    """Error al detectar o prevenir un hueco en la serie correlativa de facturación."""
    pass

class ApprovalRequiredError(DomainError):
    """Excepción lanzada cuando una operación crítica se suspende a la espera de confirmación humana."""
    def __init__(self, message: str = "", approval_id: str = "", action_type: str = "", details: dict | None = None):
        super().__init__(message, details)
        self.approval_id = approval_id
        self.action_type = action_type

class TaxCalculationError(DomainError):
    """Errores durante el cálculo de modelos tributarios oficiales (303, 130, etc.)."""
    pass

class BankStatementParseError(DomainError):
    """Errores al parsear extractos Norma 43 o CSV bancarios."""
    pass

class BankConnectionUnavailableError(ExternalProviderError):
    """Lanzada cuando un banco no tiene token o las credenciales han expirado (sin datos simulados)."""
    pass

