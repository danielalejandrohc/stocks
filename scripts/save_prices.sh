#!/bin/bash
set -euo pipefail

# Usage:
#   scripts/save_prices.sh TICKER
# or with no args to run a default list.

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="python"
SCRIPT="$ROOT_DIR/loader/save_minute_prices.py"

run_one() {
  local t="$1"
  echo "Saving prices for $t"
  $PYTHON "$SCRIPT" "$t"
}

if [[ $# -ge 1 ]]; then
  run_one "$1"
  exit 0
fi

# Default list (adjust as needed)
list=(
  "NET" "ABNB" "CRM" "RDDT" "PLTR" "SPOT" "WMT" "SMCI"
  "AMD" "NVDA" "MSFT" "META" "AMZN" "MELI" "INTC" "TSLA"
  "IBM" "ORCL" "^GSPC" "BAC" "T" "C" "^NDX" "QQQ"
)

for t in "${list[@]}"; do
  run_one "$t"
done
