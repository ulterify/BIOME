#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PICT_BIN="/home/thomas/source/pict/build/cli/pict"
MODEL_FILE="$SCRIPT_DIR/pict-model.txt"
MAX_YES_VALUES="1 2 3 4 5 6 7 8 9"
ORDERS="2 3 4 5"
ITERATIONS=10
SEED=132
OUTPUT_DIR="$SCRIPT_DIR/pict-testsets"
OUTPUT_FILE=""
PLOT_FILE=""
PLOT_SCRIPT_FILE=""
HTML_FILE=""
VTK_FILE=""

usage() {
  cat <<EOF
Usage: ./generate-pict-test-count-table.sh [OPTIONS]

Run PICT for each max-yes/order pair and write a 2D TSV table of test counts.

Options:
  --max-yes-values LIST  Space- or comma-separated max-yes values (default: "1 2 3 4 5 6 7 8 9")
  --max-yes N            Add one max-yes value; may be repeated
  --orders LIST          Space- or comma-separated PICT orders (default: "2 3 4 5")
  --order N              Add one order; may be repeated
  --iterations N         PICT /b:N seed attempts, keeping the smallest suite (default: 10)
  --seed N               PICT /r:N base random seed (default: 132)
  --model FILE           Base PICT model file (default: ./pict-model.txt)
  --pict-bin FILE        PICT executable (default: /home/thomas/source/pict/build/cli/pict)
  --output-dir DIR       Output directory (default: ./pict-testsets)
  --output-file FILE     Explicit table output path
  --plot-file FILE       Explicit SVG plot output path
  --plot-script FILE     Explicit gnuplot script output path
  --html-file FILE       Explicit Plotly HTML output path
  --vtk-file FILE        Explicit VTK PolyData (.vtp) output path
  --help                 Show this help and exit

Examples:
  ./generate-pict-test-count-table.sh
  ./generate-pict-test-count-table.sh --max-yes-values "2 3 4" --orders "3 5"
  ./generate-pict-test-count-table.sh --max-yes 3 --max-yes 4 --order 2 --order 5
EOF
}

