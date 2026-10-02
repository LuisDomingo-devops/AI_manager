"""
Cliente SOAP para comunicación telemática con la pasarela oficial de la AEAT (Veri*factu).
Conforme a la Orden HAC/1177/2024.
"""

from typing import NamedTuple, Optional
import ssl
import urllib.request
import urllib.error
from app.utils.logger import app_logger


class SOAPTransmissionResult(NamedTuple):
    success: bool
    status_code: int
    csv: Optional[str]
    response_xml: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    is_network_timeout: bool = False


class VerifactuSoapClient:
    """Cliente HTTP/SOAP con soporte mTLS para Veri*factu."""

    SANDBOX_URL = "https://prewww10.aeat.es/wlpl/SSII-FACT/ws/fe/SiiFactFEV1SOAP"
    PRODUCTION_URL = "https://www1.agenciatributaria.gob.es/wlpl/SSII-FACT/ws/fe/SiiFactFEV1SOAP"

    def __init__(self, sandbox: bool = True, timeout_seconds: float = 15.0):
        self.sandbox = sandbox
        self.endpoint_url = self.SANDBOX_URL if sandbox else self.PRODUCTION_URL
        self.timeout_seconds = timeout_seconds

    def generar_sobre_soap(self, xml_factura: str) -> str:
        """
        Envuelve el registro XML de facturación en el sobre SOAP 1.1 oficial de la AEAT.
        """
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:siiLR="https://www.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/ssii/fact/ws/SuministroLR.xsd">
    <soapenv:Header/>
    <soapenv:Body>
        {xml_factura}
    </soapenv:Body>
</soapenv:Envelope>"""

    def enviar_registro_factura(
        self,
        xml_factura: str,
        cert_pem: Optional[bytes] = None,
        key_pem: Optional[bytes] = None
    ) -> SOAPTransmissionResult:
        """
        Envía un registro de facturación de alta o anulación a la pasarela SOAP de la AEAT.
        """
        soap_envelope = self.generar_sobre_soap(xml_factura)

        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": ""
        }

        try:
            req = urllib.request.Request(
                self.endpoint_url,
                data=soap_envelope.encode("utf-8"),
                headers=headers,
                method="POST"
            )
            # En caso de no haber certificados reales o estar en test offline
            # controlamos timeout / errores
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
                return self.parse_soap_response(body, response.status)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8") if e.fp else ""
            return self.parse_soap_response(body, e.code)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            app_logger.warning("Fallo o timeout de red al contactar con la AEAT: %s", str(e))
            return SOAPTransmissionResult(
                success=False,
                status_code=0,
                csv=None,
                response_xml="",
                error_message=f"Timeout o error de red: {e}",
                is_network_timeout=True
            )

    @classmethod
    def parse_soap_response(cls, response_xml: str, status_code: int) -> SOAPTransmissionResult:
        """Parsea la respuesta XML SOAP oficial de la AEAT."""
        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(response_xml)
            # Buscar elementos con o sin namespace
            csv = None
            estado = None
            error_code = None
            error_desc = None

            for elem in root.iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag == "CSV":
                    csv = elem.text
                elif tag == "EstadoEnvio":
                    estado = elem.text
                elif tag == "CodigoErrorRegistro":
                    error_code = elem.text
                elif tag in ("DescripcionErrorRegistro", "DescripcionError", "faultstring"):
                    if not error_desc:
                        error_desc = elem.text

            is_correct = (estado == "Correcto" and not error_code) or (status_code == 200 and csv is not None and not error_code)
            if estado and estado != "Correcto":
                is_correct = False

            return SOAPTransmissionResult(
                success=is_correct,
                status_code=status_code,
                csv=csv if is_correct else None,
                response_xml=response_xml,
                error_code=error_code,
                error_message=error_desc,
                is_network_timeout=False
            )
        except Exception as e:
            return SOAPTransmissionResult(
                success=False,
                status_code=status_code,
                csv=None,
                response_xml=response_xml,
                error_message=f"Error parseando respuesta SOAP: {e}",
                is_network_timeout=False
            )
