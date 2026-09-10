# Datasource normalization

<!-- owner: argocd-grafana-dashboards skill · last reviewed: 2026-09-10 -->

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

- **selector:** ConfigMaps/Secrets with label `grafana_dashboard: "1"`
  (`grafana.sidecar.dashboards.label` / `labelValue`) — on by default.
- **folder — needs enabling.** By default the sidecar drops every dashboard in
  Grafana's root/"General" folder and **ignores the `grafana_folder` annotation**.
  For the per-app folders this plugin's ConfigMaps ask for, the
  `kube-prometheus-stack` wrapper chart must set:
  ```yaml
  kube-prometheus-stack:
    grafana:
      sidecar:
        dashboards:
          folderAnnotation: grafana_folder
          searchNamespace: ALL
          provider:
            foldersFromFilesStructure: true
  ```
  This is a one-time change to the **monitoring platform's** wrapper chart, not
  the app's. If `/argocd-add-dashboard` finds the dashboard loads into no folder,
  this is why — add it to `charts/kube-prometheus-stack/values.yaml` (or the env
  overlay) and re-sync that app. A Grafana pod restart is needed for the sidecar
  env change to take effect.
- **namespace — needs enabling.** By default the k8s-sidecar only watches
  ConfigMaps in **Grafana's own namespace** (e.g. `monitoring`). This plugin's
  app dashboard ConfigMaps live in the **app's** namespace, so the sidecar must
  be told to watch all namespaces:
  `grafana.sidecar.dashboards.searchNamespace: ALL` (in the block above).
  kube-prometheus-stack often ships this defaulted to `ALL` already — verify with
  `kubectl -n monitoring get deploy kube-prometheus-stack-grafana -o yaml | grep -A2 SEARCH`
  (or inspect the sidecar container's env). If it is not `ALL`, per-app
  ConfigMaps are silently ignored.
- Each **data key** in the ConfigMap becomes one dashboard. Multi-key ConfigMaps
  are fine.
- The `datasource` template variable is given
  `"current": {"text": "default", "value": "default"}` so it resolves to the
  org's default datasource on load (leaving it `{}` renders every panel
  "No data"); a viewer can switch it.
- Grafana's `/api/search` returns folders too (`type: dash-folder`) — filter
  `type=dash-db` to list only dashboards.

## The 1 MB limit

A ConfigMap's data cannot exceed ~1 MiB (etcd). A single rich dashboard is
usually 30–150 KB, so several fit. If a rendered ConfigMap is over the limit:
- split the dashboards into `<app>-dashboards` and `<app>-dashboards-2` (two
  templates, or a `range` that buckets files), or
- trim the dashboard: delete unused rows/panels and library-panel definitions,
  or drop embedded PNGs in `panels[].options`.
