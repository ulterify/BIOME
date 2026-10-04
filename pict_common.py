#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import itertools
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable


BINARY_PARAM_RE = re.compile(r"^\s*([^:#][^:]*):\s*yes\s*,\s*no\s*$")


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

    point_scalars = " ".join(str(count) for row in counts for count in row)
    order_values = " ".join(str(order) for order in orders)
    max_yes_values_text = " ".join(str(max_yes) for max_yes in max_yes_values)
    points_lines = []
    for max_yes, row in zip(max_yes_values, counts):
        points_lines.append(
            "          " + " ".join(
                f"{order} {max_yes} {count}" for order, count in zip(orders, row)
            ) + " "
        )

    connectivity_lines = []
    offsets: list[str] = []
    column_count = len(orders)
    poly_index = 0
    for row_index in range(len(max_yes_values) - 1):
        cells = []
        for column_index in range(len(orders) - 1):
            p0 = row_index * column_count + column_index
            p1 = p0 + 1
            p2 = p0 + column_count + 1
            p3 = p0 + column_count
            cells.append(f"{p0} {p1} {p2} {p3}")
            poly_index += 1
            offsets.append(str(poly_index * 4))
        connectivity_lines.append("          " + " ".join(cells) + " ")

    path.write_text(
        "\n".join(
            [
                '<?xml version="1.0"?>',
                '<VTKFile type="PolyData" version="0.1" byte_order="LittleEndian">',
                "  <PolyData>",
                f'    <Piece NumberOfPoints="{point_count}" NumberOfPolys="{poly_count}">',
                '      <PointData Scalars="test_count">',
                '        <DataArray type="Float32" Name="test_count" format="ascii">',
                f"          {point_scalars} ",
                "        </DataArray>",
                "      </PointData>",
                "      <FieldData>",
                f'        <DataArray type="Int32" Name="orders" NumberOfTuples="{len(orders)}" format="ascii">',
                f"          {order_values} ",
                "        </DataArray>",
                f'        <DataArray type="Int32" Name="max_yes_values" NumberOfTuples="{len(max_yes_values)}" format="ascii">',
                f"          {max_yes_values_text} ",
                "        </DataArray>",
                "      </FieldData>",
                "      <Points>",
                '        <DataArray type="Float32" NumberOfComponents="3" format="ascii">',
                *points_lines,
                "        </DataArray>",
                "      </Points>",
                "      <Polys>",
                '        <DataArray type="Int32" Name="connectivity" format="ascii">',
                *connectivity_lines,
                "        </DataArray>",
                '        <DataArray type="Int32" Name="offsets" format="ascii">',
                "          " + " ".join(offsets) + " " if offsets else "",
                "        </DataArray>",
                "      </Polys>",
                "    </Piece>",
                "  </PolyData>",
                "</VTKFile>",
                "",
            ]
        )
    )


