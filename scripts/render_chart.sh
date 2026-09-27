#!/usr/bin/env bash
# Render a chart the way Argo CD will, without modifying the chart directory.
#
#   render_chart.sh <chart-dir> <release> <namespace> [--values <file>]... [--include-crds] [-- <extra helm template args>]
#
# Copies the chart to a temp dir (removed on every exit path), builds its dependencies there
# with helm_deps.sh (private repo config; the caller's Helm repo list, Chart.lock and charts/
# are never touched), then runs `helm template <release> <copy> -n <namespace> ...` and writes
# the render to stdout. Release name = the Argo CD Application name; namespace = its destination.
# (A chart with `file://../...` dependencies must be rendered where those relative paths resolve.)
# Exit 0 on success; exit 1 with ONE `error:` line on stderr.
set -euo pipefail

die() { echo "error: $*" >&2; exit 1; }
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[ $# -ge 3 ] || die "usage: render_chart.sh <chart-dir> <release> <namespace> [--values <file>]... [--include-crds] [-- <helm args>]"
chart="${1%/}" release="$2" ns="$3"; shift 3
[ -f "$chart/Chart.yaml" ] || die "no Chart.yaml in $chart"

args=()
while [ $# -gt 0 ]; do
  case "$1" in
    --values) [ -f "${2:-}" ] || die "values file not found: ${2:-}"; args+=(-f "$2"); shift 2 ;;
    --include-crds) args+=(--include-crds); shift ;;
    --) shift; args+=("$@"); break ;;
    *) die "unknown option $1" ;;
  esac
done

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
name="$(basename "$(cd "$chart" && pwd)")"
cp -r "$chart" "$tmp/$name"

bash "$here/helm_deps.sh" "$tmp/$name" || exit 1
if ! helm template "$release" "$tmp/$name" -n "$ns" ${args[@]+"${args[@]}"} > "$tmp/out.yaml" 2> "$tmp/err"; then
  die "helm template failed for $chart: $(head -c 300 "$tmp/err" | tr '\n' ' ')"
fi
cat "$tmp/out.yaml"
