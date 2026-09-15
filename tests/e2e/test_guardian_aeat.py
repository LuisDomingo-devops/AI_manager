import pytest
from playwright.async_api import Page, expect

@pytest.mark.asyncio
async def test_guardian_autofill_modelo_303(start_server: str, firefox_page: Page):
    """
    Test E2E que verifica que el Guardián automatiza la UI para el modelo 303.
    """
    # 1. Navegar a la página principal de nuestra app UI
    await firefox_page.goto(f"{start_server}/")
    
    # 2. Verificar que la UI carga correctamente
    await expect(firefox_page.locator("text=Alfonso Autónomo")).to_be_visible(timeout=10000)
    
    # 3. Interacción simulada del usuario: "Rellenar modelo 303 del trimestre 1"
    # Suponiendo que hay un input de chat o comando en la GUI
    chat_input = firefox_page.locator("input[type='text'], textarea").first
    await chat_input.fill("Rellena el modelo 303 del T1")
    await chat_input.press("Enter")
    
    # 4. Esperar a que el agente procese e invoque al Guardián
    # El sistema debería abrir o inyectar un iframe/página hacia la AEAT y rellenar.
    # Simularemos la aserción de que aparece un mensaje de éxito o que el Guardián se ha activado.
    success_message = firefox_page.locator("text=Guardián activado")
    await expect(success_message).to_be_visible(timeout=15000)
    
    # 5. Idealmente, comprobar el DOM inyectado o la respuesta simulada
    # (El test está diseñado para fallar inicialmente en TDD)
    aeat_form_indicator = firefox_page.locator("text=Modelo 303")
    await expect(aeat_form_indicator).to_be_visible(timeout=15000)
