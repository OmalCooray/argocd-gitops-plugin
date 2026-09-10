# Grafana Dashboards for an App — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `/argocd-add-dashboard <app> <source>` + the `argocd-grafana-dashboards` skill to `argocd-gitops-plugin` — import a community Grafana dashboard into `charts/<app>/grafana-dashboards/`, normalize its datasource references, and render it as a sidecar-labelled ConfigMap in a per-app Grafana folder.

**Architecture:** A new skill directory (`SKILL.md`, `scripts/fetch_dashboard.py`, `reference/`), a new command markdown, a wrapper-chart ConfigMap template pattern documented in the skill, small edits to two existing skills + the README. Tests: a pytest for the normalize script (fixture-driven, no network), a helm smoke script, the component inventory.

**Tech Stack:** Markdown (skill/command), Python 3 stdlib (`fetch_dashboard.py`), Helm-templated YAML (the ConfigMap pattern), Bash + Helm (smoke), pytest. No new runtime deps.

**Spec:** `docs/superpowers/specs/2026-09-10-argocd-grafana-dashboards-design.md`

**Repo:** `C:\claude\argocd-gitops-plugin`, branch `feat/grafana-dashboards-spec` (spec already committed here as `698ca0c`). Continue on this branch.

**Environment (verified):** `git`, `helm` v3.19, `kubectl` v1.32 (context `docker-desktop`, live cluster with kube-prometheus-stack + Grafana; Grafana port-forward on `localhost:18300`, admin / `jKsFo1H_rV5MrlGqwt-XzQ`; Prometheus port-forward on `localhost:19090`), `python` 3.12, `gh` authenticated. `airflow` is already scraped (`serviceMonitor/airflow/airflow/0` is `up`; `airflow_*` metrics in Prometheus). pytest: `python -m pytest`.

**Conventions for every task:**
- Branch `feat/grafana-dashboards-spec`. Commit after each task with the trailer:
  ```
  Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
  ```
- LF line endings. Paths relative to `C:\claude\argocd-gitops-plugin`.
- Command/skill files reference plugin files via `${CLAUDE_PLUGIN_ROOT}/...` only (a test forbids home/absolute paths in components).
- `export PATH="$HOME/scoop/shims:$PATH"` in Bash for `helm`/`gh`.

---

## File Structure

```
argocd-gitops-plugin/
├── commands/argocd-add-dashboard.md                          # CREATE
├── skills/argocd-grafana-dashboards/
│   ├── SKILL.md                                              # CREATE
│   ├── scripts/fetch_dashboard.py                            # CREATE
│   └── reference/datasource-normalization.md                 # CREATE
├── skills/argocd-repo-conventions/SKILL.md                   # EDIT — one line
├── skills/argocd-rollout/SKILL.md                            # EDIT — functional-check row
├── tests/
│   ├── test_plugin_components.py                             # EDIT — EXPECTED_*
│   ├── test_fetch_dashboard.py                               # CREATE
│   ├── fixtures/raw-dashboard.json                           # CREATE
│   └── smoke/dashboard_smoke.sh                              # CREATE
└── README.md                                                 # EDIT
```

---

## Task 1: Fixture + failing test for `fetch_dashboard.py`

**Files:**
- Create: `tests/fixtures/raw-dashboard.json`
- Create: `tests/test_fetch_dashboard.py`

- [ ] **Step 1: Write `tests/fixtures/raw-dashboard.json`**

A trimmed community-dashboard-shaped file exercising both datasource forms:

