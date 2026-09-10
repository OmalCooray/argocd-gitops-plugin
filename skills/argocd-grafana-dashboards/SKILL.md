---
name: argocd-grafana-dashboards
description: Import an open-source Grafana dashboard into an app's wrapper chart — commit the JSON under charts/<app>/grafana-dashboards/, normalize its datasource references, and render it as a ConfigMap the kube-prometheus-stack Grafana sidecar loads into a per-app folder. Load when an app is scraped but has no dashboard, or the user asks to add / import a Grafana dashboard.
---

# Grafana dashboards for an app

## Mechanism

kube-prometheus-stack's Grafana runs a sidecar that watches for ConfigMaps
labelled `grafana_dashboard: "1"` and loads each data key as a dashboard; the
annotation `grafana_folder: <name>` places it in a folder.

You commit the dashboard JSON under the wrapper chart and render one ConfigMap:

```
charts/<app>/
├── grafana-dashboards/
│   └── <slug>.json                     # normalized community JSON, committed verbatim
└── templates/
    └── grafana-dashboards.yaml          # ConfigMap: one data key per grafana-dashboards/*.json
```

### The template (`charts/<app>/templates/grafana-dashboards.yaml`)

```yaml
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
```

- Gate: `grafanaDashboards.enabled` (nil-safe). The command sets it `true`.
- Folder: `grafanaDashboards.folder`, default the chart name → one folder per app.
- The rendered ConfigMap must stay under 1 MB (etcd). If it exceeds it: split the
  dashboards across two ConfigMaps, or trim unused rows. See
  `reference/datasource-normalization.md`.
- A `grafana-dashboards/` or `templates/` change bumps `charts/<app>/Chart.yaml`
  `version`.

## Precondition — the app must already be scraped

A working ServiceMonitor / PodMonitor and metrics visible in Prometheus
(`/api/v1/query`). No metrics → **stop**. The dashboard would be all "No data".
Adding a ServiceMonitor is `/argocd-add-manifest`. Provisioning an exporter for
an app that emits nothing (Metabase, a bare MySQL) is a separate workflow
(`argocd-exporters` / `/argocd-observe`).

## Choosing a dashboard

- Search [grafana.com/grafana/dashboards](https://grafana.com/grafana/dashboards/).
- Prefer one built for **the exporter you actually run** — e.g. an
  Airflow-statsd-exporter dashboard, not a generic StatsD one; the Percona MySQL
  dashboard for `mysqld_exporter`.
- Check the revision date and the `__requires` Grafana version.
- Skim its panel queries — do the metric names look like what your exporter
  emits?

## Steps

1. `python ${CLAUDE_PLUGIN_ROOT}/skills/argocd-grafana-dashboards/scripts/fetch_dashboard.py <source> > charts/<app>/grafana-dashboards/<slug>.json`
   — `<source>` = a grafana.com id (`12345` / `12345:8`), an `https://` URL, or a
   local `.json` path.
2. **Sanity-check the metric names.** Grep the JSON for `expr` / metric names and
   compare a sample against live Prometheus:
   `curl -s 'http://<prometheus>/api/v1/label/__name__/values' | ...`. If most
   are absent, it is the wrong dashboard for this exporter — pick another.
3. Create `charts/<app>/templates/grafana-dashboards.yaml` (the template above)
   if it does not exist; add the `grafanaDashboards` stanza to
   `charts/<app>/values.yaml`:
   ```yaml
   grafanaDashboards:
     enabled: true
     # folder: <app>        # optional; defaults to the chart name
   ```
4. Verify: `helm template <app> charts/<app>` renders the ConfigMap with the
   dashboard as a data key; `... | kubectl apply --dry-run=server -f -` if a
   cluster is reachable; the rendered ConfigMap is < 1 MB.
5. Bump `charts/<app>/Chart.yaml` `version`.

## Datasource normalization

`fetch_dashboard.py` does it — see `reference/datasource-normalization.md` for
the transform and why. Summary: strip `__inputs`/`__requires`/`id`/`uid`, add a
`datasource` template variable (type `datasource`, query `prometheus`), rewrite
every Prometheus datasource reference to `${datasource}`. Portable across
environments regardless of the Prometheus datasource UID.

## Verify after sync

After `/argocd-sync <app> <env>`:
- Grafana `GET /api/search?query=<dashboard title>` returns it, `folderTitle`
  == `<app>`.
- Open it — panels render data, not "No data". A panel showing "No data" while
  the app is scraped usually means the dashboard queries a metric name your
  exporter does not emit (step 2), or a label the dashboard expects
  (`job`, `instance`) is not what your ServiceMonitor produces.
