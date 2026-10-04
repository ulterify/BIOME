#!/usr/bin/env bash
set -euo pipefail

MAX_YES="${1:-${MAX_YES:-3}}"
MODEL_FILE="${2:-${MODEL_FILE:-pict-model.txt}}"

if ! [[ "$MAX_YES" =~ ^[0-9]+$ ]]; then
  printf 'MAX_YES must be a non-negative integer, got: %s\n' "$MAX_YES" >&2
  exit 2
fi

awk -v max_yes="$MAX_YES" '
  function trim(value) {
    gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
    return value
  }

  function emit_combo(depth, start, i, j) {
    if (depth > combo_size) {
      if (max_yes == 0) {
        printf "[%s] = \"no\";\n", params[combo[1]]
        return
      }

      printf "IF "
      for (i = 1; i <= max_yes; i++) {
        if (i > 1) {
          printf " AND "
        }
        printf "[%s] = \"yes\"", params[combo[i]]
      }
      printf " THEN [%s] = \"no\";\n", params[combo[combo_size]]
      return
    }

    for (j = start; j <= param_count - (combo_size - depth); j++) {
      combo[depth] = j
      emit_combo(depth + 1, j + 1)
    }
  }

  /^[[:space:]]*#/ || /^[[:space:]]*$/ {
    next
  }

  /^[^:]+:[[:space:]]*yes[[:space:]]*,[[:space:]]*no[[:space:]]*$/ {
    split($0, parts, ":")
    params[++param_count] = trim(parts[1])
  }

  END {
    if (param_count == 0) {
      print "No yes/no parameters found in model." > "/dev/stderr"
      exit 1
    }

    if (max_yes >= param_count) {
      exit 0
    }

    combo_size = max_yes + 1
    emit_combo(1, 1)
  }
' "$MODEL_FILE"