```json
{
  "__inputs": [
    {
      "name": "DS_PROMETHEUS",
      "label": "Prometheus",
      "description": "",
      "type": "datasource",
      "pluginId": "prometheus",
      "pluginName": "Prometheus"
    }
  ],
  "__requires": [
    { "type": "grafana", "id": "grafana", "name": "Grafana", "version": "9.0.0" },
    { "type": "datasource", "id": "prometheus", "name": "Prometheus", "version": "1.0.0" },
    { "type": "panel", "id": "timeseries", "name": "Time series", "version": "" }
  ],
  "id": 12345,
  "uid": "abc123def45",
  "title": "Test App Overview",
  "tags": ["test", "example"],
  "timezone": "browser",
  "schemaVersion": 30,
  "version": 7,
  "templating": {
    "list": [
      {
        "name": "instance",
        "type": "query",
        "datasource": "${DS_PROMETHEUS}",
        "query": "label_values(up, instance)",
        "refresh": 2
      }
    ]
  },
  "panels": [
    {
      "id": 1,
      "title": "Up (legacy string datasource)",
      "type": "stat",
      "datasource": "${DS_PROMETHEUS}",
      "targets": [
        { "expr": "up{instance=~\"$instance\"}", "datasource": "${DS_PROMETHEUS}" }
      ]
    },
    {
      "id": 2,
      "title": "Request rate (modern object datasource)",
      "type": "timeseries",
      "datasource": { "type": "prometheus", "uid": "abc123def45" },
      "targets": [
        {
          "expr": "rate(http_requests_total[5m])",
          "datasource": { "type": "prometheus", "uid": "abc123def45" }
        }
      ]
    },
    {
      "id": 3,
      "title": "Inherits datasource (null)",
      "type": "stat",
      "datasource": null,
      "targets": [{ "expr": "sum(up)" }]
    }
  ]
}
```

- [ ] **Step 2: Write `tests/test_fetch_dashboard.py`**

```python
"""fetch_dashboard.py: local-file input + datasource normalization. No network."""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/argocd-grafana-dashboards/scripts/fetch_dashboard.py"
FIXTURE = ROOT / "tests/fixtures/raw-dashboard.json"


def _run(arg):
    p = subprocess.run(
        [sys.executable, str(SCRIPT), str(arg)],
        capture_output=True, text=True,
    )
    return p


def test_script_exists():
    assert SCRIPT.exists()


def test_normalizes_local_fixture_to_valid_json():
    p = _run(FIXTURE)
    assert p.returncode == 0, p.stderr
    out = json.loads(p.stdout)  # raises if not valid JSON
    assert out["title"] == "Test App Overview"


def test_strips_import_metadata():
    out = json.loads(_run(FIXTURE).stdout)
    for k in ("__inputs", "__requires", "id", "uid"):
        assert k not in out, k


def test_adds_datasource_template_var():
    out = json.loads(_run(FIXTURE).stdout)
    names = [v.get("name") for v in out["templating"]["list"]]
    assert "datasource" in names
    dsv = next(v for v in out["templating"]["list"] if v["name"] == "datasource")
    assert dsv["type"] == "datasource" and dsv["query"] == "prometheus"


def test_no_ds_input_placeholders_remain():
    assert "${DS_" not in _run(FIXTURE).stdout


def test_legacy_string_datasource_rewritten():
    out = json.loads(_run(FIXTURE).stdout)
    panel = next(p for p in out["panels"] if p["id"] == 1)
    assert panel["datasource"] == "${datasource}"
    assert panel["targets"][0]["datasource"] == "${datasource}"


def test_modern_object_datasource_rewritten():
    out = json.loads(_run(FIXTURE).stdout)
    panel = next(p for p in out["panels"] if p["id"] == 2)
    assert panel["datasource"] == {"type": "prometheus", "uid": "${datasource}"}
    assert panel["targets"][0]["datasource"] == {"type": "prometheus", "uid": "${datasource}"}


def test_null_datasource_left_alone():
    out = json.loads(_run(FIXTURE).stdout)
    panel = next(p for p in out["panels"] if p["id"] == 3)
    assert panel["datasource"] is None


def test_provenance_recorded():
    out = json.loads(_run(FIXTURE).stdout)
    assert "__source" in out and "fetched" in out["__source"]


def test_non_prometheus_dashboard_fails():
    # a dashboard with no prometheus reference at all -> non-zero exit
    tmp = ROOT / "tests/.out/no-prom.json"
    tmp.parent.mkdir(exist_ok=True)
    tmp.write_text(json.dumps({"title": "x", "panels": [
        {"id": 1, "type": "stat", "datasource": {"type": "loki", "uid": "l1"}}
    ]}))
    p = _run(tmp)
    assert p.returncode != 0
    tmp.unlink()
```

