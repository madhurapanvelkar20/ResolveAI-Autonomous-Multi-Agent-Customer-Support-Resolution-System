"""Run all five demonstration scenarios and report pass/fail evaluation outcomes."""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from resolveai.config import get_settings
from resolveai.scenarios import ALL_SCENARIOS, run_scenario


def main() -> int:
    settings = get_settings()
    trace_dir = settings.trace_dir

    print("==================================================================")
    print("ResolveAI Multi-Agent Autonomous Resolution Evaluation")
    print(f"Running all {len(ALL_SCENARIOS)} demonstration scenarios...")
    print(f"Traces will be stored in: {trace_dir}")
    print("==================================================================\n")

    passed_count = 0
    failed_count = 0
    start_total = time.perf_counter()

    for index, (name, scenario) in enumerate(ALL_SCENARIOS.items(), start=1):
        print(f"[{index}/{len(ALL_SCENARIOS)}] Testing Scenario: {name}")
        print(f"    Description:     {scenario.description}")
        print(f"    Expected Status: {scenario.expected_status.upper()}")

        start_single = time.perf_counter()
        try:
            result, trace_path = run_scenario(scenario, trace_dir=trace_dir)
            elapsed_single = time.perf_counter() - start_single

            assert (
                result.status == scenario.expected_status
            ), f"Status mismatch: expected {scenario.expected_status}, got {result.status}"

            print(f"    Actual Status:   {result.status.upper()}")
            print(f"    Agents:          {', '.join(result.agents_involved)}")
            print(f"    Tools:           {', '.join(result.tools_used) or 'None'}")
            print(f"    Critic:          {result.critic_decision or 'N/A'}")
            print(f"    Trace:           {trace_path}")
            print(f"    Elapsed:         {elapsed_single:.2f}s")
            print("    Outcome:         PASSED [OK]\n")
            passed_count += 1

        except Exception as exc:
            elapsed_single = time.perf_counter() - start_single
            print(f"    Error:           {exc}")
            print(f"    Elapsed:         {elapsed_single:.2f}s")
            print("    Outcome:         FAILED [X]\n")
            failed_count += 1

    total_time = time.perf_counter() - start_total
    print("==================================================================")
    print("Evaluation Summary:")
    print(f"  Total Scenarios: {len(ALL_SCENARIOS)}")
    print(f"  Passed:          {passed_count}")
    print(f"  Failed:          {failed_count}")
    print(f"  Total Time:      {total_time:.2f}s")
    print("==================================================================")

    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
