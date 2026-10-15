"""Structural and security verification tests for importable n8n workflows (Phase 5.3)."""

import json
from pathlib import Path
import pytest

N8N_DIR = Path("n8n")
EXPECTED_WORKFLOW_FILES = [
    "customer_intake_case_creation.json",
    "authorized_tool_gateway.json",
    "human_escalation_notification.json",
    "audit_trace_collection.json",
    "resolution_event_demo.json",
]


def test_all_n8n_workflows_exist():
    """All required n8n workflow definitions must exist in the n8n/ directory."""
    assert N8N_DIR.exists() and N8N_DIR.is_dir()
    for filename in EXPECTED_WORKFLOW_FILES:
        path = N8N_DIR / filename
        assert path.exists(), f"Missing workflow file: {filename}"


@pytest.mark.parametrize("filename", EXPECTED_WORKFLOW_FILES)
def test_workflow_json_structure_and_integrity(filename: str):
    """Workflow files must be valid n8n importable JSON with nodes, connections, and settings."""
    path = N8N_DIR / filename
    content = path.read_text(encoding="utf-8")
    data = json.loads(content)

    assert "name" in data and isinstance(data["name"], str)
    assert "nodes" in data and isinstance(data["nodes"], list)
    assert len(data["nodes"]) >= 3, f"Workflow {filename} has too few nodes"
    assert "connections" in data and isinstance(data["connections"], dict)
    assert "settings" in data and isinstance(data["settings"], dict)

    node_names = set()
    node_ids = set()
    for node in data["nodes"]:
        assert "name" in node and isinstance(node["name"], str)
        assert "type" in node and isinstance(node["type"], str)
        assert "parameters" in node and isinstance(node["parameters"], dict)
        assert "id" in node and isinstance(node["id"], str)
        assert node["name"] not in node_names, f"Duplicate node name '{node['name']}' in {filename}"
        assert node["id"] not in node_ids, f"Duplicate node id '{node['id']}' in {filename}"
        node_names.add(node["name"])
        node_ids.add(node["id"])

    # Validate that connections point to existing nodes
    for source_node, conn_groups in data["connections"].items():
        assert source_node in node_names, f"Connection source '{source_node}' does not exist in nodes"
        for output_type, targets in conn_groups.items():
            for target_list in targets:
                for target in target_list:
                    assert target["node"] in node_names, (
                        f"Target node '{target['node']}' in connection from '{source_node}' does not exist"
                    )


@pytest.mark.parametrize("filename", EXPECTED_WORKFLOW_FILES)
def test_no_hardcoded_secrets_or_credentials(filename: str):
    """Workflows must not bake in passwords, tokens, API keys, or hardcoded secrets."""
    path = N8N_DIR / filename
    content = path.read_text(encoding="utf-8").lower()

    forbidden_patterns = [
        "secret",
        "password",
        "api_key",
        "bearer ",
        "sk-",
        "gsk_",
        "AIza",
    ]
    for pattern in forbidden_patterns:
        assert pattern not in content, f"Forbidden secret or credential pattern '{pattern}' found in {filename}"


def test_api_urls_are_configurable_via_env():
    """All HTTP request nodes must use environment variables ($env.RESOLVEAI_API_URL) for API base URLs."""
    for filename in EXPECTED_WORKFLOW_FILES:
        path = N8N_DIR / filename
        data = json.loads(path.read_text(encoding="utf-8"))
        for node in data["nodes"]:
            if node["type"] == "n8n-nodes-base.httpRequest":
                url_param = node["parameters"].get("url", "")
                assert "$env.RESOLVEAI_API_URL" in url_param or "RESOLVEAI_API_URL" in url_param, (
                    f"HTTP Request node '{node['name']}' in {filename} does not use configurable API URL env"
                )


def test_authorized_tool_gateway_enforces_whitelist():
    """Tool gateway code node must check tool whitelist and reject arbitrary execution."""
    path = N8N_DIR / "authorized_tool_gateway.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    code_node = next(n for n in data["nodes"] if n["name"] == "Validate Authorized Tool")
    code = code_node["parameters"]["jsCode"]
    assert "allowedTools" in code
    assert "lookup_customer" in code
    assert "lookup_order" in code
    assert "search_knowledge_base" in code


def test_resolution_event_workflow_is_authenticated_and_non_executing():
    path = N8N_DIR / "resolution_event_demo.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    webhook = next(
        node
        for node in data["nodes"]
        if node["name"] == "Approved Case Event Webhook"
    )
    code_node = next(
        node
        for node in data["nodes"]
        if node["name"] == "Validate and Simulate Safe Event"
    )

    assert webhook["parameters"]["authentication"] == "headerAuth"
    assert "event_idempotency_key" in code_node["parameters"]["jsCode"]
    assert "simulated_notification" in code_node["parameters"]["jsCode"]
    assert all(
        node["type"]
        in {
            "n8n-nodes-base.webhook",
            "n8n-nodes-base.code",
            "n8n-nodes-base.respondToWebhook",
        }
        for node in data["nodes"]
    )
