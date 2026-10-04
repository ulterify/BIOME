#!/usr/bin/env python3
from __future__ import annotations

import csv
import itertools
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

from jinja2 import Environment, FileSystemLoader, select_autoescape


BINARY_PARAM_RE = re.compile(r"^\s*([^:#][^:]*):\s*yes\s*,\s*no\s*$")
TEMPLATE_ENV = Environment(
    loader=FileSystemLoader(Path(__file__).resolve().parent / "templates"),
    autoescape=select_autoescape(("html", "j2")),
)


def parse_int_list(value: str) -> list[int]:
    return [int(part) for part in value.replace(",", " ").split()]


def label(values: Iterable[int]) -> str:
    return "_".join(str(value) for value in values)


def yes_no_parameters(model_text: str) -> list[str]:
    params: list[str] = []
    for line in model_text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = BINARY_PARAM_RE.match(line)
        if match:
            params.append(match.group(1).strip())
    if not params:
        raise ValueError("No yes/no parameters found in model.")
    return params


def max_yes_constraints(model_text: str, max_yes: int) -> list[str]:
    params = yes_no_parameters(model_text)
    if max_yes >= len(params):
        return []

    lines: list[str] = []
    for combo in itertools.combinations(params, max_yes + 1):
        if max_yes == 0:
            lines.append(f'[{combo[0]}] = "no";')
            continue
        predicates = " AND ".join(f'[{param}] = "yes"' for param in combo[:max_yes])
        lines.append(f'IF {predicates} THEN [{combo[max_yes]}] = "no";')
    return lines


def generated_model_text(base_model: Path, max_yes: int) -> str:
    model_text = base_model.read_text()
    lines = [model_text.rstrip(), "", f'# At most {max_yes} variables may be "yes".']
    lines.extend(max_yes_constraints(model_text, max_yes))
    return "\n".join(lines) + "\n"


def validate_non_negative(name: str, value: int) -> None:
    if value < 0:
        raise ValueError(f"{name} must be a non-negative integer, got: {value}")


def validate_positive(name: str, value: int) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer, got: {value}")


def run_pict(
    *,
    pict_bin: Path,
    model_text: str,
    order: int,
    iterations: int,
    seed: int,
    output_file: Path | None = None,
    temp_dir: Path | None = None,
) -> tuple[int, str | None]:
    validate_positive("Order", order)
    validate_positive("Iterations", iterations)
    validate_non_negative("Seed", seed)

    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".txt",
        prefix="pict-model.",
        dir=temp_dir,
        delete=False,
    ) as temp_model:
        temp_model.write(model_text)
        temp_model_path = Path(temp_model.name)

    try:
        command = [
            str(pict_bin),
            str(temp_model_path),
            f"/o:{order}",
            f"/b:{iterations}",
            f"/r:{seed}",
        ]
        result = subprocess.run(command, check=True, text=True, stdout=subprocess.PIPE)
    finally:
        temp_model_path.unlink(missing_ok=True)

    output = result.stdout
    line_count = 0 if not output else output.count("\n")
    if output and not output.endswith("\n"):
        line_count += 1
    test_count = max(0, line_count - 1)

    if output_file is not None:
        output_file.write_text(output)
        return test_count, None
    return test_count, output


