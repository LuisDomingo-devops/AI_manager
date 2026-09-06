import os
api_client_path = r'c:\Users\luisd\Desktop\Alfonso_Autonomo\client\core\api_client.py'

with open(api_client_path, 'r', encoding='utf-8') as f:
    content = f.read()

sync_method = """
    def get_dashboard_sync(self) -> dict:
        \"\"\"Obtiene los datos del dashboard sincronizados para el arranque inicial.\"\"\"
        try:
            r = self.session.get(f"{self.base_url}/dashboard/sync", timeout=15)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            print(f"[API] Error obteniendo /dashboard/sync: {e}")
            return {"status": "error", "message": str(e)}
"""

if "def get_dashboard_sync" not in content:
    # Just append it before the end of the class, or at the end of the file (assuming class goes to the end)
    content += sync_method
    with open(api_client_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("api_client.py updated with get_dashboard_sync")
else:
    print("get_dashboard_sync already exists.")
