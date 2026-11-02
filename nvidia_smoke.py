"""Opt-in NVIDIA short completion and optional synthetic report comparison.

This script makes potentially billable calls only with explicit command-line
consent. It never prints prompts, model output, or credentials.
"""
from __future__ import annotations

import argparse
import logging
import tempfile
import time
from pathlib import Path

import hosted_model_provider as hosted
import provider_config

MODEL = "meta/muse-glimmer-30b"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-live", action="store_true", help="Consent to one potentially billable short call.")
    parser.add_argument("--compare-report", action="store_true", help="Also consent to a second full report on synthetic data.")
    args = parser.parse_args(argv)
    if not args.confirm_live:
        print("No request sent. Pass --confirm-live to consent to the short test.")
        return 2
    try:
        config = hosted._config()
        if config["mode"] != "nvidia" or config["model"] != MODEL:
            print("No request sent: select NVIDIA and configure the exact Muse Glimmer model.")
            return 2
    except ValueError as exc:
        print("No request sent: " + provider_config.redact(str(exc)))
        return 2
    # Enable only our metadata logger, not verbose HTTP/SDK logs.
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    hosted.LOGGER.addHandler(handler)
    hosted.LOGGER.setLevel(logging.INFO)
    hosted.LOGGER.propagate = False
    short_config = dict(config, tokens=min(config["tokens"], 256))
    started = time.monotonic()
    try:
        _, catalog = hosted._request_content(short_config, "Reply with the single word OK.")
    except (ValueError, RuntimeError) as exc:
        print(f"Short completion: FAILED after {time.monotonic() - started:.1f}s: {provider_config.redact(str(exc))}")
        return 1
    print(f"Short completion: received visible content in {time.monotonic() - started:.1f}s; catalog={catalog}. Not a report validation test.")
    if not args.compare_report:
        print("Full report: NOT RUN (requires --compare-report).")
        return 0
    from analyze_dataset import analyze_csv
    from result_schema import ai_context

    started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix="lablens-nvidia-smoke-") as directory:
            source = Path(__file__).resolve().parent / "data" / "demo" / "linear_calibration_demo.csv"
            result = analyze_csv(source, directory, x="time_s", y="signal_mV")
            context = ai_context(result, research_question="Describe the relationship between time and signal.")
            hosted.generate_interpretation(context, confirmed=True)
    except (ValueError, RuntimeError) as exc:
        print(f"Synthetic full report: FAILED after {time.monotonic() - started:.1f}s: {provider_config.redact(str(exc))}")
        return 1
    print(f"Synthetic full report: validated in {time.monotonic() - started:.1f}s. Interpretations remain unverified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