- [ ] **Step 3: Run — expect failure (script doesn't exist)**

Run: `python -m pytest tests/test_fetch_dashboard.py -q`
Expected: FAIL / errors — `SCRIPT` path does not exist. (`test_script_exists` fails; the rest error on the missing file.)

- [ ] **Step 4: Commit the fixture + test**

```bash
git add tests/fixtures/raw-dashboard.json tests/test_fetch_dashboard.py
git commit -m "test: fixture + failing tests for fetch_dashboard.py

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 2: `fetch_dashboard.py`

**Files:**
- Create: `skills/argocd-grafana-dashboards/scripts/fetch_dashboard.py`

- [ ] **Step 1: Write the script exactly**

```python
#!/usr/bin/env python3
"""Fetch a Grafana dashboard and normalize its datasource references.

Usage: fetch_dashboard.py <source>

  <source> is one of:
    - a grafana.com dashboard id: "12345", or "12345:8" to pin revision 8
    - an https:// URL to a dashboard JSON
    - a local path to a dashboard .json

Prints the normalized dashboard JSON to stdout. Exits non-zero with a stderr
message on fetch failure, invalid JSON, or a dashboard with no Prometheus
datasource.

Normalization:
  - remove __inputs, __requires, top-level id, top-level uid
  - ensure a templating variable {name: datasource, type: datasource,
    query: prometheus}
  - rewrite every "datasource" field: "${DS_*}" / a prometheus input name /
    "prometheus" -> "${datasource}"; {"type":"prometheus","uid":...} ->
    {"type":"prometheus","uid":"${datasource}"}; null and non-prometheus
    datasources are left untouched
  - add "__source": "<origin>, fetched <YYYY-MM-DD>"
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from datetime import date

GCOM = "https://grafana.com/api/dashboards"
DS_VAR = "datasource"
_DS_INPUT_RE = re.compile(r"^\$\{DS_[A-Z0-9_]+\}$")


class DashboardError(Exception):
    pass


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "argocd-gitops-plugin"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (trusted host)
        return resp.read()


def load(source: str) -> tuple[dict, str]:
    """Return (dashboard, origin_label)."""
    if re.fullmatch(r"\d+(:\d+)?", source):
        gid, _, rev = source.partition(":")
        if not rev:
            meta = json.loads(_http_get(f"{GCOM}/{gid}"))
            rev = str(meta["revision"])
        raw = _http_get(f"{GCOM}/{gid}/revisions/{rev}/download")
        return json.loads(raw), f"grafana.com/dashboards/{gid} revision {rev}"
    if source.startswith(("http://", "https://")):
        return json.loads(_http_get(source)), source
    with open(source, encoding="utf-8") as fh:
        return json.load(fh), source


def _prom_input_names(dash: dict) -> set[str]:
    return {
        i["name"]
        for i in dash.get("__inputs", [])
        if i.get("type") == "datasource" and i.get("pluginId") == "prometheus"
    }


def _fix_ds(ds, prom_inputs: set[str]):
    if ds is None:
        return ds
    if isinstance(ds, str):
        if _DS_INPUT_RE.match(ds) or ds in prom_inputs or ds.lower() == "prometheus":
            return "${%s}" % DS_VAR
        return ds  # already a var ref, or a non-prometheus named datasource
    if isinstance(ds, dict):
        if ds.get("type") in ("prometheus", None):
            return {"type": "prometheus", "uid": "${%s}" % DS_VAR}
        return ds  # loki / mixed / other — leave it
    return ds


def normalize(dash: dict, origin: str) -> dict:
    if "prometheus" not in json.dumps(dash).lower():
        raise DashboardError("dashboard has no Prometheus datasource references")

    prom_inputs = _prom_input_names(dash)
    for key in ("__inputs", "__requires", "id", "uid"):
        dash.pop(key, None)

    tmpl = dash.setdefault("templating", {})
    tlist = tmpl.setdefault("list", [])
    if not any(isinstance(v, dict) and v.get("name") == DS_VAR for v in tlist):
        tlist.insert(0, {
            "name": DS_VAR,
            "type": "datasource",
            "query": "prometheus",
            "label": "Datasource",
            "current": {},
            "hide": 0,
            "refresh": 1,
        })

    def walk(node):
        if isinstance(node, dict):
            if "datasource" in node:
                node["datasource"] = _fix_ds(node["datasource"], prom_inputs)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(dash)
    dash["__source"] = f"{origin}, fetched {date.today().isoformat()}"
    return dash


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write(__doc__)
        return 2
    try:
        dash, origin = load(argv[1])
        dash = normalize(dash, origin)
    except (urllib.error.URLError, OSError, json.JSONDecodeError, KeyError) as exc:
        sys.stderr.write(f"error: could not load dashboard: {exc}\n")
        return 1
    except DashboardError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1
    json.dump(dash, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

- [ ] **Step 2: Run the tests — expect pass**

Run: `python -m pytest tests/test_fetch_dashboard.py -q`
Expected: PASS (10 passed). If `test_modern_object_datasource_rewritten` fails because `_fix_ds` also rewrote a `templating` query var's datasource in an unexpected way, re-check `walk` only touches `"datasource"` keys — it does; adjust nothing in the test.

- [ ] **Step 3: Sanity-run against the fixture by hand**

Run:
```bash
python skills/argocd-grafana-dashboards/scripts/fetch_dashboard.py tests/fixtures/raw-dashboard.json | python -m json.tool | head -30
```
Expected: valid JSON, `__source` present, no `${DS_` strings, a `datasource` templating var.

- [ ] **Step 4: Run full suite**

Run: `python -m pytest -q`
Expected: existing count + 10.

- [ ] **Step 5: Commit**

```bash
git add skills/argocd-grafana-dashboards/scripts/fetch_dashboard.py
git commit -m "feat: fetch_dashboard.py — grafana.com/url/file -> normalized JSON

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 3: `argocd-grafana-dashboards` skill — `SKILL.md`

**Files:**
- Create: `skills/argocd-grafana-dashboards/SKILL.md`

- [ ] **Step 1: Write `skills/argocd-grafana-dashboards/SKILL.md`**

```markdown
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
```

- [ ] **Step 2: Verify frontmatter**

Run: `python -c "import re,pathlib; t=pathlib.Path('skills/argocd-grafana-dashboards/SKILL.md').read_text(encoding='utf-8'); m=re.match(r'^---\n(.*?)\n---\n', t, re.DOTALL); assert m and 'name: argocd-grafana-dashboards' in m.group(1); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add skills/argocd-grafana-dashboards/SKILL.md
git commit -m "feat: add argocd-grafana-dashboards skill

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 4: `reference/datasource-normalization.md`

**Files:**
- Create: `skills/argocd-grafana-dashboards/reference/datasource-normalization.md`

- [ ] **Step 1: Write the file**

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add skills/argocd-grafana-dashboards/reference/datasource-normalization.md
git commit -m "docs: datasource-normalization reference

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 5: Command — `/argocd-add-dashboard`

**Files:**
- Create: `commands/argocd-add-dashboard.md`

- [ ] **Step 1: Write `commands/argocd-add-dashboard.md`**

```markdown
---
name: argocd-add-dashboard
description: Import a community Grafana dashboard for an app — fetch it (grafana.com id / URL / file), normalize its datasource references, commit it under charts/<app>/grafana-dashboards/, render it as a sidecar ConfigMap in a per-app Grafana folder, and open a PR. Opt-in; requires the app to already be scraped.
argument-hint: "<app> <source>   (source: grafana.com id | https URL | local .json)"
---

Import an open-source Grafana dashboard into `charts/<app>/`. Runs only when
invoked — nothing adds dashboards automatically.

**Follow the interaction contract:** `${CLAUDE_PLUGIN_ROOT}/references/interaction-style.md`
— announce each step, show commands + key output, checkpoint before `git push` /
the PR, end with a summary.

## Inputs

- `$1` — `<app>`; `charts/<app>/Chart.yaml` must exist.
- `$2` — `<source>`: a grafana.com dashboard id (`12345` or `12345:8`), an
  `https://` URL, or a local `.json` path.
- `--name <slug>` — dashboard file slug (default: from the dashboard title).
- `--env <env>` — optional; used for the metrics check and the sync suggestion.

## Preconditions

- CWD is a GitOps repo (`charts/`, `environments/`, `.claude/CLAUDE.md`).
- `python` and `helm` available.

## Steps

1. Load skills `argocd-grafana-dashboards` and `argocd-repo-conventions`.
2. **Metrics check.** Confirm the app is scraped:
   - a `ServiceMonitor` / `PodMonitor` exists in `charts/<app>/templates/`, **and**
   - if a cluster is reachable, Prometheus has series for it
     (`/api/v1/query?query={job=~".*<app>.*"}` or a metric you expect).
   No metrics → **STOP**: report the dashboard would be empty; point at
   `/argocd-add-manifest` (to add a ServiceMonitor) or the exporter workflow
   (`/argocd-observe`, separate) if the app emits nothing.
3. Branch `git switch -c add-dashboard/<app>-<slug>`.
4. Fetch + normalize:
   ```bash
   python ${CLAUDE_PLUGIN_ROOT}/skills/argocd-grafana-dashboards/scripts/fetch_dashboard.py "<source>" \
     > charts/<app>/grafana-dashboards/<slug>.json
   ```
   If the script exits non-zero (fetch failed, or not a Prometheus dashboard),
   report the stderr and stop.
5. **Sanity-check.** Grep the JSON for the metric names it queries; sample a few
   against `/api/v1/label/__name__/values`. If most are absent, warn that it is
   likely the wrong dashboard for this exporter and let the user confirm or pick
   another `<source>`.
6. If `charts/<app>/templates/grafana-dashboards.yaml` is absent, create it (the
   template in the `argocd-grafana-dashboards` skill). Add the `grafanaDashboards`
   stanza to `charts/<app>/values.yaml` (`enabled: true`, optional `folder`).
7. Verify:
   ```bash
   helm template <app> charts/<app>                           # ConfigMap renders, dashboard is a data key
   helm template <app> charts/<app> | kubectl apply --dry-run=server -f -   # if a cluster is reachable
   ```
   Check the rendered ConfigMap is < 1 MB.
8. Bump `charts/<app>/Chart.yaml` `version`.
9. Checkpoint → commit → push → `gh pr create` (title `Add Grafana dashboard to
   <app>`; body: the grafana.com source + revision, the folder, the metrics /
   exporter it needs).
10. Suggest `/argocd-sync <app> <env>`. Functional check: after sync, Grafana
    `/api/search?query=<title>` returns it with `folderTitle == <app>`, and its
    panels render data (open one — not "No data").

## Notes

- Opt-in. `/argocd-add-chart`, `/argocd-deploy`, `/argocd-add-manifest` never add
  dashboards.
- One ConfigMap per app; more dashboards = more files in `grafana-dashboards/`.
- Never edit the upstream chart or a subchart `_helpers`.
```

- [ ] **Step 2: Verify no hardcoded paths + frontmatter**

Run:
```bash
grep -nE '/(Users|home)/[a-z]|C:\\\\Users' commands/argocd-add-dashboard.md || echo "no hardcoded paths"
python -c "import re,pathlib; t=pathlib.Path('commands/argocd-add-dashboard.md').read_text(encoding='utf-8'); assert re.match(r'^---\n.*?\ndescription:.*?\n.*?\n---\n', t, re.DOTALL); print('frontmatter OK')"
```
Expected: `no hardcoded paths` then `frontmatter OK`.

- [ ] **Step 3: Commit**

```bash
git add commands/argocd-add-dashboard.md
git commit -m "feat: add /argocd-add-dashboard command

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 6: Smoke test — `tests/smoke/dashboard_smoke.sh`

**Files:**
- Create: `tests/smoke/dashboard_smoke.sh`

- [ ] **Step 1: Write the script**

```bash
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
```

- [ ] **Step 2: `chmod +x` and run**

Run:
```bash
chmod +x tests/smoke/dashboard_smoke.sh
bash tests/smoke/dashboard_smoke.sh
```
Expected: ends with `OK: grafana-dashboards ConfigMap renders with a normalized dashboard`.
Windows/Git-Bash note: pass the rendered file to Python as `sys.argv[1]` (done above) — Windows Python cannot open an MSYS `/c/...` path embedded in `-c`.

- [ ] **Step 3: Commit**

```bash
git add tests/smoke/dashboard_smoke.sh
git commit -m "test: helm smoke for the grafana-dashboards ConfigMap

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 7: Wire into `test_plugin_components.py`

**Files:**
- Modify: `tests/test_plugin_components.py`

- [ ] **Step 1: Edit the expected sets**

Add `"argocd-add-dashboard"` to `EXPECTED_COMMANDS` and `"argocd-grafana-dashboards"`
to `EXPECTED_SKILLS`.

- [ ] **Step 2: Run the suite**

Run: `python -m pytest -q`
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_plugin_components.py
git commit -m "test: expect argocd-add-dashboard + argocd-grafana-dashboards

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 8: Edits — `argocd-repo-conventions`, `argocd-rollout`, `README`

**Files:**
- Modify: `skills/argocd-repo-conventions/SKILL.md`
- Modify: `skills/argocd-rollout/SKILL.md`
- Modify: `README.md`

- [ ] **Step 1: `argocd-repo-conventions` — one line in "Custom manifests"**

At the end of the "## Custom manifests" section bullets, add:
```markdown
- Grafana dashboards for an app: `/argocd-add-dashboard` +
  the `argocd-grafana-dashboards` skill (a normalized community dashboard JSON
  under `charts/<app>/grafana-dashboards/`, rendered as a sidecar ConfigMap).
```

- [ ] **Step 2: `argocd-rollout` — functional-check row**

In the functional-check table, after the "Extra manifest" row, add:
```markdown
| Grafana dashboard | after sync it appears in Grafana's `<app>` folder (`GET /api/search?query=<title>`, `folderTitle == <app>`) and its panels render data — open one, not "No data" |
```

- [ ] **Step 3: `README.md`**

Command table, after the `/argocd-add-manifest` row:
```markdown
| `/argocd-add-dashboard <app> <source>` | Import a community Grafana dashboard (grafana.com id / URL / file) for a scraped app — normalized + rendered as a sidecar ConfigMap in a per-app folder. Opt-in. |
```

Roadmap — update the "Next" note:
```markdown
Next: `argocd-exporters` / `/argocd-observe` (spec #2b) — provision an exporter
for apps that emit no metrics (Metabase, bare MySQL) and tie exporter →
ServiceMonitor → dashboard into one command.
```

- [ ] **Step 4: Verify**

Run:
```bash
python -m pytest -q
grep -L 'interaction-style' commands/*.md
```
Expected: all tests pass; `grep -L` prints nothing.

- [ ] **Step 5: Commit**

```bash
git add skills/argocd-repo-conventions/SKILL.md skills/argocd-rollout/SKILL.md README.md
git commit -m "docs: wire /argocd-add-dashboard into conventions, rollout, README

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 9: End-to-end — a real Airflow dashboard in Grafana

Hand-follow `commands/argocd-add-dashboard.md` for `airflow` against the live
cluster and repo. `airflow` is already scraped (spec #1's ServiceMonitor).

**Files:**
- Modify: any skill / script / template / command file the run reveals to be wrong.

- [ ] **Step 1: Pick a dashboard**

The airflow chart's `statsd` sidecar is `prom/statsd-exporter`; its metrics are
`airflow_*`. On grafana.com search "airflow". Candidates: **id 12921**
("Apache Airflow" — statsd-exporter based) or a newer one. Fetch and inspect:
```bash
cd /c/claude/test-k8s-configs && git checkout master && git pull
python /c/claude/argocd-gitops-plugin/skills/argocd-grafana-dashboards/scripts/fetch_dashboard.py 12921 \
  | python -c "import sys,json; d=json.load(sys.stdin); print(d['title']); import re; exprs=re.findall(r'\"expr\"\s*:\s*\"([^\"]+)\"', json.dumps(d)); print('\n'.join(sorted({m.split('{')[0].split('(')[-1] for e in exprs for m in [e]})[:20]))"
```
Compare the metric names to live Prometheus:
```bash
curl -s 'http://localhost:19090/api/v1/label/__name__/values' | python -c "import sys,json; n=set(json.load(sys.stdin)['data']); print(sorted(x for x in n if x.startswith('airflow_'))[:25])"
```
If dashboard 12921's queries don't match `airflow_*` (e.g. it expects
`af_agg_*` from a different exporter), try another id or a newer Airflow
dashboard. **Record the id you settle on.**

- [ ] **Step 2: Follow the command steps**

Branch `add-dashboard/airflow-overview` in `test-k8s-configs`. Metrics check:
`charts/airflow/templates/servicemonitor.yaml` exists ✓; Prometheus has
`airflow_*` ✓. Fetch:
```bash
mkdir -p charts/airflow/grafana-dashboards
python /c/claude/argocd-gitops-plugin/skills/argocd-grafana-dashboards/scripts/fetch_dashboard.py <id> \
  > charts/airflow/grafana-dashboards/airflow-overview.json
```
Create `charts/airflow/templates/grafana-dashboards.yaml` (the skill's template).
Add to `charts/airflow/values.yaml`:
```yaml
grafanaDashboards:
  enabled: true
```
Bump `charts/airflow/Chart.yaml` `version` (→ `0.1.2`).

- [ ] **Step 3: Verify render + size**

```bash
helm dependency build charts/airflow >/dev/null
helm template airflow charts/airflow -f environments/local/values/airflow.yaml --show-only templates/grafana-dashboards.yaml > /tmp/d.yaml
wc -c /tmp/d.yaml            # well under 1 MB
helm template airflow charts/airflow -f environments/local/values/airflow.yaml --show-only templates/grafana-dashboards.yaml | kubectl apply --dry-run=server -f -
```
Expected: `configmap/airflow-dashboards created (server dry run)`.

- [ ] **Step 4: Commit, PR, merge, sync**

```bash
git add charts/airflow
git -c core.autocrlf=false commit -m "Add Grafana dashboard to airflow

Grafana.com dashboard <id> (Airflow / statsd-exporter), normalized, rendered as
airflow-dashboards ConfigMap in the 'airflow' folder.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
git push -u origin add-dashboard/airflow-overview
gh pr create --base master --head add-dashboard/airflow-overview --title "Add Grafana dashboard to airflow" --body "grafana.com dashboard <id>, normalized (datasource -> \${datasource} var), rendered as the airflow-dashboards ConfigMap (grafana_folder: airflow). airflow is scraped by its ServiceMonitor; helm render + server dry-run pass."
gh pr merge add-dashboard/airflow-overview --merge --delete-branch
git checkout master && git pull
kubectl -n argocd annotate app airflow argocd.argoproj.io/refresh=hard --overwrite
```

- [ ] **Step 5: Functional check in Grafana**

Wait for the app `Synced`, then (the sidecar picks up the ConfigMap in ~30-60s):
```bash
U="admin:jKsFo1H_rV5MrlGqwt-XzQ"
curl -s -u "$U" "http://localhost:18300/api/search?query=$(python -c 'import urllib.parse;print(urllib.parse.quote("<dashboard title>"))')" \
  | python -c "import sys,json; [print(d['title'],'| folder:',d.get('folderTitle')) for d in json.load(sys.stdin)]"
```
Expected: the dashboard listed with `folder: airflow`.

Then confirm a panel has data — pick one panel's `expr` from the JSON and query
it:
```bash
curl -s "http://localhost:19090/api/v1/query?query=<a metric the dashboard uses>" \
  | python -c "import sys,json; r=json.load(sys.stdin)['data']['result']; print(len(r),'series')"
```
Expected: ≥ 1 series. If the dashboard loaded but panels are "No data", the
dashboard's queries don't match the exporter's metric names / labels — go back to
Step 1 and pick a better dashboard, or add `metricRelabelings` in the
ServiceMonitor (spec #1) to bridge label names. Fix and re-run.

- [ ] **Step 6: Record findings, fix the plugin**

For every deviation (script mis-normalized a field, template rendered wrong, the
skill's metric-check guidance was too vague, the command missed a step), fix the
plugin file in `C:\claude\argocd-gitops-plugin`. Re-run
`python -m pytest -q` and `bash tests/smoke/dashboard_smoke.sh`.

- [ ] **Step 7: Clean up + commit fixes**

```bash
cd /c/claude/argocd-gitops-plugin
rm -rf tests/.out
git add -A
git commit -m "fix: corrections from the airflow dashboard e2e

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>" || echo "e2e clean"
```

---

## Task 10: Validate and finalise

- [ ] **Step 1: plugin-validator agent**

Dispatch `plugin-dev:plugin-validator` against `C:\claude\argocd-gitops-plugin`.
Expected: `argocd-add-dashboard` command + `argocd-grafana-dashboards` skill
valid and discoverable; `scripts/fetch_dashboard.py` is plugin data, not a
component (not flagged); no path issues. Fix anything flagged.

- [ ] **Step 2: skill-reviewer agent**

Dispatch `plugin-dev:skill-reviewer` for `skills/argocd-grafana-dashboards`.
Apply reasonable suggestions (do not weaken the metrics-check precondition or the
"stop if no metrics" guardrail).

- [ ] **Step 3: Full green**

```bash
python -m pytest
bash tests/smoke/dashboard_smoke.sh
bash tests/smoke/extra_manifest_smoke.sh
bash tests/smoke/helm_smoke.sh
```
Expected: all pass.

- [ ] **Step 4: PR + merge**

```bash
git push -u origin feat/grafana-dashboards-spec
gh pr create --base master --head feat/grafana-dashboards-spec \
  --title "Grafana dashboards for an app: /argocd-add-dashboard + argocd-grafana-dashboards" \
  --body "Spec #2a. Opt-in /argocd-add-dashboard imports a community dashboard (grafana.com id / URL / file), normalizes its datasource refs to a \`\${datasource}\` template var (fetch_dashboard.py, stdlib), commits it under charts/<app>/grafana-dashboards/, and renders it as a sidecar-labelled ConfigMap in a per-app Grafana folder. Requires the app to already be scraped — reports and stops otherwise. New argocd-grafana-dashboards skill + datasource-normalization reference. Tests: test_fetch_dashboard.py (10, fixture-driven, no network) + dashboard_smoke.sh. Verified end-to-end: a real Airflow dashboard live in Grafana's 'airflow' folder with data.

Next: spec #2b (argocd-exporters / /argocd-observe) for apps that emit no metrics.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
gh pr merge feat/grafana-dashboards-spec --merge --delete-branch
git checkout master && git pull && git remote prune origin
```

- [ ] **Step 5: Report**

Files added/edited, `pytest` + smoke output, the Airflow dashboard result
(loaded in the `airflow` folder + a panel with data, or the diagnosed reason),
and that spec #2b is next for trino/mysql/metabase.

---

## Self-Review

**1. Spec coverage**

| Spec item | Task |
|---|---|
| `charts/<app>/grafana-dashboards/*.json` convention | 3 (skill), 9 (e2e) |
| `templates/grafana-dashboards.yaml` ConfigMap pattern | 3 (skill documents it), 6 (smoke asserts it), 9 |
| `grafana_dashboard: "1"` label + `grafana_folder` annotation | 3, 6 |
| per-app folder (default chart name) | 3, 6 |
| nil-safe `grafanaDashboards.enabled` gate | 3, 6 |
| datasource normalization (both forms, template var) | 1, 2, 4 |
| `fetch_dashboard.py` — id / URL / file; non-prom → non-zero | 2 (+ tests in 1) |
| `/argocd-add-dashboard` command | 5 |
| opt-in only | 5 (stated), 8 (README/conventions framing) |
| metrics-check precondition (stop if not scraped) | 3, 5 |
| verify: render + `--dry-run=server` + < 1 MB | 5, 6, 9 |
| bump chart version | 3, 5, 9 |
| `argocd-repo-conventions` pointer | 8 |
| `argocd-rollout` functional-check row | 8 |
| README command table + roadmap | 8 |
| `test_plugin_components.py` EXPECTED_* | 7 |
| `test_fetch_dashboard.py` | 1 |
| `dashboard_smoke.sh` | 6 |
| end task: real Airflow dashboard, live, with data | 9 |
| validation | 10 |

No gaps.

**2. Placeholder scan** — no "TBD"/"handle appropriately". The one deliberate
`<id>` placeholder is Task 9 Step 1, which spells out how to choose it (fetch,
compare metric names, record) — that is the e2e discovering the right value, not
a plan gap.

**3. Type / name consistency**

- Command `argocd-add-dashboard`, skill `argocd-grafana-dashboards`, script
  `fetch_dashboard.py` — identical in Tasks 1-10 and `test_plugin_components.py`.
- The ConfigMap template appears in Task 3 (skill) and Task 6 (smoke) —
  **must be byte-identical**; the implementer copies from the skill into the
  smoke fixture. `metadata.name: {{ .Chart.Name }}-dashboards`, label
  `grafana_dashboard: "1"`, annotation key `grafana_folder`, glob
  `grafana-dashboards/*.json`, `{{ base $path }}` key.
- Values key `grafanaDashboards.enabled` / `.folder` — Tasks 3, 5, 6, 9.
- `fetch_dashboard.py` output contract (`__source`, no `${DS_`, `datasource`
  templating var, object form `{"type":"prometheus","uid":"${datasource}"}`) —
  Task 2 script ↔ Task 1 test assertions ↔ Task 4 reference table. Checked: the
  test's `test_modern_object_datasource_rewritten` expects exactly
  `{"type": "prometheus", "uid": "${datasource}"}` which `_fix_ds` produces.
- `${datasource}` (the Grafana template-var syntax) vs `${DS_PROMETHEUS}` (the
  import-input syntax) — used consistently; the transform goes from the latter to
  the former.

Fixed during review: Task 9 Step 5's `curl .../api/search?query=` needs URL
encoding of the title — added a `urllib.parse.quote` inline.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-10-argocd-grafana-dashboards.md`.