def write_plotly_html(path: Path, orders: list[int], max_yes_values: list[int], counts: list[list[int]]) -> None:
    orders_json = json.dumps(orders)
    max_yes_json = json.dumps(max_yes_values)
    counts_json = json.dumps(counts)
    title = html.escape("PICT test count surface")
    path.write_text(f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    html, body {{ height: 100%; margin: 0; font-family: Arial, sans-serif; }}
    #plot {{ width: 100vw; height: 100vh; }}
  </style>
</head>
<body>
  <div id="plot"></div>
  <script>
    const orders = {orders_json};
    const maxYes = {max_yes_json};
    const counts = {counts_json};
    const colorScale = [[0.00, '#1d4ed8'], [0.45, '#60a5fa'], [0.65, '#facc15'], [1.00, '#dc2626']];
    const flatCounts = counts.flat();
    const minCount = Math.min(...flatCounts);
    const maxCount = Math.max(...flatCounts);

    function hexToRgb(hex) {{
      const value = hex.replace('#', '');
      return [parseInt(value.slice(0, 2), 16), parseInt(value.slice(2, 4), 16), parseInt(value.slice(4, 6), 16)];
    }}

    function interpolateColor(low, high, t) {{
      const a = hexToRgb(low);
      const b = hexToRgb(high);
      return 'rgb(' + a.map((component, index) => Math.round(component + (b[index] - component) * t)).join(',') + ')';
    }}

    function countColor(value) {{
      const denominator = maxCount === minCount ? 1 : maxCount - minCount;
      const normalized = (value - minCount) / denominator;
      for (let index = 1; index < colorScale.length; index++) {{
        const [stop, color] = colorScale[index];
        const [previousStop, previousColor] = colorScale[index - 1];
        if (normalized <= stop) {{
          return interpolateColor(previousColor, color, (normalized - previousStop) / (stop - previousStop));
        }}
      }}
      return colorScale[colorScale.length - 1][1];
    }}

    function makeBarMesh() {{
      const x = [], y = [], z = [], i = [], j = [], k = [], vertexcolor = [], text = [];
      const halfWidth = 0.38;
      function addVertex(xValue, yValue, zValue, color, label) {{
        x.push(xValue); y.push(yValue); z.push(zValue); vertexcolor.push(color); text.push(label);
        return x.length - 1;
      }}
      function addTriangle(a, b, c) {{ i.push(a); j.push(b); k.push(c); }}
      maxYes.forEach((maxValue, rowIndex) => {{
        orders.forEach((orderValue, columnIndex) => {{
          const height = counts[rowIndex][columnIndex];
          const color = countColor(height);
          const label = 'order=' + orderValue + '<br>max yes=' + maxValue + '<br>tests=' + height;
          const x0 = orderValue - halfWidth, x1 = orderValue + halfWidth;
          const y0 = maxValue - halfWidth, y1 = maxValue + halfWidth;
          const base = [
            addVertex(x0, y0, 0, color, label), addVertex(x1, y0, 0, color, label),
            addVertex(x1, y1, 0, color, label), addVertex(x0, y1, 0, color, label),
            addVertex(x0, y0, height, color, label), addVertex(x1, y0, height, color, label),
            addVertex(x1, y1, height, color, label), addVertex(x0, y1, height, color, label)
          ];
          [[0,1,2], [0,2,3], [4,6,5], [4,7,6], [0,4,5], [0,5,1],
           [1,5,6], [1,6,2], [2,6,7], [2,7,3], [3,7,4], [3,4,0]]
            .forEach(([a, b, c]) => addTriangle(base[a], base[b], base[c]));
        }});
      }});
      return {{
        type: 'mesh3d', x, y, z, i, j, k, vertexcolor, text,
        hovertemplate: '%{{text}}<extra></extra>', flatshading: true,
        showscale: false, visible: false, name: 'Bars'
      }};
    }}

    const data = [{{
      type: 'surface',
      x: orders,
      y: maxYes,
      z: counts,
      colorscale: colorScale,
      colorbar: {{ title: 'Tests' }},
      contours: {{ z: {{ show: true, usecolormap: true, highlightcolor: '#111827', project: {{ z: true }} }} }},
      hovertemplate: 'order=%{{x}}<br>max yes=%{{y}}<br>tests=%{{z}}<extra></extra>',
      name: 'Surface'
    }}, makeBarMesh()];

    const layout = {{
      title: 'PICT test count by order and max-yes',
      margin: {{ l: 0, r: 0, t: 48, b: 0 }},
      scene: {{
        xaxis: {{ title: 'Order', dtick: 1 }},
        yaxis: {{ title: 'Max yes', dtick: 1 }},
        zaxis: {{ title: 'Tests' }},
        camera: {{ eye: {{ x: 1.55, y: 1.55, z: 1.05 }} }}
      }},
      updatemenus: [{{
        type: 'buttons', direction: 'right', x: 0.02, y: 0.98, xanchor: 'left', yanchor: 'top',
        buttons: [
          {{ label: 'Surface', method: 'update', args: [{{ visible: [true, false] }}] }},
          {{ label: 'Bars', method: 'update', args: [{{ visible: [false, true] }}] }}
        ]
      }}]
    }};
    Plotly.newPlot('plot', data, layout, {{ responsive: true }});
  </script>
</body>
</html>
""")
