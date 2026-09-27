---
name: argocd-add-dashboard
description: Import a community Grafana dashboard for an app — fetch it (grafana.com id / URL / file), normalize its datasource references, commit it under charts/<app>/grafana-dashboards/, render it as a sidecar ConfigMap in a per-app Grafana folder, and open a PR. Opt-in; requires the app to already be scraped.
argument-hint: "<app> <source>   (source: grafana.com id | https URL | local .json) [--context <name>]"
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

0. **Resolve the target:** follow `${CLAUDE_PLUGIN_ROOT}/references/target-resolution.md`; use its `CTX` and `ARGOCD_NS` in every command below. Accept an optional `--context <name>` argument.
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
   (`/argocd-observe`, separate — planned) if the app emits nothing.
3. Branch `git switch -c add-dashboard/<app>-<slug>`.
4. Fetch + normalize:
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/skills/argocd-grafana-dashboards/scripts/fetch_dashboard.py" "<source>" \
     --out charts/<app>/grafana-dashboards/<slug>.json
   ```
   (Create `charts/<app>/grafana-dashboards/` first if needed. The script writes
   atomically: a failed fetch leaves **no** file.) If the script exits non-zero
   (fetch failed, or not a Prometheus dashboard), report the stderr and stop.
5. **Sanity-check metrics and labels.**
   a. Metric names: grep the JSON for the metrics it queries; sample a few against
      `/api/v1/label/__name__/values`. If most are absent, warn it is likely the wrong dashboard.
   b. Labels: `python "${CLAUDE_PLUGIN_ROOT}/skills/argocd-grafana-dashboards/scripts/fetch_dashboard.py" "<source>" --labels`
      prints the label names the dashboard uses (matchers, `by`/`on`/... lists,
      `label_values(..., <label>)`, legend `{{ label }}` templates).
      - **No reachable cluster** (`kubectl --context "$CTX" get ns` fails): print
        `label check skipped (no cluster)` and continue with step 6.
      - Otherwise reach Prometheus through its own service. Find it with
        `kubectl --context "$CTX" -n <monitoring-ns> get svc -l app=kube-prometheus-stack-prometheus`
        (or `kubectl --context "$CTX" -n <monitoring-ns> get svc | grep prometheus`),
        then run a short-lived foreground
        `kubectl --context "$CTX" -n <monitoring-ns> port-forward svc/<prometheus-svc> 9090:9090`
        and, from a second shell, one-shot `curl -s localhost:9090/api/v1/labels`
        (confirm on one series with `curl -s 'localhost:9090/api/v1/series?match[]=up{job=~".*<app>.*"}'`).
        Stop the port-forward afterwards.
      - For every dashboard label that Prometheus does not have, warn and offer to rewrite. Common scrape-label renames:
        `kubernetes_namespace->namespace`, `kubernetes_pod_name->pod`, `kubernetes_name->service`, `kubernetes_node->node`.
      - For each accepted rename, re-run step 4 with one `--relabel OLD=NEW` per rename, e.g.
        ```bash
        python "${CLAUDE_PLUGIN_ROOT}/skills/argocd-grafana-dashboards/scripts/fetch_dashboard.py" "<source>" \
          --relabel kubernetes_namespace=namespace --relabel kubernetes_pod_name=pod \
          --out charts/<app>/grafana-dashboards/<slug>.json
        ```
        Re-running into the same `--out` path safely replaces the file (atomic write).
6. If `charts/<app>/templates/grafana-dashboards.yaml` is absent, create it (the
   template in the `argocd-grafana-dashboards` skill). Add the `grafanaDashboards`
   stanza to `charts/<app>/values.yaml` (`enabled: true`, optional `folder`).
7. Verify:
   ```bash
   helm template <app> charts/<app>                           # ConfigMap renders, dashboard is a data key
   helm template <app> charts/<app> | kubectl --context "$CTX" apply --dry-run=server -f -   # if a cluster is reachable
   ```
   Check the rendered ConfigMap is < 1 MB.
8. Bump `charts/<app>/Chart.yaml` `version`.
9. Checkpoint → commit → push → `gh pr create` (title `Add Grafana dashboard to
   <app>`; body: the grafana.com source + revision, the folder, the metrics /
   exporter it needs).
   Follow `${CLAUDE_PLUGIN_ROOT}/references/no-remote-fallback.md` for the no-remote / no-`gh` cases.
10. Suggest `/argocd-sync <app> <env>`. Functional check: after sync, Grafana
    `/api/search?type=dash-db&query=<title>` returns it with
    `folderTitle == <app>`, and its panels render data (open one — not "No data").
    - Dashboard loads but `folderTitle` is null / it's in the root: the
      kube-prometheus-stack Grafana sidecar needs
      `grafana.sidecar.dashboards.provider.foldersFromFilesStructure: true` +
      `folderAnnotation: grafana_folder` — a one-time change to
      `charts/kube-prometheus-stack/` (see `argocd-grafana-dashboards` →
      `reference/datasource-normalization.md`). Grafana pod restart needed after.
    - The sidecar also has to watch the app's namespace. See the
      kube-prometheus-stack section of
      `${CLAUDE_PLUGIN_ROOT}/skills/values-review/reference/chart-notes.md` when
      present; otherwise set these Grafana sidecar values in
      `charts/kube-prometheus-stack/values.yaml` (under `grafana:`):
      `sidecar.dashboards.searchNamespace: ALL`,
      `sidecar.dashboards.folderAnnotation: grafana_folder`,
      `sidecar.dashboards.provider.foldersFromFilesStructure: true`.

## Notes

- Opt-in. `/argocd-add-chart`, `/argocd-deploy`, `/argocd-add-manifest` never add
  dashboards.
- One ConfigMap per app; more dashboards = more files in `grafana-dashboards/`.
- Never edit the upstream chart or a subchart `_helpers`.
