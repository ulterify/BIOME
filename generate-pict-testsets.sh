#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PICT_BIN="/home/thomas/source/pict/build/cli/pict"
MODEL_FILE="$SCRIPT_DIR/pict-model.txt"
MAX_YES=4
ORDERS="2 3 4 5"
ITERATIONS=10
SEED=132
OUTPUT_DIR="$SCRIPT_DIR/pict-testsets"

usage() {
  cat <<EOF
Usage: ./generate-pict-testsets.sh [OPTIONS]

Generate PICT testsets from the base model plus a generated max-yes constraint.

Options:
  --max-yes N       Maximum number of variables that may be "yes" (default: 4)
  --orders LIST     Space- or comma-separated PICT orders to generate (default: "2 3 4 5")
  --order N         Add one order to generate; may be repeated
  --iterations N    PICT /b:N seed attempts, keeping the smallest suite (default: 10)
  --seed N          PICT /r:N base random seed (default: 132)
  --model FILE      Base PICT model file (default: ./pict-model.txt)
  --pict-bin FILE   PICT executable (default: /home/thomas/source/pict/build/cli/pict)
  --output-dir DIR  Output directory (default: ./pict-testsets)
  --help            Show this help and exit

Examples:
  ./generate-pict-testsets.sh
  ./generate-pict-testsets.sh --max-yes 3 --orders "2 4 5"
  ./generate-pict-testsets.sh --order 3 --order 5 --iterations 20 --seed 140
EOF
}

ORDER_ARGS=()
while (($# > 0)); do
  case "$1" in
    --help|-h)
      usage
      exit 0
      ;;
    --max-yes)
      [[ $# -ge 2 ]] || { printf 'Missing value for --max-yes\n' >&2; exit 2; }
      MAX_YES="$2"
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
    *)
      printf 'Unknown argument: %s\n\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ((${#ORDER_ARGS[@]} == 0)); then
  read -r -a ORDER_ARGS <<< "$ORDERS"
fi

if ! [[ "$MAX_YES" =~ ^[0-9]+$ ]]; then
  printf 'MAX_YES must be a non-negative integer, got: %s\n' "$MAX_YES" >&2
  exit 2
fi

if ! [[ "$ITERATIONS" =~ ^[1-9][0-9]*$ ]]; then
  printf 'Iterations must be a positive integer, got: %s\n' "$ITERATIONS" >&2
  exit 2
fi

if ! [[ "$SEED" =~ ^[0-9]+$ ]]; then
  printf 'Seed must be a non-negative integer, got: %s\n' "$SEED" >&2
  exit 2
fi

mkdir -p "$OUTPUT_DIR"

GENERATED_MODEL_FILE="$(mktemp "$OUTPUT_DIR/pict-model.max-yes-${MAX_YES}.XXXXXX.txt")"
trap 'rm -f "$GENERATED_MODEL_FILE"' EXIT

{
  cat "$MODEL_FILE"
  printf '\n# At most %s variables may be "yes".\n' "$MAX_YES"
  "$SCRIPT_DIR/generate-max-yes-constraints.sh" "$MAX_YES" "$MODEL_FILE"
} > "$GENERATED_MODEL_FILE"

for order in "${ORDER_ARGS[@]}"; do
  if ! [[ "$order" =~ ^[1-9][0-9]*$ ]]; then
    printf 'Order must be a positive integer, got: %s\n' "$order" >&2
    exit 2
  fi

  output_file="$OUTPUT_DIR/order-${order}.max-yes-${MAX_YES}.tsv"
  "$PICT_BIN" "$GENERATED_MODEL_FILE" "/o:$order" "/b:$ITERATIONS" "/r:$SEED" > "$output_file"
  line_count="$(wc -l < "$output_file")"
  test_count="$((line_count - 1))"
  printf 'Generated %s (%d tests)\n' "$output_file" "$test_count"
done
