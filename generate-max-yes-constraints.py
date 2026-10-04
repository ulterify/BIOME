#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pict_common import max_yes_constraints


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Generate PICT constraints for "at most N variables may be yes".'
    )
    parser.add_argument("max_yes", nargs="?", type=int, default=3)
    parser.add_argument("model", nargs="?", type=Path, default=Path("pict-model.txt"))
    args = parser.parse_args()

    if args.max_yes < 0:
        parser.error(f"MAX_YES must be a non-negative integer, got: {args.max_yes}")

    try:
        model_text = args.model.read_text()
        for line in max_yes_constraints(model_text, args.max_yes):
            print(line)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
