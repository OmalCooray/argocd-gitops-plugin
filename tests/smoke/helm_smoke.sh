#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$ROOT/tests/.out/smoke-podinfo"
rm -rf "$OUT"; mkdir -p "$OUT"

python "$ROOT/tests/render.py" "$ROOT/templates/Chart.yaml.tmpl" \
  "$ROOT/tests/fixtures/podinfo.vars.json" > "$OUT/Chart.yaml"
python "$ROOT/tests/render.py" "$ROOT/templates/values.yaml.tmpl" \
  "$ROOT/tests/fixtures/podinfo.vars.json" > "$OUT/values.yaml"

helm dependency build "$OUT"
helm lint "$OUT"
helm template "$OUT" >/dev/null
echo "OK: wrapper chart builds, lints, and templates"
