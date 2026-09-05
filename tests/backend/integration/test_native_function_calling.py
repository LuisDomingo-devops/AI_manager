import pytest

@pytest.mark.skip(reason="Ollama native tool calling removed")
@pytest.mark.asyncio
async def test_native_tool_call_parsing():
    pass

@pytest.mark.skip(reason="Ollama native tool calling removed")
@pytest.mark.asyncio
async def test_native_tool_call_fallback_to_text():
    pass