def write_count_table(path: Path, orders: list[int], max_yes_values: list[int], counts: list[list[int]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["max_yes", *[f"order_{order}" for order in orders]])
        for max_yes, row in zip(max_yes_values, counts):
            writer.writerow([max_yes, *row])


def write_plot_data(path: Path, orders: list[int], max_yes_values: list[int], counts: list[list[int]]) -> None:
    with path.open("w") as handle:
        for max_yes, row in zip(max_yes_values, counts):
            for order, count in zip(orders, row):
                handle.write(f"{order}\t{max_yes}\t{count}\n")
            handle.write("\n")
        if len(max_yes_values) == 1:
            duplicate_max_yes = max_yes_values[0] + 1
            for order, count in zip(orders, counts[0]):
                handle.write(f"{order}\t{duplicate_max_yes}\t{count}\n")
            handle.write("\n")


def write_gnuplot_script(path: Path, plot_file: Path, plot_data: Path, orders: list[int], max_yes_values: list[int]) -> None:
    x_min, x_max = min(orders), max(orders)
    y_min, y_max = min(max_yes_values), max(max_yes_values)
    path.write_text(
        "\n".join(
            [
                'set terminal svg size 1400,900 enhanced font "Arial,12"',
                f'set output "{plot_file}"',
                'set title "PICT test count by order and max-yes"',
                'set xlabel "Order"',
                'set ylabel "Max yes"',
                'set zlabel "Tests"',
                f"set xrange [{x_min - 1}:{x_max + 1}]",
                f"set yrange [{y_min - 1}:{y_max + 1}]",
                'set datafile separator "\\t"',
                "set grid",
                "set ticslevel 0",
                "set view 58,36",
                "set pm3d depthorder interpolate 2,2",
                "set hidden3d",
                'set palette defined (0 "#1d4ed8", 0.45 "#60a5fa", 0.65 "#facc15", 1 "#dc2626")',
                "set colorbox vertical",
                f'splot "{plot_data}" using 1:2:3 with pm3d notitle',
                "",
            ]
        )
    )


def render_gnuplot(script_path: Path) -> None:
    subprocess.run(["gnuplot", str(script_path)], check=True)


def write_vtp(path: Path, orders: list[int], max_yes_values: list[int], counts: list[list[int]]) -> None:
    point_count = len(orders) * len(max_yes_values)
    poly_count = max(0, len(orders) - 1) * max(0, len(max_yes_values) - 1)

    root = ET.Element(
        "VTKFile",
        {"type": "PolyData", "version": "0.1", "byte_order": "LittleEndian"},
    )
    poly_data = ET.SubElement(root, "PolyData")
    piece = ET.SubElement(
        poly_data,
        "Piece",
        {"NumberOfPoints": str(point_count), "NumberOfPolys": str(poly_count)},
    )

    point_data = ET.SubElement(piece, "PointData", {"Scalars": "test_count"})
    scalar_array = ET.SubElement(
        point_data,
        "DataArray",
        {"type": "Float32", "Name": "test_count", "format": "ascii"},
    )
    scalar_array.text = " ".join(str(count) for row in counts for count in row)

    field_data = ET.SubElement(piece, "FieldData")
    orders_array = ET.SubElement(
        field_data,
        "DataArray",
        {
            "type": "Int32",
            "Name": "orders",
            "NumberOfTuples": str(len(orders)),
            "format": "ascii",
        },
    )
    orders_array.text = " ".join(str(order) for order in orders)
    max_yes_array = ET.SubElement(
        field_data,
        "DataArray",
        {
            "type": "Int32",
            "Name": "max_yes_values",
            "NumberOfTuples": str(len(max_yes_values)),
            "format": "ascii",
        },
    )
    max_yes_array.text = " ".join(str(max_yes) for max_yes in max_yes_values)

    points = ET.SubElement(piece, "Points")
    points_array = ET.SubElement(
        points,
        "DataArray",
        {"type": "Float32", "NumberOfComponents": "3", "format": "ascii"},
    )
    points_array.text = " ".join(
        f"{order} {max_yes} {count}"
        for max_yes, row in zip(max_yes_values, counts)
        for order, count in zip(orders, row)
    )

    connectivity: list[str] = []
    offsets: list[str] = []
    column_count = len(orders)
    poly_index = 0
    for row_index in range(len(max_yes_values) - 1):
        for column_index in range(len(orders) - 1):
            p0 = row_index * column_count + column_index
            p1 = p0 + 1
            p2 = p0 + column_count + 1
            p3 = p0 + column_count
            connectivity.extend(str(point) for point in (p0, p1, p2, p3))
            poly_index += 1
            offsets.append(str(poly_index * 4))

    polys = ET.SubElement(piece, "Polys")
    connectivity_array = ET.SubElement(
        polys,
        "DataArray",
        {"type": "Int32", "Name": "connectivity", "format": "ascii"},
    )
    connectivity_array.text = " ".join(connectivity)
    offsets_array = ET.SubElement(
        polys,
        "DataArray",
        {"type": "Int32", "Name": "offsets", "format": "ascii"},
    )
    offsets_array.text = " ".join(offsets)

    ET.indent(root, space="  ")
    tree = ET.ElementTree(root)
    tree.write(path, encoding="unicode", xml_declaration=True)
    path.write_text(path.read_text() + "\n")


def write_plotly_html(path: Path, orders: list[int], max_yes_values: list[int], counts: list[list[int]]) -> None:
    rendered = PLOTLY_HTML_TEMPLATE.render(
        orders_json=json.dumps(orders),
        max_yes_json=json.dumps(max_yes_values),
        counts_json=json.dumps(counts),
    )
    path.write_text(rendered)
