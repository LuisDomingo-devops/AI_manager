import pytest
from unittest.mock import patch, MagicMock
from client.gui.dialogs.widgets import PlaywrightWorkerThread

def test_playwright_worker_thread_uses_firefox():
    """
    Test que verifica que PlaywrightWorkerThread usa Firefox en lugar de Chromium.
    """
    worker = PlaywrightWorkerThread()
    
    import playwright.sync_api
    with patch.object(playwright.sync_api, 'sync_playwright') as mock_sync_pw:
        mock_pw_instance = MagicMock()
        mock_sync_pw.return_value.start.return_value = mock_pw_instance
        
        mock_firefox = MagicMock()
        mock_pw_instance.firefox = mock_firefox
        mock_browser = MagicMock()
        mock_firefox.launch.return_value = mock_browser
        
        mock_context = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_context.pages = []
        
        mock_page = MagicMock()
        mock_context.new_page.return_value = mock_page
        
        # Evitamos el bucle infinito en el test
        worker.running = False
        
        worker.run()
        
        # Verificar que se lanzó Firefox
        mock_firefox.launch.assert_called_once_with(headless=False)
        
        # Verificar que no se llamó a chromium
        assert not mock_pw_instance.chromium.launch.called
