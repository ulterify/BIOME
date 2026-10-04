#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from pict_common import generated_model_text, parse_int_list, run_pict


SCRIPT_DIR = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate PICT testsets from the base model plus a generated max-yes constraint."
    )
    parser.add_argument("--max-yes", type=int, default=4, help='maximum number of variables that may be "yes"')
    parser.add_argument("--orders", default="2 3 4 5", help="space- or comma-separated PICT orders to generate")
    parser.add_argument("--order", action="append", type=int, help="add one order to generate; may be repeated")
    parser.add_argument("--iterations", type=int, default=10, help="PICT /b:N seed attempts")
    parser.add_argument("--seed", type=int, default=132, help="PICT /r:N base random seed")
    parser.add_argument("--model", type=Path, default=SCRIPT_DIR / "pict-model.txt", help="base PICT model file")
    parser.add_argument("--pict-bin", type=Path, default=Path("pict"), help="PICT executable")
    parser.add_argument("--output-dir", type=Path, default=SCRIPT_DIR / "pict-testsets", help="output directory")
    args = parser.parse_args()

    if args.max_yes < 0:
        parser.error("--max-yes must be a non-negative integer")
    if args.iterations <= 0:
        parser.error("--iterations must be a positive integer")
    if args.seed < 0:
        parser.error("--seed must be a non-negative integer")

    orders = args.order if args.order else parse_int_list(args.orders)
    if not orders:
        parser.error("at least one order is required")
    if any(order <= 0 for order in orders):
        parser.error("orders must be positive integers")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    model_text = generated_model_text(args.model, args.max_yes)

    for order in orders:
        output_file = args.output_dir / f"order-{order}.max-yes-{args.max_yes}.tsv"
        test_count, _ = run_pict(
            pict_bin=args.pict_bin,
            model_text=model_text,
            order=order,
            iterations=args.iterations,
            seed=args.seed,
            output_file=output_file,
            temp_dir=args.output_dir,
        )
        print(f"Generated {output_file} ({test_count} tests)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
