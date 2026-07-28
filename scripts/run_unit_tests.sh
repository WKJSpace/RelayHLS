#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/common.sh"

for variant in $(variants); do
  echo "[$variant] generator unit tests"
  python3 -m unittest discover \
    -s "$ROOT/variants/$variant/tests" \
    -p 'test_*.py'
done
