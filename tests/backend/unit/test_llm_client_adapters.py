"""
Tests unitarios para los adaptadores de llm_client (Spec 029 - US1).
Valida:
1. format_tool_call produce {"type": "tool_call", "tool_name": ..., "tool_args": ...}
2. validate_tool_call valida unívocamente tool_name y tool_args.
"""
import pytest
from app.infrastructure.adapters.llm_client import format_tool_call, validate_tool_call


class TestLLMClientAdapters:

    def test_format_tool_call_generates_canonical_schema(self):
        payload = format_tool_call("create_directory", {"path": "/tmp/test"})
        assert payload["type"] == "tool_call"
        assert payload["tool_name"] == "create_directory"
        assert payload["tool_args"] == {"path": "/tmp/test"}

    def test_format_tool_call_with_empty_or_none_args(self):
        payload = format_tool_call("get_clients")
        assert payload["type"] == "tool_call"
        assert payload["tool_name"] == "get_clients"
        assert payload["tool_args"] == {}

    def test_validate_tool_call_canonical_format(self):
        payload = {
            "type": "tool_call",
            "tool_name": "list_directory",
            "tool_args": {"path": "."}
        }
        validated = validate_tool_call(payload)
        assert validated["tool_name"] == "list_directory"
        assert validated["tool_args"] == {"path": "."}

    def test_validate_tool_call_legacy_format_backward_compat(self):
        payload = {
            "tool": "list_directory",
            "args": {"path": "."}
        }
        validated = validate_tool_call(payload)
        assert validated["tool_name"] == "list_directory"
        assert validated["tool_args"] == {"path": "."}

    def test_validate_tool_call_invalid_tool_returns_no_op(self):
        payload = {
            "type": "tool_call",
            "tool_name": "herramienta_inexistente_xyz",
            "tool_args": {}
        }
        validated = validate_tool_call(payload)
        assert validated["tool_name"] == "no_op"
