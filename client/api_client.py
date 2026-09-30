"""Cliente de API Local Estandarizado para GUI PyQt6.

Implementa el contrato OpenAPI formal y soporta transporte HTTP real hacia
127.0.0.1 o transporte en memoria (TestClient/in-memory) para tests deterministas.
"""

from typing import Any, Dict, Optional
import httpx


class LocalApiClient:
    """Cliente estandarizado de la aplicación de escritorio para el backend local."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        api_key: Optional[str] = None,
        session_token: Optional[str] = None,
        client_session: Optional[Any] = None,
    ):
        self.base_url = base_url.rstrip("/")
        if not api_key:
            try:
                from app.config import settings
                api_key = settings.ALFONSO_API_KEY
            except Exception:
                api_key = "test_key"
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": api_key or "test_key",
            "X-Session-Token": session_token or "",
            "X-Client-ID": "default",
        }
        self.client_session = client_session

    def _post(self, path: str, json: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        if self.client_session is not None:
            res = self.client_session.post(path, json=json, headers=self.headers)
            res.raise_for_status()
            return res.json()
        with httpx.Client(headers=self.headers, timeout=15.0) as client:
            res = client.post(url, json=json)
            res.raise_for_status()
            return res.json()

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        if self.client_session is not None:
            res = self.client_session.get(path, params=params, headers=self.headers)
            res.raise_for_status()
            return res.json()
        with httpx.Client(headers=self.headers, timeout=15.0) as client:
            res = client.get(url, params=params)
            res.raise_for_status()
            return res.json()

    def issue_legal_invoice(
        self, client_name: str, client_nif: str, amount: float, concept: str, iva_rate: float = 21.0
    ) -> Dict[str, Any]:
        """Emite una factura legal oficial."""
        payload = {
            "client_name": client_name,
            "client_nif": client_nif,
            "amount": amount,
            "concept": concept,
            "iva_rate": iva_rate,
        }
        return self._post("/api/v1/billing/invoices/legal/issue", json=payload)

    def get_invoices(self, year: Optional[int] = None) -> Dict[str, Any]:
        """Recupera el listado de facturas."""
        params = {"year": year} if year else None
        return self._get("/api/v1/billing/invoices", params=params)
