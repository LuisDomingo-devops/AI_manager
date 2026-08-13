import pytest
from unittest.mock import patch, MagicMock
from app.adapters.bank_providers import GoCardlessProvider

def test_gocardless_auth_link_mock_fallback():
    provider = GoCardlessProvider()
    creds = {"secret_id": "mock_id", "secret_key": "mock_key"}
    link = provider.get_auth_link(redirect_url="http://redirect.com", credentials_dict=creds)
    assert "mock-auth" in link

@patch("httpx.post")
def test_gocardless_get_auth_link_real(mock_post):
    # Mocking JWT token generation
    mock_token_resp = MagicMock()
    mock_token_resp.json.return_value = {"access": "fake_access_token"}
    mock_token_resp.raise_for_status.return_value = None

    # Mocking Requisition creation
    mock_req_resp = MagicMock()
    mock_req_resp.json.return_value = {"link": "https://ob.gocardless.com/ob-link-xyz"}
    mock_req_resp.raise_for_status.return_value = None

    mock_post.side_effect = [mock_token_resp, mock_req_resp]

    provider = GoCardlessProvider()
    creds = {"secret_id": "real_id", "secret_key": "real_key", "institution_id": "BANK_ES"}
    
    link = provider.get_auth_link(redirect_url="http://redirect.com", credentials_dict=creds)
    assert link == "https://ob.gocardless.com/ob-link-xyz"
    assert mock_post.call_count == 2

@patch("httpx.post")
@patch("httpx.get")
def test_gocardless_confirm_auth(mock_get, mock_post):
    # Token mock
    mock_token_resp = MagicMock()
    mock_token_resp.json.return_value = {"access": "fake_access_token"}
    mock_post.return_value = mock_token_resp

    # Requisition check mock
    mock_req_resp = MagicMock()
    mock_req_resp.json.return_value = {"accounts": ["acc_1", "acc_2"]}
    mock_get.return_value = mock_req_resp

    provider = GoCardlessProvider()
    creds = {"secret_id": "real_id", "secret_key": "real_key"}
    res = provider.confirm_auth(requisition_id="req_real_987", credentials_dict=creds)
    
    assert res["status"] == "success"
    assert res["accounts"] == ["acc_1", "acc_2"]

@patch("httpx.post")
@patch("httpx.get")
def test_gocardless_fetch_transactions(mock_get, mock_post):
    # Token mock
    mock_token_resp = MagicMock()
    mock_token_resp.json.return_value = {"access": "fake_access_token"}
    mock_post.return_value = mock_token_resp

    # Transactions mock
    mock_txs_resp = MagicMock()
    mock_txs_resp.json.return_value = {
        "transactions": {
            "booked": [
                {
                    "bookingDate": "2026-08-05",
                    "remittanceInformationUnstructured": "Compra en Supermercado",
                    "transactionAmount": {
                        "amount": "-45.50",
                        "currency": "EUR"
                    },
                    "entryReference": "TXN_SUPER_01"
                },
                {
                    "bookingDate": "2026-08-06",
                    "remittanceInformationUnstructuredArray": ["Cobro nomina Luis"],
                    "transactionAmount": {
                        "amount": "2500.00",
                        "currency": "EUR"
                    },
                    "transactionId": "TXN_NOMINA_02"
                }
            ]
        }
    }
    mock_get.return_value = mock_txs_resp

    provider = GoCardlessProvider()
    creds = {"secret_id": "real_id", "secret_key": "real_key"}
    txs = provider.fetch_transactions(credentials_dict=creds, account_id="real_acc_123", start_date="2026-08-01")
    
    assert len(txs) == 2
    assert txs[0]["date"] == "05/08/2026"
    assert txs[0]["concept"] == "Compra en Supermercado"
    assert txs[0]["amount"] == -45.50
    assert txs[0]["reference"] == "TXN_SUPER_01"

    assert txs[1]["date"] == "06/08/2026"
    assert txs[1]["concept"] == "Cobro nomina Luis"
    assert txs[1]["amount"] == 2500.00
    assert txs[1]["reference"] == "TXN_NOMINA_02"
