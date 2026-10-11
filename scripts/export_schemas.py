
"""Export Pydantic model schemas to JSON files."""

import json
import sys
from pathlib import Path

# Add the project root to Python's import path.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from resolveai.schemas import (
    AgentDecision,
    CaseResult,
    CaseState,
    CriticFeedback,
    TicketIn,
)

OUTPUT_DIR = ROOT / "schemas_export"

MODELS = {
    "ticket_in": TicketIn,
    "agent_decision": AgentDecision,
    "critic_feedback": CriticFeedback,
    "case_state": CaseState,
    "case_result": CaseResult,
}


def main() -> None:
    """Export each Pydantic model's JSON Schema."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for name, model in MODELS.items():
        output_path = OUTPUT_DIR / f"{name}.schema.json"

        schema = model.model_json_schema()
        output_path.write_text(
            json.dumps(schema, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print(f"Exported: {output_path.relative_to(ROOT)}")

    print(f"\nSuccessfully exported {len(MODELS)} schemas.")


if __name__ == "__main__":
    main()
