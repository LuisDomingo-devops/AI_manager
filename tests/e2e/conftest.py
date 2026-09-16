import pytest
import os
from playwright.async_api import async_playwright
import asyncio
import subprocess
import time
import httpx

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def start_server():
    """Lanza el servidor de prueba (FastAPI + GUI) para los tests E2E."""
    # Como queremos un test completo, levantamos la aplicación.
    # Asumimos que podemos levantar uvicorn localmente.
    env = os.environ.copy()
    env["TESTING"] = "1"
    
    # Levantar el backend en un puerto distinto para no colisionar con el dev server
    process = subprocess.Popen(
        ["uvicorn", "app.main:app", "--port", "8999"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    
    # Esperar a que el servidor esté vivo
    async with httpx.AsyncClient() as client:
        for _ in range(30):
            try:
                response = await client.get("http://127.0.0.1:8999/health")
                if response.status_code == 200:
                    break
            except Exception:
                pass
            await asyncio.sleep(1)
        else:
            process.terminate()
            raise RuntimeError("El servidor no arrancó a tiempo para los tests E2E.")
            
    yield "http://127.0.0.1:8999"
    
    process.terminate()
    process.wait()

@pytest.fixture(scope="function")
async def firefox_page():
    """Provee una página de Playwright usando exclusivamente Firefox, con certificados."""
    async with async_playwright() as p:
        # Forzar Firefox por requerimiento
        browser = await p.firefox.launch(headless=True)
        
        # En una situación real de AEAT, podríamos inyectar el certificado en el contexto,
        # Playwright permite client_certificates en los contextos a partir de v1.46 (aprox)
        # o mediante opciones de Firefox.
        # Aquí apuntamos a la ruta dummy
        cert_path = os.path.abspath("data/certificados_prueba/certificado_pruebas.pem")
        key_path = os.path.abspath("data/certificados_prueba/clave_pruebas.pem")
        
        context_options = {
            "ignore_https_errors": True,
        }
        
        # Si la versión de playwright soporta client_certificates:
        try:
            context_options["client_certificates"] = [{
                "origin": "https://www1.agenciatributaria.gob.es",
                "certPath": cert_path,
                "keyPath": key_path
            }]
        except Exception as e:
            print(f"Playwright version doesn't support client_certificates out of the box or error: {e}")
            
        context = await browser.new_context(**context_options)
        page = await context.new_page()
        
        yield page
        
        await context.close()
        await browser.close()
