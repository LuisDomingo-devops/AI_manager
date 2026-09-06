import re
path = r'c:\Users\luisd\Desktop\Alfonso_Autonomo\tests\backend\qa\test_qa_stress.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

mock_code = '''
    # Mockear GeminiClient para no saturar la API externa durante el test de estrés
    class MockGemini:
        async def generate(self, *args, **kwargs):
            time.sleep(0.01)
            return '{"iva_rate": 21.0, "irpf_rate": 0.0}', 10, 10
        async def chat(self, *args, **kwargs):
            time.sleep(0.01)
            return "Respuesta simulada"

    monkeypatch.setattr("app.infrastructure.adapters.llm_client.GeminiClient", lambda: MockGemini())
'''

# Find the clean_and_mock fixture and inject our mock code
if 'MockGemini' not in content:
    content = content.replace(
        'monkeypatch.setattr(routes, "orchestrator", MockOrchestrator())',
        'monkeypatch.setattr(routes, "orchestrator", MockOrchestrator())\n' + mock_code
    )
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
