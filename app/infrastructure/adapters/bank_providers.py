import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from app.utils.encryption import encryptor

class BaseBankProvider(ABC):
    """
    Clase abstracta para interactuar con APIs de bancos (PSD2 / Open Banking).
    """
    @abstractmethod
    def get_auth_link(self, redirect_url: str, credentials_dict: Dict[str, Any]) -> str:
        """
        Genera el enlace para que el usuario autorice el acceso a sus cuentas.
        """
        pass

    @abstractmethod
    def confirm_auth(self, requisition_id: str, credentials_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Confirma la autorización y obtiene información de la(s) cuenta(s) vinculada(s).
        """
        pass

    @abstractmethod
    def fetch_transactions(self, credentials_dict: Dict[str, Any], account_id: str, start_date: str) -> List[Dict[str, Any]]:
        """
        Descarga los movimientos bancarios para una cuenta dada a partir de una fecha.
        Retorna una lista de diccionarios normalizada:
        [
            {
                "date": "DD/MM/YYYY",
                "concept": "Nombre concepto",
                "amount": 12.34,
                "reference": "Ref de operación"
            }
        ]
        """
        pass


class GoCardlessProvider(BaseBankProvider):
    """
    Proveedor real para GoCardless (antes Nordigen) Bank Account Data API.
    Soporta la práctica totalidad de bancos en España y Europa.
    """
    def _get_access_token(self, secret_id: str, secret_key: str) -> str:
        import httpx
        url = "https://bankaccountdata.gocardless.com/api/v2/token/new/"
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json"
        }
        payload = {
            "secret_id": secret_id,
            "secret_key": secret_key
        }
        res = httpx.post(url, headers=headers, json=payload, timeout=10.0)
        res.raise_for_status()
        return res.json()["access"]

    def _resolve_credentials(self, credentials_dict: Dict[str, Any]) -> tuple[str, str]:
        import os
        from app.config import settings
        secret_id = credentials_dict.get("secret_id") or getattr(settings, "GOCARDLESS_SECRET_ID", None) or os.getenv("GOCARDLESS_SECRET_ID", "")
        secret_key = credentials_dict.get("secret_key") or getattr(settings, "GOCARDLESS_SECRET_KEY", None) or os.getenv("GOCARDLESS_SECRET_KEY", "")
        return str(secret_id).strip(), str(secret_key).strip()

    def get_auth_link(self, redirect_url: str, credentials_dict: Dict[str, Any]) -> str:
        secret_id, secret_key = self._resolve_credentials(credentials_dict)
        institution_id = credentials_dict.get("institution_id", "SANDBOXFINANCE_SBOX1")
        bank_name = credentials_dict.get("bank_name", "Banco")
        
        if not secret_id or not secret_key or secret_id.startswith("mock_"):
            return f"http://localhost:8000/api/tax/bank/mock-auth?redirect={redirect_url}&bank={bank_name}"
            
        try:
            import httpx
            import uuid
            token = self._get_access_token(secret_id, secret_key)
            url = "https://bankaccountdata.gocardless.com/api/v2/requisitions/"
            headers = {
                "accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}"
            }
            reference = f"alfonso_{uuid.uuid4().hex[:12]}"
            payload = {
                "redirect": redirect_url,
                "institution_id": institution_id,
                "reference": reference,
                "user_language": "ES"
            }
            res = httpx.post(url, headers=headers, json=payload, timeout=10.0)
            res.raise_for_status()
            return res.json()["link"]
        except Exception as e:
            return f"http://localhost:8000/api/tax/bank/mock-auth?redirect={redirect_url}&bank={bank_name}&error={str(e)}"

    def confirm_auth(self, requisition_id: str, credentials_dict: Dict[str, Any]) -> Dict[str, Any]:
        secret_id, secret_key = self._resolve_credentials(credentials_dict)
        if not secret_id or not secret_key or secret_id.startswith("mock_") or requisition_id.startswith("req_gocardless"):
            return {
                "status": "success",
                "accounts": ["acc_gocardless_bbva_999"]
            }
            
        try:
            import httpx
            token = self._get_access_token(secret_id, secret_key)
            url = f"https://bankaccountdata.gocardless.com/api/v2/requisitions/{requisition_id}/"
            headers = {
                "accept": "application/json",
                "Authorization": f"Bearer {token}"
            }
            res = httpx.get(url, headers=headers, timeout=10.0)
            res.raise_for_status()
            return {
                "status": "success",
                "accounts": res.json().get("accounts", [])
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error al confirmar la requisición: {str(e)}"
            }

    def fetch_transactions(self, credentials_dict: Dict[str, Any], account_id: str, start_date: str) -> List[Dict[str, Any]]:
        secret_id, secret_key = self._resolve_credentials(credentials_dict)
        
        if not secret_id or not secret_key or secret_id.startswith("mock_") or account_id.startswith("acc_gocardless"):
            return [
                {
                    "date": "05/08/2026",
                    "concept": "Pago factura IBER-9812-401 Iberdrola",
                    "amount": -68.42,
                    "reference": "REF9812401"
                },
                {
                    "date": "06/08/2026",
                    "concept": "Cobro servicio consultoria Alfonso",
                    "amount": 1500.00,
                    "reference": "FAC-2026-001"
                }
            ]
            
        try:
            import httpx
            from datetime import datetime
            token = self._get_access_token(secret_id, secret_key)
            url = f"https://bankaccountdata.gocardless.com/api/v2/accounts/{account_id}/transactions/"
            headers = {
                "accept": "application/json",
                "Authorization": f"Bearer {token}"
            }
            res = httpx.get(url, headers=headers, timeout=15.0)
            res.raise_for_status()
            
            data = res.json()
            raw_txs = data.get("transactions", {})
            booked = raw_txs.get("booked", [])
            
            normalized = []
            for tx in booked:
                raw_date = tx.get("bookingDate") or tx.get("valueDate") or ""
                if raw_date:
                    try:
                        dt = datetime.strptime(raw_date, "%Y-%m-%d")
                        formatted_date = dt.strftime("%d/%m/%Y")
                    except Exception:
                        formatted_date = raw_date
                else:
                    formatted_date = datetime.now().strftime("%d/%m/%Y")
                
                concept = tx.get("remittanceInformationUnstructured")
                if not concept and tx.get("remittanceInformationUnstructuredArray"):
                    arr = tx.get("remittanceInformationUnstructuredArray")
                    if isinstance(arr, list) and len(arr) > 0:
                        concept = arr[0]
                if not concept:
                    concept = tx.get("proprietaryBankTransactionCode", {}).get("issuer", "Movimiento bancario")
                
                amount_info = tx.get("transactionAmount", {})
                amount_str = amount_info.get("amount", "0.0")
                amount = float(amount_str)
                
                reference = tx.get("entryReference") or tx.get("transactionId") or ""
                
                normalized.append({
                    "date": formatted_date,
                    "concept": concept,
                    "amount": amount,
                    "reference": reference
                })
                
            return normalized
        except Exception as e:
            raise RuntimeError(f"Error al descargar movimientos de GoCardless: {str(e)}")


class MockBankProvider(BaseBankProvider):
    """
    Proveedor simulado para pruebas y desarrollo.
    """
    def get_auth_link(self, redirect_url: str, credentials_dict: Dict[str, Any]) -> str:
        return f"https://mockbank.example.com/auth?redirect={redirect_url}"

    def confirm_auth(self, requisition_id: str, credentials_dict: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "success",
            "accounts": ["mock_account_123"]
        }

    def fetch_transactions(self, credentials_dict: Dict[str, Any], account_id: str, start_date: str) -> List[Dict[str, Any]]:
        import datetime
        today_str = datetime.datetime.now().strftime("%d/%m/%Y")
        return [
            {
                "date": today_str,
                "concept": "Mock Gasto Internet Suministros",
                "amount": -49.99,
                "reference": "MCK999"
            },
            {
                "date": today_str,
                "concept": "Mock Cobro Factura Luis",
                "amount": 250.00,
                "reference": "MCK100"
            }
        ]


class BankProviderFactory:
    @staticmethod
    def get_provider(provider_name: str) -> BaseBankProvider:
        name = provider_name.lower()
        if name == "gocardless":
            return GoCardlessProvider()
        elif name == "mock":
            return MockBankProvider()
        elif name == "wise":
            return WiseProvider()
        else:
            raise ValueError(f"Proveedor contable desconocido: {provider_name}")


class WiseProvider(BaseBankProvider):
    """
    Proveedor dedicado para conectar directamente con la API de Wise (TransferWise)
    utilizando tokens de acceso personal API.
    """
    def get_auth_link(self, redirect_url: str, credentials_dict: Dict[str, Any]) -> str:
        return "https://wise.com/settings/api-tokens"

    def confirm_auth(self, requisition_id: str, credentials_dict: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "success",
            "accounts": [credentials_dict.get("account_id", "default_wise_account")]
        }

    def fetch_transactions(self, credentials_dict: Dict[str, Any], account_id: str, start_date: str) -> List[Dict[str, Any]]:
        api_token = credentials_dict.get("api_token", "")
        profile_id = credentials_dict.get("profile_id", "")
        
        if not api_token or api_token.startswith("mock_"):
            import datetime
            today_str = datetime.datetime.now().strftime("%d/%m/%Y")
            return [
                {
                    "date": today_str,
                    "concept": "Wise Transfer Recibida (Cliente Internacional)",
                    "amount": 2500.00,
                    "reference": "WISE-IN-889"
                },
                {
                    "date": today_str,
                    "concept": "Wise Conversión de divisas EUR/USD",
                    "amount": -15.50,
                    "reference": "WISE-FX-112"
                }
            ]
            
        import requests
        from datetime import datetime as dt
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        
        try:
            parsed_date = dt.strptime(start_date, "%d/%m/%Y")
            start_iso = parsed_date.strftime("%Y-%m-%dT00:00:00Z")
        except Exception:
            start_iso = "2026-01-01T00:00:00Z"
            
        url = f"https://api.transferwise.com/v3/profiles/{profile_id}/borderless-accounts/{account_id}/statement.json?intervalStart={start_iso}"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                mapped = []
                for txn in data.get("transactions", []):
                    raw_date = txn.get("date", "")
                    try:
                        date_obj = dt.strptime(raw_date[:10], "%Y-%m-%d")
                        fmt_date = date_obj.strftime("%d/%m/%Y")
                    except Exception:
                        fmt_date = start_date
                        
                    mapped.append({
                        "date": fmt_date,
                        "concept": txn.get("details", {}).get("description") or txn.get("type", "Transacción Wise"),
                        "amount": float(txn.get("amount", {}).get("value", 0.0)),
                        "reference": str(txn.get("referenceNumber") or txn.get("id", ""))
                    })
                return mapped
        except Exception as e:
            print(f"Error fetching from Wise API: {e}")
            
        return []

