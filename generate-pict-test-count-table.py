#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from pict_common import (
    generated_model_text,
    label,
    parse_int_list,
    render_gnuplot,
    run_pict,
    write_count_table,
    write_gnuplot_script,
    write_plot_data,
    write_plotly_html,
    write_vtp,
)


SCRIPT_DIR = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run PICT for each max-yes/order pair and write a 2D TSV table of test counts."
    )
    parser.add_argument("--max-yes-values", default="1 2 3 4 5 6 7 8 9", help="space- or comma-separated max-yes values")
    parser.add_argument("--max-yes", action="append", type=int, help="add one max-yes value; may be repeated")
    parser.add_argument("--orders", default="2 3 4 5", help="space- or comma-separated PICT orders")
    parser.add_argument("--order", action="append", type=int, help="add one order; may be repeated")
    parser.add_argument("--iterations", type=int, default=10, help="PICT /b:N seed attempts")
    parser.add_argument("--seed", type=int, default=132, help="PICT /r:N base random seed")
    parser.add_argument("--model", type=Path, default=SCRIPT_DIR / "pict-model.txt", help="base PICT model file")
    parser.add_argument("--pict-bin", type=Path, default=Path("pict"), help="PICT executable")
    parser.add_argument("--output-dir", type=Path, default=SCRIPT_DIR / "pict-testsets", help="output directory")
    parser.add_argument("--output-file", type=Path, help="explicit table output path")
    parser.add_argument("--plot-file", type=Path, help="explicit SVG plot output path")
    parser.add_argument("--plot-script", type=Path, help="explicit gnuplot script output path")
    parser.add_argument("--html-file", type=Path, help="explicit Plotly HTML output path")
    parser.add_argument("--vtk-file", type=Path, help="explicit VTK PolyData (.vtp) output path")
    args = parser.parse_args()

    max_yes_values = args.max_yes if args.max_yes else parse_int_list(args.max_yes_values)
    orders = args.order if args.order else parse_int_list(args.orders)

    if not max_yes_values:
        parser.error("at least one max-yes value is required")
    if not orders:
        parser.error("at least one order is required")
    if any(value < 0 for value in max_yes_values):
        parser.error("max-yes values must be non-negative integers")
    if any(order <= 0 for order in orders):
        parser.error("orders must be positive integers")
    if args.iterations <= 0:
        parser.error("--iterations must be a positive integer")
    if args.seed < 0:
        parser.error("--seed must be a non-negative integer")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    orders_label = label(orders)
    max_yes_label = label(max_yes_values)

    output_file = args.output_file or args.output_dir / f"test-counts.orders-{orders_label}.max-yes-{max_yes_label}.tsv"
    plot_file = args.plot_file or output_file.with_suffix(".svg")
    plot_script = args.plot_script or output_file.with_suffix(".gnuplot")
    html_file = args.html_file or output_file.with_suffix(".html")
    vtk_file = args.vtk_file or output_file.with_suffix(".vtp")
    plot_data_file = output_file.with_suffix(".plot-data.tsv")

    counts: list[list[int]] = []
    for max_yes in max_yes_values:
        model_text = generated_model_text(args.model, max_yes)
        row: list[int] = []
        for order in orders:
            test_count, _ = run_pict(
                pict_bin=args.pict_bin,
                model_text=model_text,
                order=order,
                iterations=args.iterations,
                seed=args.seed,
                temp_dir=args.output_dir,
            )
            row.append(test_count)
        counts.append(row)

    write_count_table(output_file, orders, max_yes_values, counts)
    write_plot_data(plot_data_file, orders, max_yes_values, counts)
    write_gnuplot_script(plot_script, plot_file, plot_data_file, orders, max_yes_values)
    try:
        render_gnuplot(plot_script)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        parser.error(f"gnuplot failed: {exc}")
    write_plotly_html(html_file, orders, max_yes_values, counts)
    write_vtp(vtk_file, orders, max_yes_values, counts)

    for path in (output_file, plot_file, plot_script, html_file, vtk_file):
        print(f"Generated {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
