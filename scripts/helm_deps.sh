#!/usr/bin/env bash
# Build a chart's Helm dependencies WITHOUT touching the user's Helm repo list.
#
#   helm_deps.sh <chart-dir>
#   helm_deps.sh <chart-dir> --print-repos    # only print the distinct http(s) repo URLs (sorted), no helm
#
# Helm 3.x refuses `helm dependency build` when a dependency's repository URL is not in the
# repo list ("no repository definition for <url>"). This script registers each distinct http(s)
# URL under a stable name (r-<12 hex of sha1(url)>) in a PRIVATE repositories.yaml/cache
# (temp, removed on exit) unless the caller already exported HELM_REPOSITORY_CONFIG/CACHE.
# oci:// and file:// repositories need no repo definition and are skipped. `@alias` / `alias:`
# repositories cannot be resolved without the user's repo list: replace them with the URL.
# Uses `helm dependency build` when Chart.lock exists (reproducible, exact locked versions),
# otherwise `helm dependency update` (there is no lock to build from yet; this creates it).
# A chart with no dependencies is a no-op. Exit 0 on success; exit 1 with ONE `error:` line.
set -euo pipefail

die() { echo "error: $*" >&2; exit 1; }

chart="${1:-}"; mode="${2:-}"
[ -n "$chart" ] || die "usage: helm_deps.sh <chart-dir> [--print-repos]"
chart="${chart%/}"
[ -f "$chart/Chart.yaml" ] || die "no Chart.yaml in $chart"

py=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import yaml' >/dev/null 2>&1; then py="$c"; break; fi
done
[ -n "$py" ] || die "python with PyYAML is required (pip install pyyaml)"

# Prints "<name> <url>" per distinct http(s) repository, sorted by URL; exits 3 with a message on aliases.
repos="$("$py" - "$chart/Chart.yaml" <<'PY'
import hashlib, sys, yaml
try:
    doc = yaml.safe_load(open(sys.argv[1], encoding="utf-8")) or {}
except Exception as e:
    print("error: cannot parse %s: %s" % (sys.argv[1], str(e).splitlines()[0]))
    sys.exit(3)
urls = set()
for d in (doc.get("dependencies") or []):
    r = str(d.get("repository") or "").strip()
    if not r or r.startswith(("oci://", "file://")):
        continue
    if r.startswith(("http://", "https://")):
        urls.add(r)
    else:
        print("error: dependency repository '%s' is an alias; replace it with the repository URL" % r)
        sys.exit(3)
for u in sorted(urls):
    print("r-%s %s" % (hashlib.sha1(u.encode()).hexdigest()[:12], u))
PY
)" || { echo "${repos:-error: could not read dependencies of $chart}" | head -n1 >&2; exit 1; }

if [ "$mode" = "--print-repos" ]; then
  [ -z "$repos" ] || printf '%s\n' "$repos" | cut -d' ' -f2
  exit 0
fi

grep -Eq '^dependencies:' "$chart/Chart.yaml" || exit 0   # own-app chart: nothing to build

tmp=""
cleanup() { [ -z "$tmp" ] || rm -rf "$tmp"; }
trap cleanup EXIT
if [ -z "${HELM_REPOSITORY_CONFIG:-}" ] || [ -z "${HELM_REPOSITORY_CACHE:-}" ]; then
  tmp="$(mktemp -d)"
  : > "$tmp/repositories.yaml"
  export HELM_REPOSITORY_CONFIG="$tmp/repositories.yaml" HELM_REPOSITORY_CACHE="$tmp/cache"
  mkdir -p "$tmp/cache"
fi

err="$(mktemp)"
trap 'cleanup; rm -f "$err"' EXIT
oneline() { head -c 300 "$err" | tr '\n' ' '; }

while read -r name url; do
  [ -n "$name" ] || continue
  helm repo add "$name" "$url" >/dev/null 2>"$err" || die "helm repo add failed for $url: $(oneline)"
done <<< "$repos"

if [ -f "$chart/Chart.lock" ]; then sub=build; else sub=update; fi
helm dependency "$sub" "$chart" >/dev/null 2>"$err" || die "helm dependency $sub failed for $chart: $(oneline)"
