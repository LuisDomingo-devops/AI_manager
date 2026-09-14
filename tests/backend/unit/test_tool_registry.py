import pytest
from app.adapters.tool_registry import list_tools, load_plugins, get_tool

def test_tool_registry_loads_plugins():
    load_plugins()
    tools = list_tools()
    
    assert "no_op" in tools
    assert "create_file" in tools
    assert "read_file" in tools
    assert "append_file" in tools
    assert "list_directory" in tools
    assert "delete_file" in tools

def test_get_tool_existing():
    load_plugins()
    tool = get_tool("create_file")
    assert tool is not None
    assert callable(tool)

def test_get_tool_non_existing():
    load_plugins()
    tool = get_tool("this_tool_does_not_exist")
    assert tool is None
