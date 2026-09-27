#!/usr/bin/env bash
# List the CustomResourceDefinition names a Helm chart renders.
#
#   list_crds.sh <chart-dir> [--namespace <ns>] [--values <file>]
#   list_crds.sh --filter          # rendered YAML on stdin -> CRD names (no helm needed)
#
# The chart is copied to a temp dir so the caller's Chart.lock / charts/ are never touched;
# `helm template` needs --include-crds or a chart's crds/ directory is silently skipped.
# stdout: CRD names only, sorted, unique, one per line (empty = the chart renders none).
# Exit 0 on success (even with no CRDs); exit 1 with one `error:` line on stderr if helm fails.
set -euo pipefail

filter() {
  # One document per `---`; take metadata.name only when the document's top-level kind is a CRD.
  tr -d '\r' | awk '
    function flush() { if (k && n != "") print n; k = 0; n = ""; m = 0 }
    /^---/ { flush(); next }
    /^kind:[[:space:]]+CustomResourceDefinition[[:space:]]*$/ { k = 1; next }
    /^metadata:[[:space:]]*$/ { m = 1; next }
    m && /^  name:[[:space:]]/ { n = $2; gsub(/["\047]/, "", n); m = 0; next }
    /^[A-Za-z]/ { m = 0 }
    END { flush() }
  ' | sort -u
}

if [ "${1:-}" = "--filter" ]; then
  filter
  exit 0
fi

chart="" ns="default" values=""
while [ $# -gt 0 ]; do
  case "$1" in
    --namespace) ns="${2:?--namespace needs a value}"; shift 2 ;;
    --values) values="${2:?--values needs a value}"; shift 2 ;;
    -*) echo "error: unknown option $1" >&2; exit 1 ;;
    *) chart="$1"; shift ;;
  esac
done
[ -n "$chart" ] && [ -f "${chart%/}/Chart.yaml" ] || { echo "error: usage: list_crds.sh <chart-dir> [--namespace <ns>] [--values <file>]" >&2; exit 1; }
[ -z "$values" ] || [ -f "$values" ] || { echo "error: values file not found: $values" >&2; exit 1; }

chart="${chart%/}"
name="$(basename "$(cd "$chart" && pwd)")"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cp -r "$chart" "$tmp/$name"

if ! helm dependency build "$tmp/$name" >&2; then
  echo "error: helm dependency build failed for $chart" >&2; exit 1
fi
args=(template "$name" "$tmp/$name" -n "$ns" --include-crds)
[ -z "$values" ] || args+=(-f "$values")
if ! helm "${args[@]}" > "$tmp/rendered.yaml" 2> "$tmp/err"; then
  echo "error: helm template failed for $chart: $(head -c 300 "$tmp/err" | tr '\n' ' ')" >&2; exit 1
fi
filter < "$tmp/rendered.yaml"
