"""Make one minimal Gemini API call without displaying credentials."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rfp_eval.gemini_client import (
    GeminiAPIError,
    GeminiConfigurationError,
    GeminiEvaluator,
    is_placeholder_setting,
)


def main() -> int:
    import os

    if is_placeholder_setting(os.getenv("GEMINI_API_KEY")):
        print("SKIPPED: GEMINI_API_KEY is missing or looks like a placeholder; no request was sent.")
        return 2
    if is_placeholder_setting(os.getenv("GEMINI_MODEL")):
        print("SKIPPED: GEMINI_MODEL is missing or looks like a placeholder; no request was sent.")
        return 2
    try:
        evaluator = GeminiEvaluator()
    except GeminiConfigurationError as exc:
        print(f"SKIPPED: {exc}")
        return 2
    try:
        evaluator.smoke_test()
    except GeminiAPIError as exc:
        print(f"FAILED: {exc}")
        return 1
    except Exception as exc:
        print(f"FAILED: unexpected error ({type(exc).__name__}). Check local configuration and SDK setup.")
        return 1
    finally:
        evaluator.close()
    print("SUCCESS: Gemini API returned a response.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
