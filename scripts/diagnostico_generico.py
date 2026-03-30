#!/usr/bin/env python3
"""V0 contract stub for the diagnostic entrypoint.

Responsibilities for the future implementation:
- collect website and business evidence
- calculate fit score
- assign route
- write temporary artifacts into .tmp/
"""

from __future__ import annotations

import argparse
import json


CONTRACT = {
    "script": "diagnostico_generico.py",
    "status": "scaffold",
    "inputs": [
        "empresa",
        "url",
        "pais",
        "sector",
        "route_hint(optional)",
    ],
    "outputs": [
        "health_check_<slug>.md",
        "fit_score_<slug>.json",
        "evidence_pack_<slug>.json",
        "route_recommendation_<slug>.json",
    ],
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Contract stub for the diagnostic workflow."
    )
    parser.add_argument("--empresa")
    parser.add_argument("--url")
    parser.add_argument("--pais")
    parser.add_argument("--sector")
    parser.add_argument("--route-hint", choices=["ES_LOCAL", "ES_B2B", "US_HISPANIC"])
    parser.add_argument("--describe", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.describe:
        print(json.dumps(CONTRACT, indent=2))
        return 0
    raise SystemExit(
        "diagnostico_generico.py is a V0 scaffold. Use --describe to inspect the contract and implement after the first documented ES case."
    )


if __name__ == "__main__":
    raise SystemExit(main())
