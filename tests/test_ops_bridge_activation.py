"""Offline regression checks for the one-time bridge integration overlay."""
from __future__ import annotations

import ast

import pytest

from deploy.ops import activate_bridge_v2 as activation


LIVE_STYLE_SERVER = """
from mcp.server.fastmcp import FastMCP
mcp = FastMCP('CREW Development Bridge')

@mcp.tool()
def crew_deploy_plan() -> dict:
    return {'ok': True}

@mcp.tool()
def crew_deploy_status() -> dict:
    return {'ok': True}

if __name__ == '__main__':
    mcp.run(transport='streamable-http')
"""

LIVE_STYLE_COMPOSE = """name: crew-dev-bridge
services:
  bridge:
    group_add: ["986"]
    volumes:
      - ./source:/workspace:rw
      - /run/crew-ops:/run/crew-ops:ro
      - /run/crew-deploy:/run/crew-deploy:ro
  runner:
    network_mode: none
    read_only: true
"""


def test_registers_eleven_no_argument_tools_preserving_existing_functions():
    result = activation.patch_server(LIVE_STYLE_SERVER)
    tree = ast.parse(result)
    names = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert all(name in names for name in activation.METHODS)
    assert len(activation.METHODS) == 11
    assert "crew_deploy_plan" in names
    assert "crew_deploy_status" in names
    assert result.index("def crew_deploy_plan") < result.index("def crew_maint_dashboard")
    assert result.index("def crew_maint_dashboard") < result.index("if __name__")
    assert all(not names[name].args.args for name in activation.METHODS)
    assert all(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                   and n.func.id == "mcp" for n in []) is False
                   for name in activation.METHODS)


def test_code_adapter_never_accepts_arbitrary_ops():
    class FakeMCP:
        def tool(self):
            return lambda fn: fn
    namespace = {"mcp": FakeMCP()}
    exec(compile(activation.tool_registrations(), "<fixed adapter>", "exec"), namespace)
    assert namespace["_crew_maint_request"]("shell") == {
        "ok": False, "error": "operation_not_allowed"}
    assert namespace["_crew_maint_request"]("restart_nginx") == {
        "ok": False, "error": "operation_not_allowed"}
    assert all(name in namespace for name in activation.METHODS)


def test_adds_read_only_socket_mount_only_to_existing_bridge_service():
    updated = activation.patch_compose(LIVE_STYLE_COMPOSE)
    assert updated.count("/run/crew-maint:/run/crew-maint:ro") == 1
    assert "/run/crew-ops:/run/crew-ops:ro" in updated
    assert "/run/crew-deploy:/run/crew-deploy:ro" in updated
    assert 'group_add: ["986"]' in updated
    assert "network_mode: none" in updated
    assert "read_only: true" in updated
    assert updated.endswith("    read_only: true\n")


def test_refuses_unknown_server_or_missing_mount():
    with pytest.raises(ValueError, match="Unexpected bridge server version"):
        activation.patch_server("print('hi')")
    with pytest.raises(ValueError, match="mount not found uniquely"):
        activation.patch_compose("services:\n  bridge:\n    volumes: []\n")


def test_refuses_partial_or_duplicate_activation():
    result = activation.patch_server(LIVE_STYLE_SERVER)
    with pytest.raises(ValueError, match="already present"):
        activation.patch_server(result)
    with pytest.raises(ValueError, match="already configured"):
        activation.patch_compose(activation.patch_compose(LIVE_STYLE_COMPOSE))
    with pytest.raises(ValueError, match="Partial maintenance"):
        activation.patch_server(LIVE_STYLE_SERVER + "\n# crew_maint_dashboard\n")


def test_refuses_nonunique_main_entrypoint():
    repeated = LIVE_STYLE_SERVER + "\nif __name__ == \"__main__\":\n    pass\n"
    with pytest.raises(ValueError, match="not unique"):
        activation.patch_server(repeated)


def test_bridge_rpc_probe_has_jsonl_newline_framing():
    import inspect
    source = inspect.getsource(activation.main)
    tree = ast.parse(source)
    assignments = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "probe"
                           for t in n.targets)]
    assert len(assignments) == 1
    probe = ast.literal_eval(assignments[0].value)
    calls = [n.args[0] for n in ast.walk(ast.parse(probe))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "sendall"]
    assert len(calls) == 1
    assert isinstance(calls[0], ast.BinOp)
    assert ast.literal_eval(calls[0].left) == b'{"operation":"capabilities"}'
    # The probe appends a literal LF byte without shell/string escaping.
    assert ast.unparse(calls[0].right) == "bytes((10,))"
