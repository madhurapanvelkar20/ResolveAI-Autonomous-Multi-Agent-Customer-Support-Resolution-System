
"""Tests for ResolveAI utility scripts."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_export_schemas_script():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export_schemas.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Successfully exported 5 schemas." in result.stdout

    output_dir = ROOT / "docs" / "schemas"
    expected_files = [
        "ticket_in.schema.json",
        "agent_decision.schema.json",
        "critic_feedback.schema.json",
        "case_state.schema.json",
        "case_result.schema.json",
    ]

    for filename in expected_files:
        path = output_dir / filename
        assert path.exists(), f"Missing schema: {filename}"
        assert path.stat().st_size > 0


def test_check_llm_script_without_configuration():
    env = os.environ.copy()

    # Ensure this test doesn't accidentally use real provider credentials.
    for key in (
        "GROQ_API_KEY",
        "GEMINI_API_KEY",
        "OLLAMA_API_KEY",
        "GROQ_MODEL",
        "GEMINI_MODEL",
        "OLLAMA_MODEL",
    ):
        env.pop(key, None)

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_llm.py")],
        cwd=ROOT.parent,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 1
    assert "No providers are configured" in result.stdout
    assert "Traceback" not in result.stderr
