"""Check provider configuration and benchmark structured Triage decisions."""

import argparse
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pydantic import ValidationError

from resolveai.config import get_settings
from resolveai.llm import FallbackLLM, LLMError, StructuredLLM
from resolveai.llm_factory import build_llm
from resolveai.schemas import AgentDecision


SYSTEM_PROMPT = """
You are ResolveAI's customer-support Triage agent.
Choose a safe next action based only on the supplied ticket.
Return exactly one JSON object matching the requested schema.
Do not invent investigation results or claim that an action has been completed.
For a routine request needing more information, use ask_customer with
next_agent set to none. Include agent, next_action, next_agent, reason,
confidence, and state_updates. Include tool_call only when calling a tool.
"""

USER_PROMPT = """
Ticket:
ID: ticket-benchmark-001
Channel: web
Customer message: I was charged twice for the same order. Please help.

Return a valid triage decision. If more information is needed, ask the
customer for the order ID or transaction details. Do not issue a refund
without investigation.
"""


def close_clients(client: FallbackLLM) -> None:
    """Close all configured provider HTTP clients."""
    for provider_client in client.clients.values():
        close = getattr(provider_client, "close", None)
        if close:
            close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check ResolveAI LLM configuration and benchmark."
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run repeated real Triage decision requests.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=10,
        help="Number of benchmark requests (default: 10).",
    )
    args = parser.parse_args()

    if args.runs < 1:
        parser.error("--runs must be at least 1")

    settings = get_settings()
    client = build_llm(settings)

    print("ResolveAI LLM configuration")
    print(f"Provider order: {', '.join(settings.llm_provider_order)}")

    if not client.clients:
        print("No providers are configured with a model and required credentials.")
        print("Configure the relevant model and API key in your local .env file.")
        return 1

    print(f"Configured providers: {', '.join(client.clients.keys())}")
    for provider in client.clients:
        model = getattr(settings, f"{provider}_model", "")
        print(f"  {provider} model: {model}")

    if not args.benchmark:
        print("Configuration check complete. No network request was made.")
        print("Run with --benchmark to measure structured decision quality.")
        close_clients(client)
        return 0

    structured = StructuredLLM(
        client,
        max_validation_retries=settings.llm_max_retries,
    )
    latencies_ms = []
    valid_decisions = 0
    failures = 0

    try:
        for run_number in range(1, args.runs + 1):
            started = time.perf_counter()
            try:
                decision = structured.decide(
                    agent="triage",
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=USER_PROMPT,
                    schema=AgentDecision,
                )
                if decision.agent != "triage":
                    raise ValueError("Decision agent is not triage")

                valid_decisions += 1
                outcome = "valid"
            except (LLMError, ValidationError, ValueError) as exc:
                failures += 1
                outcome = f"invalid ({type(exc).__name__})"
            finally:
                latencies_ms.append(
                    (time.perf_counter() - started) * 1000
                )

            print(f"Run {run_number}/{args.runs}: {outcome}")

    finally:
        close_clients(client)

    valid_rate = valid_decisions / args.runs * 100
    median_latency = statistics.median(latencies_ms)

    print("\nBenchmark results")
    print(f"Runs: {args.runs}")
    print(f"Valid decisions: {valid_decisions}/{args.runs}")
    print(f"Invalid/failed decisions: {failures}/{args.runs}")
    print(f"Valid-decision rate: {valid_rate:.2f}%")
    print(f"Median latency: {median_latency:.2f} ms")

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())