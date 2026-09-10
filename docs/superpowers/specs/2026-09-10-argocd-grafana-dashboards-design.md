# argocd-gitops-plugin — Grafana Dashboards for an App

**Date:** 2026-09-10
**Status:** Approved (design phase)
**Author:** Omal Cooray (with Claude)

## Summary

Add an **opt-in** capability to bring an open-source Grafana dashboard into an
app's wrapper chart: the dashboard JSON is committed under
`charts/<app>/grafana-dashboards/`, normalized for datasource portability, and a
wrapper-chart template renders it as a ConfigMap the kube-prometheus-stack
Grafana sidecar picks up — placing it in a per-app Grafana folder.

This is spec **#2a**. It is the dashboard-delivery mechanism only. Spec **#2b**
(`argocd-exporters` + an `/argocd-observe` orchestrator) will add exporter
provisioning for apps that expose no metrics, and tie exporter → ServiceMonitor →
dashboard into one workflow.

It builds on the extra-manifests primitive (spec #1): the dashboard ConfigMap is
just another manifest in `charts/<app>/templates/`, following the same
conventions (values-gated, lives with the app, bumps the chart version).

## Background

kube-prometheus-stack's Grafana runs the `k8s-sidecar` container. It watches for
ConfigMaps labelled `grafana_dashboard: "1"` and loads each data key as a
dashboard; the annotation `grafana_folder: <name>` (chart default
`sidecar.dashboards.folderAnnotation`) puts it in a folder.

The plugin can already scrape an app (spec #1's `/argocd-add-manifest` adds a
ServiceMonitor). It has no way to add the dashboard that visualizes those
metrics. Doing it by hand means: find a dashboard on grafana.com, download it,
strip its `__inputs`, rewrite every datasource reference so it resolves against
this Grafana, wrap it in a labelled ConfigMap, and get the folder annotation
right. That is fiddly and repeated per app.

## Goals

- `charts/<app>/grafana-dashboards/*.json` — committed, normalized dashboard JSON.
- One wrapper-chart template, `charts/<app>/templates/grafana-dashboards.yaml`,
  that renders a single ConfigMap with a data key per JSON file, labelled and
  folder-annotated.
- A skill (`argocd-grafana-dashboards`) with the conventions, a fetch+normalize
  script, and datasource-normalization reference.
- A command, `/argocd-add-dashboard <app> <source>`, that fetches, normalizes,
  scaffolds the template + values stanza, verifies, and opens a PR.
- Datasource references normalized to a `datasource` template variable so the
  dashboard is portable across environments regardless of the Prometheus
  datasource UID.
- Per-app Grafana folders.

## Non-Goals

- **Not** auto-adding dashboards. `/argocd-add-chart`, `/argocd-deploy`,
  `/argocd-add-manifest` never add dashboards. Only `/argocd-add-dashboard`.
- Not exporter provisioning — an app with no metrics is out of scope here
  (report and stop; that is spec #2b).
- Not authoring dashboards from scratch — this imports existing community ones.
- Not the `/argocd-observe` orchestrator (spec #2b).
- Not managing Grafana itself, datasources, or alerting.

## Design

### Convention (documented in `argocd-repo-conventions` + the new skill)

```
charts/<app>/
├── grafana-dashboards/
│   └── <slug>.json                     # normalized community JSON, committed verbatim
└── templates/
    └── grafana-dashboards.yaml          # ConfigMap: one data key per grafana-dashboards/*.json
```

`templates/grafana-dashboards.yaml`:

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

- Gate: `grafanaDashboards.enabled` (nil-safe; the command sets it `true`).
- Folder: `grafanaDashboards.folder`, default the chart name → one folder per app.
- Data keys are the file basenames (`airflow-overview.json`).
- The ConfigMap must stay under 1 MB (etcd). If a rendered ConfigMap exceeds it,
  split into two ConfigMaps or trim unused rows from the dashboard.
- Lives with the app (same rule as extra-manifests). A `grafana-dashboards/` or
  `templates/` change bumps `charts/<app>/Chart.yaml` `version`.

### Datasource normalization

Community dashboards reference their datasource one of two ways:

- **Legacy** — a `__inputs` entry `{name: "DS_PROMETHEUS", type: "datasource",
  pluginId: "prometheus"}` and panels using the string `"${DS_PROMETHEUS}"`.
- **Modern** — panels using an object `{"type": "prometheus", "uid": "<uid>"}`.

Neither resolves reliably against an arbitrary Grafana. The normalization:

1. Remove `__inputs`, `__requires`, top-level `id`, and top-level `uid` (let
   Grafana assign a uid; the folder + title identify it).
2. Ensure `templating.list` contains
   `{"name": "datasource", "type": "datasource", "query": "prometheus",
   "current": {}, "hide": 0}`.
3. Rewrite every `datasource` field:
   - string `"${DS_PROMETHEUS}"` or any `"${DS_*}"` → `"${datasource}"`
   - object `{"type": "prometheus", "uid": "..."}` →
     `{"type": "prometheus", "uid": "${datasource}"}`
   - a bare string datasource *name* (older dashboards) → `"${datasource}"`
   - leave non-Prometheus datasources (e.g. `-- Mixed --`, `loki`) untouched;
     if the dashboard is fundamentally non-Prometheus, the script exits non-zero.
4. Add a top-level `"__source"` string: `grafana.com/dashboards/<id> revision <n>,
   fetched <date>` (or the URL / local path) for later re-fetching.
5. Pretty-print (2-space) so diffs are reviewable.

Full before/after examples: `reference/datasource-normalization.md`.

### New skill: `argocd-grafana-dashboards`

```
skills/argocd-grafana-dashboards/
├── SKILL.md
├── scripts/
│   └── fetch_dashboard.py
└── reference/
    └── datasource-normalization.md
```

**`SKILL.md`** — description triggers on "add a Grafana dashboard for <app>",
"import dashboard <id>", "the app has no dashboard / no visualization". Body:

- The convention above (`grafana-dashboards/` + the ConfigMap template + the
  sidecar label + `grafana_folder`).
- **Precondition — the app must already be scraped.** A working
  ServiceMonitor/PodMonitor and metrics visible in Prometheus. No metrics →
  stop; the dashboard would be all "No data". Adding a ServiceMonitor is
  `/argocd-add-manifest`; provisioning an exporter is spec #2b.
- Choosing a dashboard: search grafana.com; prefer one built for the **exporter
  you actually run** (e.g. an Airflow-statsd-exporter dashboard, not a generic
  StatsD one; the Percona MySQL dashboard for `mysqld_exporter`); check the
  revision date and `__requires` Grafana version; skim its panel queries.
- Run `scripts/fetch_dashboard.py <source> > charts/<app>/grafana-dashboards/<slug>.json`.
- **Sanity-check the metric names** the dashboard queries against
  `/api/v1/label/__name__/values` — if most are absent, it is the wrong
  dashboard for your exporter.
- The datasource normalization (see `reference/`).
- Verify after sync: Grafana `GET /api/search?query=<title>` returns it in the
  `<app>` folder; open it — panels show data, not "No data".

**`scripts/fetch_dashboard.py`** — Python 3 stdlib only. Usage:
`fetch_dashboard.py <id[:revision] | https-url | local-path>`.
- ID: GET `https://grafana.com/api/dashboards/<id>` for the latest revision (or
  use the given one), then GET
  `https://grafana.com/api/dashboards/<id>/revisions/<rev>/download`.
- URL: GET it. Local path: read it.
- Parse JSON. Apply the normalization (steps 1–5 above).
- Print normalized JSON to stdout. On fetch failure, invalid JSON, or a
  non-Prometheus dashboard: stderr message + non-zero exit.

**`reference/datasource-normalization.md`** — the transform rules with
before/after for both datasource forms; what the kube-prometheus-stack sidecar
does (`grafana_dashboard` label selector, `folderAnnotation: grafana_folder`,
`provider.foldersFromFilesStructure`); the 1 MB ConfigMap limit and remedies.

### New command: `/argocd-add-dashboard`

```
/argocd-add-dashboard <app> <source> [--name <slug>] [--env <env>]
```

- `<source>` — grafana.com ID (`12345` or `12345:8`), an `https://` URL, or a
  local `.json` path.
- `--name <slug>` — dashboard file slug (default: derived from the dashboard
  title).
- **Follows the interaction contract** (`references/interaction-style.md`).
- **Preconditions:** CWD is a GitOps repo; `charts/<app>/Chart.yaml` exists;
  `python` available.
- **Steps:**
  1. Load skills `argocd-grafana-dashboards` and `argocd-repo-conventions`.
  2. **Metrics check.** A ServiceMonitor/PodMonitor exists in
     `charts/<app>/templates/`, and — if a cluster is reachable — Prometheus has
     series for the app (`/api/v1/query?query={job=~".*<app>.*"}` or a known
     metric). No metrics → **stop**: report the dashboard would be empty; point
     at `/argocd-add-manifest` (ServiceMonitor) or spec #2b (exporter).
  3. Branch `add-dashboard/<app>-<slug>`.
  4. `python ${CLAUDE_PLUGIN_ROOT}/skills/argocd-grafana-dashboards/scripts/fetch_dashboard.py <source>`
     → write to `charts/<app>/grafana-dashboards/<slug>.json`.
  5. Grep the JSON for the metric names it queries; sample-check against
     `/api/v1/label/__name__/values`. If most are absent, warn (wrong dashboard)
     and have the user confirm or choose another.
  6. If `charts/<app>/templates/grafana-dashboards.yaml` is absent, create it
     (the Section 1 template). Add the `grafanaDashboards` stanza to
     `charts/<app>/values.yaml` (`enabled: true`, optional `folder`).
  7. Verify: `helm template <app> charts/<app>` renders the ConfigMap with the
     dashboard as a data key; `... | kubectl apply --dry-run=server -f -` if
     reachable; rendered ConfigMap < 1 MB.
  8. Bump `charts/<app>/Chart.yaml` `version`.
  9. Checkpoint → commit → PR (title `Add Grafana dashboard to <app>`; body:
     grafana.com source + revision, folder, the metrics it needs).
  10. Suggest `/argocd-sync <app> <env>`; functional check: after sync, Grafana
      `/api/search?query=<title>` returns it in the `<app>` folder and its panels
      render data.

### Edits to existing components

- **`skills/argocd-repo-conventions/SKILL.md`** — one line in the "Custom
  manifests" section pointing at `/argocd-add-dashboard` +
  `argocd-grafana-dashboards` for Grafana dashboards.
- **`skills/argocd-rollout/SKILL.md`** — functional-check table row: "Grafana
  dashboard → after sync it appears in Grafana's `<app>` folder
  (`/api/search`) and its panels render data (open one; not 'No data')".
- **`README.md`** — command table row + roadmap note (spec #2b).

## Testing

- **`tests/test_plugin_components.py`** — add `argocd-add-dashboard` to
  `EXPECTED_COMMANDS`, `argocd-grafana-dashboards` to `EXPECTED_SKILLS`.
- **`tests/fixtures/raw-dashboard.json`** (new) — a trimmed real community
  dashboard: has `__inputs` with `DS_PROMETHEUS`, `__requires`, a top-level
  `id`/`uid`, some panels using `"${DS_PROMETHEUS}"` and some using the object
  form `{"type":"prometheus","uid":"abc123"}`, plus one `templating` var.
- **`tests/test_fetch_dashboard.py`** (new, pytest, no network) — run
  `fetch_dashboard.py tests/fixtures/raw-dashboard.json` and assert:
  `__inputs`/`__requires`/top-level `id`/`uid` gone; a `templating.list` entry
  named `datasource` type `datasource`; no `${DS_` substring anywhere; every
  panel `datasource` is `"${datasource}"` or `{... "uid": "${datasource}"}`;
  `__source` present; stdout is valid JSON.
- **`tests/smoke/dashboard_smoke.sh`** (new) — build a `podinfo` wrapper, put the
  normalized fixture into `grafana-dashboards/podinfo-test.json`, add
  `templates/grafana-dashboards.yaml`, `helm template podinfo .` and assert: one
  `ConfigMap` named `podinfo-dashboards`, label `grafana_dashboard: "1"`,
  annotation `grafana_folder: podinfo`, a `data` key `podinfo-test.json` whose
  value parses as JSON.

## File structure

```
argocd-gitops-plugin/
├── commands/argocd-add-dashboard.md                          # NEW
├── skills/argocd-grafana-dashboards/
│   ├── SKILL.md                                              # NEW
│   ├── scripts/fetch_dashboard.py                            # NEW
│   └── reference/datasource-normalization.md                 # NEW
├── skills/argocd-repo-conventions/SKILL.md                   # EDIT
├── skills/argocd-rollout/SKILL.md                            # EDIT
├── tests/
│   ├── test_plugin_components.py                             # EDIT
│   ├── test_fetch_dashboard.py                               # NEW
│   ├── fixtures/raw-dashboard.json                           # NEW
│   └── smoke/dashboard_smoke.sh                              # NEW
├── README.md                                                 # EDIT
└── docs/superpowers/
    ├── specs/2026-09-10-argocd-grafana-dashboards-design.md  # this file
    └── plans/2026-09-10-argocd-grafana-dashboards.md
```

## End task for this spec

Via the plugin: `/argocd-add-dashboard airflow <grafana.com-id>` produces a
working, data-populated Airflow dashboard in an `airflow` folder in the live
Grafana (airflow is already scraped by spec #1's ServiceMonitor). trino, mysql,
and metabase need spec #2b's exporter workflow first; the Kubernetes cluster is
already covered by the kube-prometheus-stack default dashboards.

## Risks

- **Wrong dashboard for the exporter** — a dashboard querying metric names your
  exporter does not emit renders all "No data". Mitigation: step 5's metric-name
  sanity check against live Prometheus.
- **Datasource normalization misses a form** — a dashboard variant the script
  does not recognize. Mitigation: `test_fetch_dashboard.py` covers both known
  forms; the command's step 7 dry-run + step 10 functional check catch a broken
  result; unrecognized non-Prometheus datasources cause a non-zero exit rather
  than silent breakage.
- **1 MB ConfigMap limit** — a large dashboard. Mitigation: step 7 checks the
  rendered size; the skill documents split/trim.
- **grafana.com API shape change** — `fetch_dashboard.py` depends on the
  `revisions/<n>/download` endpoint. Mitigation: URL and local-path inputs are a
  fallback; the script fails loudly.
