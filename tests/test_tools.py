from resolveai import database
from resolveai.tools import execute_tool


def test_unknown_tool_is_rejected():
    result = execute_tool("delete_everything", {})
    assert result["ok"] is False
    assert result["error"] == "Unknown tool"


def test_invalid_tool_arguments_are_rejected():
    result = execute_tool("request_refund", {"amount": -10})
    assert result["ok"] is False
    assert result["error"] == "Invalid tool arguments"


def test_extra_arguments_are_rejected():
    result = execute_tool(
        "lookup_customer",
        {"customer_id": "cust-demo-001", "admin": True},
    )
    assert result["ok"] is False


def test_demo_data_and_customer_lookup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = execute_tool("initialize_demo_data", {})
    assert result["ok"] is True

    result = execute_tool(
        "lookup_customer", {"customer_id": "cust-demo-001"}
    )
    assert result["ok"] is True
    assert result["data"]["name"] == "Alex Morgan"


def test_refund_tool_rejects_amount_over_limit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    execute_tool("initialize_demo_data", {})

    result = execute_tool(
        "request_refund",
        {
            "payment_id": "pay-demo-001",
            "amount": 5000,
            "reason": "Customer request",
        },
    )
    assert result["ok"] is False