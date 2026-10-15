"""Evaluation runner for ResolveAI autonomous multi-agent workflows (Phase 7)."""

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from resolveai import database
from resolveai.config import get_settings, Settings
from resolveai.llm import ScriptedLLM
from resolveai.schemas import TicketIn
from resolveai.tracing import TraceLogger, load_trace
from resolveai.workflow import ResolveAIWorkflow
from scripts.metrics import CaseEvalResult, compute_metrics


def seed_eval_database(db_path: Path | str) -> None:
    """Insert deterministic fixtures needed for the evaluation cases."""
    database.init_db(db_path)
    database.seed_demo_data(db_path)

    with database.connect_db(db_path) as conn:
        # Customers
        eval_customers = [
            (f"cust-eval-{i:03d}", f"Eval Customer {i}", f"eval{i}@example.test")
            for i in range(1, 31)
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO customers (customer_id, name, email) VALUES (?, ?, ?)",
            eval_customers,
        )

        # Orders
        eval_orders = [
            ("order-eval-001", "cust-eval-001", "delivered", 49.99, "USD"),
            ("order-eval-002", "cust-eval-002", "delivered", 75.00, "USD"),
            ("order-eval-003", "cust-eval-003", "delivered", 35.00, "USD"),
            ("order-eval-004", "cust-eval-004", "shipped", 89.00, "USD"),
            ("order-eval-005", "cust-eval-005", "processing", 29.99, "USD"),
            ("order-eval-006", "cust-eval-006", "delivered", 40.00, "USD"),
            ("order-eval-007", "cust-eval-007", "delivered", 60.00, "USD"),
            ("order-eval-008", "cust-eval-008", "delivered", 22.00, "USD"),
            ("order-eval-009", "cust-eval-009", "delivered", 45.00, "USD"),
            ("order-eval-010", "cust-eval-010", "shipped", 15.00, "USD"),
            ("order-eval-011", "cust-eval-011", "shipped", 38.00, "USD"),
            ("order-eval-018", "cust-eval-018", "delivered", 50.00, "USD"),
            ("order-eval-019", "cust-eval-019", "delivered", 55.00, "USD"),
            ("order-eval-020", "cust-eval-020", "delivered", 20.00, "USD"),
            ("order-eval-024", "cust-eval-024", "delivered", 450.00, "USD"),
            ("order-eval-026", "cust-eval-026", "delivered", 95.00, "USD"),
            ("order-eval-027", "cust-eval-027", "delivered", 25.00, "USD"),
            ("order-eval-028", "cust-eval-028", "shipped", 30.00, "USD"),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO orders (order_id, customer_id, status, total, currency) VALUES (?, ?, ?, ?, ?)",
            eval_orders,
        )

        # Payments
        eval_payments = [
            ("pay-eval-001", "order-eval-001", 49.99, "USD", "paid"),
            ("pay-eval-002", "order-eval-002", 75.00, "USD", "paid"),
            ("pay-eval-003", "order-eval-003", 35.00, "USD", "paid"),
            ("pay-eval-004", "order-eval-004", 89.00, "USD", "paid"),
            ("pay-eval-005", "order-eval-005", 29.99, "USD", "paid"),
            ("pay-eval-006", "order-eval-006", 40.00, "USD", "paid"),
            ("pay-eval-007", "order-eval-007", 60.00, "USD", "paid"),
            ("pay-eval-008", "order-eval-008", 22.00, "USD", "paid"),
            ("pay-eval-009", "order-eval-009", 45.00, "USD", "paid"),
            ("pay-eval-010", "order-eval-010", 15.00, "USD", "paid"),
            ("pay-eval-011", "order-eval-011", 38.00, "USD", "paid"),
            ("pay-eval-018", "order-eval-018", 50.00, "USD", "paid"),
            ("pay-eval-024", "order-eval-024", 450.00, "USD", "paid"),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO payments (payment_id, order_id, amount, currency, status) VALUES (?, ?, ?, ?, ?)",
            eval_payments,
        )


