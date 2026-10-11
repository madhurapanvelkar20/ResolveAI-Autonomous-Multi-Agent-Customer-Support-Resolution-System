
"""Inspect LLM provider configuration and optionally test a connection."""

import sys
from pathlib import Path

# Add the project root to Python's import path.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from resolveai.config import get_settings
from resolveai.llm_factory import build_llm
from resolveai.llm import LLMError


def main() -> int:
    """Check provider configuration and optionally send a test request."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Check ResolveAI LLM provider configuration."
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Send a small request to the configured provider chain.",
    )
    args = parser.parse_args()

    settings = get_settings()
    client = build_llm(settings)

    print("ResolveAI LLM configuration")
    print(f"Provider order: {', '.join(settings.llm_provider_order)}")

    if not client.clients:
        print(
            "No providers are configured with a model and required credentials."
        )
        print(
            "Configure the relevant model and API key in your local .env file."
        )
        return 1

    print(f"Configured providers: {', '.join(client.clients.keys())}")

    if not args.probe:
        print("Configuration check complete. No network request was made.")
        return 0

    try:
        answer = client.complete(
            [
                {
                    "role": "user",
                    "content": "Reply with exactly: ResolveAI OK",
                }
            ]
        )
        print(f"LLM response: {answer[:200]}")
        return 0
    except LLMError as exc:
        print(f"LLM probe failed: {exc}")
        return 1
    finally:
        for provider_client in client.clients.values():
            close = getattr(provider_client, "close", None)
            if close:
                close()


if __name__ == "__main__":
    raise SystemExit(main())