MAX_YES_ARGS=()
ORDER_ARGS=()
while (($# > 0)); do
  case "$1" in
    --help|-h)
      usage
      exit 0
      ;;
    --max-yes-values)
      [[ $# -ge 2 ]] || { printf 'Missing value for --max-yes-values\n' >&2; exit 2; }
      MAX_YES_VALUES="${2//,/ }"
      MAX_YES_ARGS=()
      shift 2
      ;;
    --max-yes)
      [[ $# -ge 2 ]] || { printf 'Missing value for --max-yes\n' >&2; exit 2; }
      if ((${#MAX_YES_ARGS[@]} == 0)); then
        MAX_YES_VALUES=""
      fi
      MAX_YES_ARGS+=("$2")
      shift 2
      ;;
    --orders)
      [[ $# -ge 2 ]] || { printf 'Missing value for --orders\n' >&2; exit 2; }
      ORDERS="${2//,/ }"
      ORDER_ARGS=()
      shift 2
      ;;
    --order)
      [[ $# -ge 2 ]] || { printf 'Missing value for --order\n' >&2; exit 2; }
      if ((${#ORDER_ARGS[@]} == 0)); then
        ORDERS=""
      fi
      ORDER_ARGS+=("$2")
      shift 2
      ;;
    --iterations)
      [[ $# -ge 2 ]] || { printf 'Missing value for --iterations\n' >&2; exit 2; }
      ITERATIONS="$2"
      shift 2
      ;;
    --seed)
      [[ $# -ge 2 ]] || { printf 'Missing value for --seed\n' >&2; exit 2; }
      SEED="$2"
      shift 2
      ;;
    --model)
      [[ $# -ge 2 ]] || { printf 'Missing value for --model\n' >&2; exit 2; }
      MODEL_FILE="$2"
      shift 2
      ;;
    --pict-bin)
      [[ $# -ge 2 ]] || { printf 'Missing value for --pict-bin\n' >&2; exit 2; }
      PICT_BIN="$2"
      shift 2
      ;;
    --output-dir)
      [[ $# -ge 2 ]] || { printf 'Missing value for --output-dir\n' >&2; exit 2; }
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --output-file)
      [[ $# -ge 2 ]] || { printf 'Missing value for --output-file\n' >&2; exit 2; }
      OUTPUT_FILE="$2"
      shift 2
      ;;
    --plot-file)
      [[ $# -ge 2 ]] || { printf 'Missing value for --plot-file\n' >&2; exit 2; }
      PLOT_FILE="$2"
      shift 2
      ;;
    --plot-script)
      [[ $# -ge 2 ]] || { printf 'Missing value for --plot-script\n' >&2; exit 2; }
      PLOT_SCRIPT_FILE="$2"
      shift 2
      ;;
    --html-file)
      [[ $# -ge 2 ]] || { printf 'Missing value for --html-file\n' >&2; exit 2; }
      HTML_FILE="$2"
      shift 2
      ;;
    --vtk-file)
      [[ $# -ge 2 ]] || { printf 'Missing value for --vtk-file\n' >&2; exit 2; }
      VTK_FILE="$2"
      shift 2
      ;;
    *)
      printf 'Unknown argument: %s\n\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ((${#MAX_YES_ARGS[@]} == 0)); then
  read -r -a MAX_YES_ARGS <<< "$MAX_YES_VALUES"
fi

if ((${#ORDER_ARGS[@]} == 0)); then
  read -r -a ORDER_ARGS <<< "$ORDERS"
fi

if ! [[ "$ITERATIONS" =~ ^[1-9][0-9]*$ ]]; then
  printf 'Iterations must be a positive integer, got: %s\n' "$ITERATIONS" >&2
  exit 2
fi

if ! [[ "$SEED" =~ ^[0-9]+$ ]]; then
  printf 'Seed must be a non-negative integer, got: %s\n' "$SEED" >&2
  exit 2
fi

for max_yes in "${MAX_YES_ARGS[@]}"; do
  if ! [[ "$max_yes" =~ ^[0-9]+$ ]]; then
    printf 'Max-yes values must be non-negative integers, got: %s\n' "$max_yes" >&2
    exit 2
  fi
done

for order in "${ORDER_ARGS[@]}"; do
  if ! [[ "$order" =~ ^[1-9][0-9]*$ ]]; then
    printf 'Orders must be positive integers, got: %s\n' "$order" >&2
    exit 2
  fi
done

join_by_underscore() {
  local IFS=_
  printf '%s' "$*"
}

numeric_min() {
  local min="$1"
  shift
  local value
  for value in "$@"; do
    if ((value < min)); then
      min="$value"
    fi
  done
  printf '%s' "$min"
}

numeric_max() {
  local max="$1"
  shift
  local value
  for value in "$@"; do
    if ((value > max)); then
      max="$value"
    fi
  done
  printf '%s' "$max"
}

mkdir -p "$OUTPUT_DIR"
GENERATED_MODEL_FILES=()
cleanup_generated_models() {
  rm -f "${GENERATED_MODEL_FILES[@]}"
}
trap cleanup_generated_models EXIT

orders_label="$(join_by_underscore "${ORDER_ARGS[@]}")"
max_yes_label="$(join_by_underscore "${MAX_YES_ARGS[@]}")"
if [[ -z "$OUTPUT_FILE" ]]; then
  OUTPUT_FILE="$OUTPUT_DIR/test-counts.orders-${orders_label}.max-yes-${max_yes_label}.tsv"
fi
if [[ -z "$PLOT_FILE" ]]; then
  PLOT_FILE="${OUTPUT_FILE%.tsv}.svg"
fi
if [[ -z "$PLOT_SCRIPT_FILE" ]]; then
  PLOT_SCRIPT_FILE="${OUTPUT_FILE%.tsv}.gnuplot"
fi
if [[ -z "$HTML_FILE" ]]; then
  HTML_FILE="${OUTPUT_FILE%.tsv}.html"
fi
if [[ -z "$VTK_FILE" ]]; then
  VTK_FILE="${OUTPUT_FILE%.tsv}.vtp"
fi
PLOT_DATA_FILE="${OUTPUT_FILE%.tsv}.plot-data.tsv"

{
  printf 'max_yes'
  for order in "${ORDER_ARGS[@]}"; do
    printf '\torder_%s' "$order"
  done
  printf '\n'

  for max_yes in "${MAX_YES_ARGS[@]}"; do
    generated_model_file="$(mktemp "$OUTPUT_DIR/pict-model.max-yes-${max_yes}.XXXXXX.txt")"
    GENERATED_MODEL_FILES+=("$generated_model_file")
    {
      cat "$MODEL_FILE"
      printf '\n# At most %s variables may be "yes".\n' "$max_yes"
      "$SCRIPT_DIR/generate-max-yes-constraints.sh" "$max_yes" "$MODEL_FILE"
    } > "$generated_model_file"

    printf '%s' "$max_yes"
    for order in "${ORDER_ARGS[@]}"; do
      test_count="$("$PICT_BIN" "$generated_model_file" "/o:$order" "/b:$ITERATIONS" "/r:$SEED" | awk 'END { if (NR > 0) print NR - 1; else print 0 }')"
      printf '\t%s' "$test_count"
    done
    printf '\n'
  done
} > "$OUTPUT_FILE"

{
  awk -F '\t' '
    NR == 1 {
      for (column = 2; column <= NF; column++) {
        order = $column
        sub(/^order_/, "", order)
        orders[column] = order
      }
      next
    }
    {
      max_yes = $1
      for (column = 2; column <= NF; column++) {
        printf "%s\t%s\t%s\n", orders[column], max_yes, $column
      }
      printf "\n"
    }
  ' "$OUTPUT_FILE"

  if ((${#MAX_YES_ARGS[@]} == 1)); then
    awk -F '\t' '
      NR == 1 {
        for (column = 2; column <= NF; column++) {
          order = $column
          sub(/^order_/, "", order)
          orders[column] = order
        }
        next
      }
      NR == 2 {
        max_yes = $1 + 1
        for (column = 2; column <= NF; column++) {
          printf "%s\t%s\t%s\n", orders[column], max_yes, $column
        }
        printf "\n"
      }
    ' "$OUTPUT_FILE"
  fi
} > "$PLOT_DATA_FILE"

awk -F '\t' '
  NR == 1 {
    column_count = NF - 1
    for (column = 2; column <= NF; column++) {
      order = $column
      sub(/^order_/, "", order)
      orders[column - 1] = order
    }
    next
  }
  {
    row_count++
    max_yes[row_count] = $1
    for (column = 2; column <= NF; column++) {
      counts[row_count, column - 1] = $column
    }
  }
  END {
    point_count = row_count * column_count
    poly_count = row_count > 1 && column_count > 1 ? (row_count - 1) * (column_count - 1) : 0

    print "<?xml version=\"1.0\"?>"
    print "<VTKFile type=\"PolyData\" version=\"0.1\" byte_order=\"LittleEndian\">"
    print "  <PolyData>"
    printf "    <Piece NumberOfPoints=\"%d\" NumberOfPolys=\"%d\">\n", point_count, poly_count
    print "      <PointData Scalars=\"test_count\">"
    print "        <DataArray type=\"Float32\" Name=\"test_count\" format=\"ascii\">"
    printf "          "
    for (row = 1; row <= row_count; row++) {
      for (column = 1; column <= column_count; column++) {
        printf "%s ", counts[row, column]
      }
    }
    print ""
    print "        </DataArray>"
    print "      </PointData>"
    print "      <FieldData>"
    print "        <DataArray type=\"Int32\" Name=\"orders\" NumberOfTuples=\"" column_count "\" format=\"ascii\">"
    printf "          "
    for (column = 1; column <= column_count; column++) {
      printf "%s ", orders[column]
    }
    print ""
    print "        </DataArray>"
    print "        <DataArray type=\"Int32\" Name=\"max_yes_values\" NumberOfTuples=\"" row_count "\" format=\"ascii\">"
    printf "          "
    for (row = 1; row <= row_count; row++) {
      printf "%s ", max_yes[row]
    }
    print ""
    print "        </DataArray>"
    print "      </FieldData>"
    print "      <Points>"
    print "        <DataArray type=\"Float32\" NumberOfComponents=\"3\" format=\"ascii\">"
    for (row = 1; row <= row_count; row++) {
      printf "          "
      for (column = 1; column <= column_count; column++) {
        printf "%s %s %s ", orders[column], max_yes[row], counts[row, column]
      }
      print ""
    }
    print "        </DataArray>"
    print "      </Points>"
    print "      <Polys>"
    print "        <DataArray type=\"Int32\" Name=\"connectivity\" format=\"ascii\">"
    if (poly_count > 0) {
      for (row = 1; row < row_count; row++) {
        printf "          "
        for (column = 1; column < column_count; column++) {
          p0 = (row - 1) * column_count + (column - 1)
          p1 = p0 + 1
          p2 = p0 + column_count + 1
          p3 = p0 + column_count
          printf "%d %d %d %d ", p0, p1, p2, p3
        }
        print ""
      }
    }
    print "        </DataArray>"
    print "        <DataArray type=\"Int32\" Name=\"offsets\" format=\"ascii\">"
    if (poly_count > 0) {
      printf "          "
      for (poly = 1; poly <= poly_count; poly++) {
        printf "%d ", poly * 4
      }
      print ""
    }
    print "        </DataArray>"
    print "      </Polys>"
    print "    </Piece>"
    print "  </PolyData>"
    print "</VTKFile>"
  }
' "$OUTPUT_FILE" > "$VTK_FILE"

x_min="$(numeric_min "${ORDER_ARGS[@]}")"
x_max="$(numeric_max "${ORDER_ARGS[@]}")"
y_min="$(numeric_min "${MAX_YES_ARGS[@]}")"
y_max="$(numeric_max "${MAX_YES_ARGS[@]}")"

cat > "$PLOT_SCRIPT_FILE" <<EOF
set terminal svg size 1400,900 enhanced font "Arial,12"
set output "$PLOT_FILE"
set title "PICT test count by order and max-yes"
set xlabel "Order"
set ylabel "Max yes"
set zlabel "Tests"
set xrange [$((x_min - 1)):$((x_max + 1))]
set yrange [$((y_min - 1)):$((y_max + 1))]
set datafile separator "\t"
set grid
set ticslevel 0
set view 58,36
set pm3d depthorder interpolate 2,2
set hidden3d
set palette defined (0 "#1d4ed8", 0.45 "#60a5fa", 0.65 "#facc15", 1 "#dc2626")
set colorbox vertical
splot "$PLOT_DATA_FILE" using 1:2:3 with pm3d notitle
EOF

gnuplot "$PLOT_SCRIPT_FILE"

orders_json="$(printf '%s\n' "${ORDER_ARGS[@]}" | awk 'BEGIN { printf "[" } { if (NR > 1) printf ","; printf "%s", $1 } END { print "]" }')"
max_yes_json="$(printf '%s\n' "${MAX_YES_ARGS[@]}" | awk 'BEGIN { printf "[" } { if (NR > 1) printf ","; printf "%s", $1 } END { print "]" }')"
counts_json="$(
  awk -F '\t' '
    NR == 1 {
      next
    }
    {
      if (row_count > 0) {
        rows = rows ","
      }
      row = "["
      for (column = 2; column <= NF; column++) {
        if (column > 2) {
          row = row ","
        }
        row = row $column
      }
      row = row "]"
      rows = rows row
      row_count++
    }
    END {
      printf "[%s]\n", rows
    }
  ' "$OUTPUT_FILE"
)"

cat > "$HTML_FILE" <<EOF
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PICT test count surface</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    html, body {
      height: 100%;
      margin: 0;
      font-family: Arial, sans-serif;
    }
    #plot {
      width: 100vw;
      height: 100vh;
    }
  </style>
</head>
<body>
  <div id="plot"></div>
  <script>
    const orders = $orders_json;
    const maxYes = $max_yes_json;
    const counts = $counts_json;

    const colorScale = [
      [0.00, '#1d4ed8'],
      [0.45, '#60a5fa'],
      [0.65, '#facc15'],
      [1.00, '#dc2626']
    ];

    const flatCounts = counts.flat();
    const minCount = Math.min(...flatCounts);
    const maxCount = Math.max(...flatCounts);

    function hexToRgb(hex) {
      const value = hex.replace('#', '');
      return [
        parseInt(value.slice(0, 2), 16),
        parseInt(value.slice(2, 4), 16),
        parseInt(value.slice(4, 6), 16)
      ];
    }

    function interpolateColor(low, high, t) {
      const a = hexToRgb(low);
      const b = hexToRgb(high);
      return 'rgb(' + a.map((component, index) =>
        Math.round(component + (b[index] - component) * t)
      ).join(',') + ')';
    }

    function countColor(value) {
      const denominator = maxCount === minCount ? 1 : maxCount - minCount;
      const normalized = (value - minCount) / denominator;
      for (let index = 1; index < colorScale.length; index++) {
        const [stop, color] = colorScale[index];
        const [previousStop, previousColor] = colorScale[index - 1];
        if (normalized <= stop) {
          return interpolateColor(previousColor, color, (normalized - previousStop) / (stop - previousStop));
        }
      }
      return colorScale[colorScale.length - 1][1];
    }

    function makeBarMesh() {
      const x = [];
      const y = [];
      const z = [];
      const i = [];
      const j = [];
      const k = [];
      const vertexcolor = [];
      const text = [];
      const halfWidth = 0.38;

      function addVertex(xValue, yValue, zValue, color, label) {
        x.push(xValue);
        y.push(yValue);
        z.push(zValue);
        vertexcolor.push(color);
        text.push(label);
        return x.length - 1;
      }

      function addTriangle(a, b, c) {
        i.push(a);
        j.push(b);
        k.push(c);
      }

      maxYes.forEach((maxValue, rowIndex) => {
        orders.forEach((orderValue, columnIndex) => {
          const height = counts[rowIndex][columnIndex];
          const color = countColor(height);
          const label = 'order=' + orderValue + '<br>max yes=' + maxValue + '<br>tests=' + height;
          const x0 = orderValue - halfWidth;
          const x1 = orderValue + halfWidth;
          const y0 = maxValue - halfWidth;
          const y1 = maxValue + halfWidth;
          const base = [
            addVertex(x0, y0, 0, color, label),
            addVertex(x1, y0, 0, color, label),
            addVertex(x1, y1, 0, color, label),
            addVertex(x0, y1, 0, color, label),
            addVertex(x0, y0, height, color, label),
            addVertex(x1, y0, height, color, label),
            addVertex(x1, y1, height, color, label),
            addVertex(x0, y1, height, color, label)
          ];

          [
            [0, 1, 2], [0, 2, 3],
            [4, 6, 5], [4, 7, 6],
            [0, 4, 5], [0, 5, 1],
            [1, 5, 6], [1, 6, 2],
            [2, 6, 7], [2, 7, 3],
            [3, 7, 4], [3, 4, 0]
          ].forEach(([a, b, c]) => addTriangle(base[a], base[b], base[c]));
        });
      });

      return {
        type: 'mesh3d',
        x,
        y,
        z,
        i,
        j,
        k,
        vertexcolor,
        text,
        hovertemplate: '%{text}<extra></extra>',
        flatshading: true,
        showscale: false,
        visible: false,
        name: 'Bars'
      };
    }

    const data = [{
      type: 'surface',
      x: orders,
      y: maxYes,
      z: counts,
      colorscale: colorScale,
      colorbar: { title: 'Tests' },
      contours: {
        z: {
          show: true,
          usecolormap: true,
          highlightcolor: '#111827',
          project: { z: true }
        }
      },
      hovertemplate: 'order=%{x}<br>max yes=%{y}<br>tests=%{z}<extra></extra>',
      name: 'Surface'
    }, makeBarMesh()];

    const layout = {
      title: 'PICT test count by order and max-yes',
      margin: { l: 0, r: 0, t: 48, b: 0 },
      scene: {
        xaxis: { title: 'Order', dtick: 1 },
        yaxis: { title: 'Max yes', dtick: 1 },
        zaxis: { title: 'Tests' },
        camera: {
          eye: { x: 1.55, y: 1.55, z: 1.05 }
        }
      },
      updatemenus: [{
        type: 'buttons',
        direction: 'right',
        x: 0.02,
        y: 0.98,
        xanchor: 'left',
        yanchor: 'top',
        buttons: [{
          label: 'Surface',
          method: 'update',
          args: [{ visible: [true, false] }]
        }, {
          label: 'Bars',
          method: 'update',
          args: [{ visible: [false, true] }]
        }]
      }]
    };

    Plotly.newPlot('plot', data, layout, { responsive: true });
  </script>
</body>
</html>
EOF

printf 'Generated %s\n' "$OUTPUT_FILE"
printf 'Generated %s\n' "$PLOT_FILE"
printf 'Generated %s\n' "$PLOT_SCRIPT_FILE"
printf 'Generated %s\n' "$HTML_FILE"
printf 'Generated %s\n' "$VTK_FILE"
