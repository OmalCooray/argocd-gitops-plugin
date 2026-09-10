#!/usr/bin/env bash
# Render the servicemonitor starter inside a real podinfo wrapper chart and
# assert the ServiceMonitor comes out correct. Needs helm + network. No cluster.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$ROOT/tests/.out/extra-manifest"
STARTER="$ROOT/skills/argocd-extra-manifests/reference/starters/servicemonitor.yaml"
rm -rf "$OUT"; mkdir -p "$OUT/templates"

cat > "$OUT/Chart.yaml" <<'YAML'
apiVersion: v2
name: podinfo
version: 0.1.0
appVersion: "6.9.0"
dependencies:
  - name: podinfo
    version: 6.9.0
    repository: https://stefanprodan.github.io/podinfo
YAML

cat > "$OUT/values.yaml" <<'YAML'
podinfo:
  fullnameOverride: podinfo
serviceMonitor:
  enabled: true
  selectorLabels:
    app.kubernetes.io/name: podinfo
  port: http
  path: /metrics
  interval: 15s
  labels:
    release: kube-prometheus-stack
YAML

cp "$STARTER" "$OUT/templates/servicemonitor.yaml"

helm dependency build "$OUT" >/dev/null
helm template t "$OUT" --show-only templates/servicemonitor.yaml > "$OUT/rendered.yaml"
cat "$OUT/rendered.yaml"
echo "---"
# assertions
grep -q '^kind: ServiceMonitor$' "$OUT/rendered.yaml"                  || { echo "FAIL: not a ServiceMonitor"; exit 1; }
grep -q 'app.kubernetes.io/name: podinfo' "$OUT/rendered.yaml"         || { echo "FAIL: missing name label"; exit 1; }
grep -q 'app.kubernetes.io/managed-by: argocd-gitops-plugin' "$OUT/rendered.yaml" || { echo "FAIL: missing managed-by"; exit 1; }
grep -q 'release: kube-prometheus-stack' "$OUT/rendered.yaml"          || { echo "FAIL: extra label not applied"; exit 1; }
grep -qE '^\s+-?\s*port: http$' "$OUT/rendered.yaml"                   || { echo "FAIL: named port not http"; exit 1; }
grep -qE '^\s+interval: 15s$' "$OUT/rendered.yaml"                     || { echo "FAIL: interval override lost"; exit 1; }
grep -qE '^\s+path: /metrics$' "$OUT/rendered.yaml"                    || { echo "FAIL: path"; exit 1; }
python -c "import sys,yaml; d=yaml.safe_load(open(sys.argv[1])); assert d['apiVersion']=='monitoring.coreos.com/v1'; assert d['spec']['selector']['matchLabels']['app.kubernetes.io/name']=='podinfo'; print('yaml parse + shape OK')" "$OUT/rendered.yaml"

# gate check: disabled -> nothing rendered
DISABLED="$(helm template t "$OUT" --set serviceMonitor.enabled=false --show-only templates/servicemonitor.yaml 2>&1 || true)"
echo "$DISABLED" | grep -q 'ServiceMonitor' && { echo "FAIL: rendered while disabled"; exit 1; } || true

echo "OK: servicemonitor starter renders, overrides apply, gate works"
