# Datasource normalization

Community dashboards from grafana.com reference their datasource in ways that do
not resolve against an arbitrary Grafana. `fetch_dashboard.py` rewrites them.

## The two forms

**Legacy (`__inputs`)** — a top-level `__inputs` entry and string references:

```json
"__inputs": [
  {"name": "DS_PROMETHEUS", "type": "datasource", "pluginId": "prometheus"}
],
"panels": [
  {"datasource": "${DS_PROMETHEUS}", "targets": [{"datasource": "${DS_PROMETHEUS}"}]}
]
```

**Modern (object)** — an inline object with a hard-coded uid:

```json
"panels": [
  {"datasource": {"type": "prometheus", "uid": "P1809F7CD0C75ACF3"}}
]
```

## The transform

1. Remove `__inputs`, `__requires`, top-level `id`, top-level `uid`. Grafana
   assigns a fresh uid; the folder + title identify the dashboard.
2. Ensure `templating.list` has:
   ```json
   {"name": "datasource", "type": "datasource", "query": "prometheus",
    "label": "Datasource", "current": {}, "hide": 0, "refresh": 1}
   ```
3. Every `datasource` field, recursively:
   | before | after |
   |---|---|
   | `"${DS_PROMETHEUS}"` (or any `"${DS_*}"`) | `"${datasource}"` |
   | a bare `"Prometheus"` / a prometheus `__inputs` name | `"${datasource}"` |
   | `{"type": "prometheus", "uid": "..."}` | `{"type": "prometheus", "uid": "${datasource}"}` |
   | `{"type": "prometheus"}` / `{}` (no type) | `{"type": "prometheus", "uid": "${datasource}"}` |
   | `null` | `null` (unchanged — panel inherits) |
   | `{"type": "loki", ...}` / `"-- Mixed --"` | unchanged |
4. Add `"__source": "<origin>, fetched <date>"`.

A dashboard with **no** prometheus reference anywhere → the script exits non-zero
(it is not a fit for this plugin).

## What the kube-prometheus-stack sidecar does

From the chart's `grafana.sidecar.dashboards` defaults:
- **selector:** ConfigMaps/Secrets with label `grafana_dashboard: "1"`
  (`sidecar.dashboards.label` / `labelValue`).
- **folder:** `sidecar.dashboards.folderAnnotation: grafana_folder` — the
  ConfigMap annotation names the Grafana folder; `provider.foldersFromFilesStructure: true`
  lets the sidecar create it.
- Each **data key** in the ConfigMap becomes one dashboard. Multi-key ConfigMaps
  are fine.
- The `datasource` template variable resolves against Grafana's default
  Prometheus datasource on first load; a viewer can switch it.

## The 1 MB limit

A ConfigMap's data cannot exceed ~1 MiB (etcd). A single rich dashboard is
usually 30–150 KB, so several fit. If a rendered ConfigMap is over the limit:
- split the dashboards into `<app>-dashboards` and `<app>-dashboards-2` (two
  templates, or a `range` that buckets files), or
- trim the dashboard: delete unused rows/panels and library-panel definitions,
  or drop embedded PNGs in `panels[].options`.
