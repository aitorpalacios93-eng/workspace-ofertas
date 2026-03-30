#!/usr/bin/env python3
"""V0 contract stub for the closing pack.

Responsibilities for the future implementation:
- produce a light ROI model
- generate battlecard
- generate discovery questions
- generate three follow-up messages
"""

from __future__ import annotations

import argparse
import json


CONTRACT = {
    "script": "acelerador_cierre.py",
    "status": "scaffold",
    "inputs": [
        "company",
        "route",
        "proposal_file",
        "evidence_pack_file",
    ],
    "outputs": [
        "roi_<slug>.md",
        "battlecard_<slug>.md",
        "discovery_questions_<slug>.md",
        "followups_<slug>.md",
    ],
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Contract stub for the closing pack.")
    parser.add_argument("--company")
    parser.add_argument("--route", choices=["ES_LOCAL", "ES_B2B", "US_HISPANIC"])
    parser.add_argument("--proposal-file")
    parser.add_argument("--evidence-pack-file")
    parser.add_argument("--describe", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.describe:
        print(json.dumps(CONTRACT, indent=2))
        return 0
    raise SystemExit(
        "acelerador_cierre.py is a V0 scaffold. Use --describe to inspect the contract and implement after the proposal flow is proven."
    )


if __name__ == "__main__":
    raise SystemExit(main())
