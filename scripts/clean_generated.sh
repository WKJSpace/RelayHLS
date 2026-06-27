#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
find "$ROOT" \( -name hls -o -name logs -o -name reports -o -name backups -o -name .Xil -o -name .cache -o -name __pycache__ \) -type d -prune -exec rm -rf {} +
find "$ROOT" \( -name '*.log' -o -name '*.rpt' -o -name '*.jou' -o -name '*.str' -o -name '*.hlscompile_summary' -o -name '*.hlsrun_*_summary' -o -name '*.pyc' \) -type f -delete
