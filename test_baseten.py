"""Manual opt-in connectivity probe, using the single application adapter.

Running this file makes one potentially billable provider request. Importing it
has no side effects. It never prints response content or credential values.
"""

import sys

import ask_muse


def main() -> int:
    try:
        ask_muse.check_provider_connectivity()
    except RuntimeError as exc:
        # The adapter produces fixed, secret-free error categories, never raw
        # provider messages. Do not print or persist model/provider metadata.
        print(f"Connectivity check failed: {exc}", file=sys.stderr)
        return 1
    print("Live connectivity succeeded; structured interpretation is not yet verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
