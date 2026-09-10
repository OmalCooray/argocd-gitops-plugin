#!/usr/bin/env bash
# Render the grafana-dashboards ConfigMap template inside a podinfo wrapper and
# assert its shape. Needs helm + network (podinfo dep). No cluster.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$ROOT/tests/.out/dashboard"
rm -rf "$OUT"; mkdir -p "$OUT/templates" "$OUT/grafana-dashboards"

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
podinfo: {}
grafanaDashboards:
  enabled: true
YAML

# normalized dashboard from the fixture
python "$ROOT/skills/argocd-grafana-dashboards/scripts/fetch_dashboard.py" \
  "$ROOT/tests/fixtures/raw-dashboard.json" > "$OUT/grafana-dashboards/podinfo-test.json"

# the template (must match the one the skill documents)
cat > "$OUT/templates/grafana-dashboards.yaml" <<'YAML'
{{- if (.Values.grafanaDashboards).enabled }}
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ .Chart.Name }}-dashboards
  labels:
    grafana_dashboard: "1"
    app.kubernetes.io/name: {{ .Chart.Name }}
    app.kubernetes.io/managed-by: argocd-gitops-plugin
  annotations:
    grafana_folder: {{ .Values.grafanaDashboards.folder | default .Chart.Name | quote }}
data:
  {{- range $path, $_ := .Files.Glob "grafana-dashboards/*.json" }}
  {{ base $path }}: |
    {{- $.Files.Get $path | nindent 4 }}
  {{- end }}
{{- end }}
YAML

helm dependency build "$OUT" >/dev/null
helm template podinfo "$OUT" --show-only templates/grafana-dashboards.yaml > "$OUT/rendered.yaml"
cat "$OUT/rendered.yaml"
echo "---"
grep -q '^kind: ConfigMap$' "$OUT/rendered.yaml"                         || { echo "FAIL: not a ConfigMap"; exit 1; }
grep -q 'name: podinfo-dashboards' "$OUT/rendered.yaml"                   || { echo "FAIL: name"; exit 1; }
grep -q 'grafana_dashboard: "1"' "$OUT/rendered.yaml"                     || { echo "FAIL: sidecar label"; exit 1; }
grep -q 'grafana_folder: "podinfo"' "$OUT/rendered.yaml"                  || { echo "FAIL: folder annotation"; exit 1; }
grep -q 'podinfo-test.json: |' "$OUT/rendered.yaml"                       || { echo "FAIL: data key"; exit 1; }
python - "$OUT/rendered.yaml" <<'PY'
import sys, yaml, json
cm = yaml.safe_load(open(sys.argv[1]))
body = cm["data"]["podinfo-test.json"]
d = json.loads(body)                       # the embedded value must be valid JSON
assert "__source" in d
assert "${DS_" not in body
print("embedded dashboard JSON parses; datasource normalized")
PY
echo "OK: grafana-dashboards ConfigMap renders with a normalized dashboard"
