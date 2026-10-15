"""Execute a ResolveAI support case or demo scenario with multi-agent orchestration."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from resolveai.config import get_settings
from resolveai.database import fetch_one, init_db, seed_demo_data
from resolveai.policies import PolicyVectorStore
from resolveai.scenarios import ALL_SCENARIOS, run_scenario
from resolveai.schemas import TicketIn
from resolveai.tracing import TraceLogger, load_trace, render_text
from resolveai.workflow import ResolveAIWorkflow


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a ResolveAI support case through the autonomous multi-agent workflow."
    )
    parser.add_argument(
        "--scenario",
        type=str,
        choices=list(ALL_SCENARIOS.keys()),
        help="Run a predefined demo scenario.",
    )
    parser.add_argument(
        "--ticket-id",
        type=str,
        help="Run against an existing ticket from the SQLite database.",
    )
    parser.add_argument(
        "--seed-data",
        action="store_true",
        help="Seed synthetic demo records into SQLite database before execution.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Force deterministic offline mock execution.",
    )
    parser.add_argument(
        "--verbose-trace",
        action="store_true",
        help="Print detailed execution trace events.",
    )
    args = parser.parse_args()

    settings = get_settings()

    if args.seed_data:
        print("Seeding demo database records...")
        seed_demo_data(settings.database_path)
        print("Database seeded successfully.")

    # Validate or check vector store
    store = PolicyVectorStore(chroma_dir=settings.chroma_dir, settings=settings)
    chunk_count = 0
    try:
        chunk_count = store.count()
    except Exception:
        pass

    if chunk_count == 0:
        print(
            "Warning: Policy vector store at data/chroma appears empty.\n"
            "Run 'python scripts/ingest_policies.py' to ingest policy documents.",
            file=sys.stderr,
        )

    if args.scenario:
        scenario = ALL_SCENARIOS[args.scenario]
        print(f"\n========================================================")
        print(f"Running Demo Scenario: {scenario.name}")
        print(f"Description: {scenario.description}")
        print(f"========================================================\n")

        try:
            result, trace_path = run_scenario(
                scenario, trace_dir=settings.trace_dir
            )
            print("\nCase Execution Summary:")
            print(f"  Case ID:          {result.case_id}")
            print(f"  Status:           {result.status.upper()}")
            print(f"  Iterations:       {result.iterations}")
            print(f"  Agents Involved:  {', '.join(result.agents_involved)}")
            print(f"  Tools Used:       {', '.join(result.tools_used) or 'None'}")
            print(f"  Critic Decision:  {result.critic_decision or 'N/A'}")
            if result.resolution:
                print(
                    f"  Resolution:       {result.resolution.type} "
                    f"({result.resolution.amount or ''} {result.resolution.currency or ''})"
                )
            if result.escalation_reason:
                print(f"  Escalation:       {result.escalation_reason}")
            print(f"  Trace Saved To:   {trace_path}")
            print(f"  Customer Message: {result.customer_response}\n")

            if args.verbose_trace:
                print("--- Detailed Execution Trace ---")
                events = load_trace(trace_path)
                print(render_text(events))
                print("--------------------------------\n")

            return 0
        except Exception as exc:
            print(f"Scenario execution failed: {exc}", file=sys.stderr)
            return 1

    if args.ticket_id:
        print(f"Looking up ticket '{args.ticket_id}' from database...")
        ticket_row = fetch_one(
            "tickets", "ticket_id", args.ticket_id, db_path=settings.database_path
        )
        if not ticket_row:
            print(
                f"Error: Ticket '{args.ticket_id}' not found in database.",
                file=sys.stderr,
            )
            return 1

        ticket = TicketIn(
            ticket_id=ticket_row["ticket_id"],
            customer_id=ticket_row["customer_id"],
            message=ticket_row["message"],
            channel=ticket_row["channel"],
            timestamp=ticket_row["created_at"],
            metadata={"subject": ticket_row["subject"]},
        )

        tracer = TraceLogger(trace_dir=settings.trace_dir)
        workflow = ResolveAIWorkflow(settings=settings, tracer=tracer)
        try:
            result = workflow.run(ticket)
            print("\nCase Execution Summary:")
            print(f"  Case ID:          {result.case_id}")
            print(f"  Status:           {result.status.upper()}")
            print(f"  Iterations:       {result.iterations}")
            print(f"  Agents Involved:  {', '.join(result.agents_involved)}")
            print(f"  Tools Used:       {', '.join(result.tools_used) or 'None'}")
            print(f"  Critic Decision:  {result.critic_decision or 'N/A'}")
            print(f"  Trace Saved To:   {tracer.path}")
            print(f"  Customer Message: {result.customer_response}\n")
            return 0
        except Exception as exc:
            print(f"Workflow execution failed: {exc}", file=sys.stderr)
            return 1

    print("Please specify --scenario <name> or --ticket-id <id>.")
    print("Available scenarios: " + ", ".join(ALL_SCENARIOS.keys()))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