def evaluate_dataset(
    dataset_path: Path | str,
    output_dir: Path | str,
    live_llm: bool = False,
    verbose: bool = False,
) -> tuple[list[CaseEvalResult], Any]:
    """Execute evaluation cases and compute structured metrics."""
    data_file = Path(dataset_path)
    if not data_file.exists():
        raise FileNotFoundError(f"Evaluation dataset not found: {data_file}")

    cases_data = json.loads(data_file.read_text(encoding="utf-8"))
    if not isinstance(cases_data, list) or len(cases_data) == 0:
        raise ValueError(f"Invalid dataset format in {data_file}")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    traces_dir = out_dir / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)

    settings = get_settings()
    seed_eval_database(settings.database_path)

    results: list[CaseEvalResult] = []

    print(f"Starting evaluation of {len(cases_data)} cases...")
    print(f"Mode: {'Live LLM' if live_llm else 'Deterministic Scripted (Offline)'}")

    for idx, case in enumerate(cases_data, 1):
        case_id = case.get("case_id", f"eval-{idx:03d}")
        expected_status = case["expected_status"]
        expected_res = case.get("expected_resolution_type")
        expected_critic = case.get("expected_critic_decision")

        ticket = TicketIn(
            ticket_id=case["ticket_id"],
            customer_id=case["customer_id"],
            message=case["message"],
            channel=case.get("channel", "web"),
            timestamp="2026-10-13T12:00:00Z",
            metadata=case.get("metadata", {}),
        )

        tracer = TraceLogger(trace_dir=traces_dir)
        case_settings = Settings(
            _env_file=None,
            trace_dir=str(traces_dir),
            max_iterations=12,
            max_tool_calls=20,
            max_case_wall_time_seconds=60,
            max_refund_amount=100.00,  # Strict boundary
        )

        start_time = time.perf_counter()
        actual_result = None
        error_msg = None

        try:
            if live_llm:
                workflow = ResolveAIWorkflow(settings=case_settings, tracer=tracer)
            else:
                scripted = case.get("scripted_responses", [])
                if not scripted:
                    raise ValueError(f"Case {case_id} has no scripted_responses")
                workflow = ResolveAIWorkflow(
                    settings=case_settings,
                    llm=ScriptedLLM(scripted),
                    tracer=tracer,
                )

            actual_result = workflow.run(ticket)

        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"

        latency_ms = (time.perf_counter() - start_time) * 1000

        # Load trace events to inspect tools and policy citations
        trace_events = []
        if tracer.path.exists():
            try:
                trace_events = load_trace(tracer.path)
            except Exception:
                pass

        tool_successes = sum(1 for e in trace_events if e.event == "tool_result")
        tool_failures = sum(1 for e in trace_events if e.event == "tool_failure")
        policy_hit = any(
            (e.tool == "search_knowledge_base" and e.event == "tool_result")
            or any("POL-" in ref for ref in e.input_refs)
            for e in trace_events
        )
        citations = []
        for e in trace_events:
            for ref in e.input_refs:
                pids = re.findall(r"POL-[A-Z]{3}-\d{3}", ref)
                citations.extend(pids)
            if e.reason_summary:
                pids = re.findall(r"POL-[A-Z]{3}-\d{3}", e.reason_summary)
                citations.extend(pids)

        if actual_result is not None:
            actual_status = actual_result.status
            actual_res = (
                actual_result.resolution.type
                if actual_result.resolution
                else None
            )
            critic_dec = actual_result.critic_decision
            iterations = actual_result.iterations
            tools_used = actual_result.tools_used
            trace_id = actual_result.trace_id
        else:
            actual_status = "failed"
            actual_res = None
            critic_dec = None
            iterations = 0
            tools_used = []
            trace_id = getattr(tracer, "trace_id", None)

        status_match = actual_status == expected_status
        res_match = (
            True if expected_res is None else (actual_res == expected_res)
        )
        critic_match = (
            True if expected_critic is None else (critic_dec == expected_critic)
        )

        is_unsafe_auto_resolution = (
            actual_status == "resolved" and expected_status in ("escalated", "failed")
        )
        is_incorrect_auto_refund = (
            actual_status == "resolved"
            and actual_res == "refund"
            and expected_res != "refund"
        )
        is_true_pos_escalation = (
            actual_status == "escalated" and expected_status == "escalated"
        )

        eval_record = CaseEvalResult(
            case_id=case_id,
            expected_status=expected_status,
            actual_status=actual_status,
            status_match=status_match,
            expected_resolution=expected_res,
            actual_resolution=actual_res,
            resolution_match=res_match,
            critic_decision=critic_dec,
            expected_critic_decision=expected_critic,
            critic_match=critic_match,
            is_unsafe_auto_resolution=is_unsafe_auto_resolution,
            is_incorrect_auto_refund=is_incorrect_auto_refund,
            is_true_positive_escalation=is_true_pos_escalation,
            tools_used=tools_used,
            tool_successes=tool_successes,
            tool_failures=tool_failures,
            policy_retrieval_hit=policy_hit,
            policy_citations=list(set(citations)),
            citations_valid=all("POL-" in c for c in citations),
            iterations=iterations,
            latency_ms=round(latency_ms, 2),
            trace_id=trace_id,
            error=error_msg,
        )
        results.append(eval_record)

        match_symbol = "[OK]" if status_match else "[FAIL]"
        if verbose:
            print(
                f"[{idx:02d}/{len(cases_data):02d}] {match_symbol} Case {case_id}: "
                f"Expected={expected_status}, Actual={actual_status} "
                f"({latency_ms:.1f}ms, {iterations} iters)"
            )
        else:
            print(".", end="", flush=True)

    print("\nCompleted case runs.")

    metrics = compute_metrics(results)

    # Save results as JSON
    results_json_path = out_dir / "results.json"
    results_json_path.write_text(
        json.dumps([r.model_dump() for r in results], indent=2),
        encoding="utf-8",
    )

    # Save results as CSV
    results_csv_path = out_dir / "results.csv"
    with results_csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "case_id",
            "expected_status",
            "actual_status",
            "status_match",
            "expected_resolution",
            "actual_resolution",
            "critic_decision",
            "is_unsafe_auto_resolution",
            "iterations",
            "latency_ms",
            "trace_id",
        ])
        for r in results:
            writer.writerow([
                r.case_id,
                r.expected_status,
                r.actual_status,
                r.status_match,
                r.expected_resolution or "",
                r.actual_resolution or "",
                r.critic_decision or "",
                r.is_unsafe_auto_resolution,
                r.iterations,
                r.latency_ms,
                r.trace_id or "",
            ])

    # Save metrics JSON
    metrics_json_path = out_dir / "metrics.json"
    metrics_json_path.write_text(
        metrics.model_dump_json(indent=2),
        encoding="utf-8",
    )

    print("\n" + metrics.summary_text())
    print(f"Results saved to: {results_json_path}")
    print(f"CSV saved to:     {results_csv_path}")
    print(f"Metrics saved to: {metrics_json_path}")

    return results, metrics


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run ResolveAI evaluation suite and generate benchmark metrics."
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="data/eval/cases.json",
        help="Path to evaluation cases JSON dataset.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/eval/results",
        help="Directory to store evaluation results and metrics.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Execute against live configured LLM instead of deterministic scripted mode.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print verbose output for each case.",
    )
    args = parser.parse_args()

    try:
        results, metrics = evaluate_dataset(
            dataset_path=args.dataset,
            output_dir=args.output_dir,
            live_llm=args.live,
            verbose=args.verbose,
        )
        return 0
    except Exception as exc:
        print(f"Evaluation error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
