---
name: argocd-add-manifest
description: Add your own templated manifest (ServiceMonitor, PodMonitor, or any kind via free text) to a wrapper chart's templates/ directory, gated on a values flag, verified to render and to be accepted by its CRD, then open a PR. Opt-in only — nothing else adds templates.
argument-hint: "<app> <kind>   (kind: servicemonitor | podmonitor | free text)"
---

Add a custom manifest to `charts/<app>/templates/` alongside the pinned upstream
chart. Nothing about this is automatic — it runs only when invoked.

**Follow the interaction contract:** `${CLAUDE_PLUGIN_ROOT}/references/interaction-style.md`
— announce each step, show commands + key output, checkpoint before `git push` /
the PR, end with a summary.

## Inputs

- `$1` — `<app>`; `charts/<app>/Chart.yaml` must exist.
- `$2..` — `<kind>`: `servicemonitor`, `podmonitor`, or free text for any other
  resource ("a Traefik IngressRoute for the web port").
- `--env <env>` — optional; used to check the CRD's controller app is deployed
  there and to suggest the follow-up sync.

## Preconditions

- CWD is a GitOps repo (`charts/`, `environments/`, `.claude/CLAUDE.md`).
- `helm` available.

## Steps

1. Load skills `argocd-extra-manifests` and `argocd-repo-conventions`. Follow the
   authoring checklist.
2. Branch: `git switch -c add-manifest/<app>-<kind-slug>`.
3. `helm dependency build charts/<app>` then
   `helm template <app> charts/<app>` once (release name `<app>` — Argo CD uses
   the Application name as the release name; the default `release-name` gives
   wrong names). Read the real Service names, the **named** ports, and the
   Service/pod labels the new manifest must target.
   - If the names are not `<app>-<component>`: if the chart supports
     `fullnameOverride`, add `<chart>.fullnameOverride: <app>` to
     `charts/<app>/values.yaml` (tell the user — may rename on next sync). If the
     chart ignores it (Airflow, kube-prometheus-stack, …), use the names as
     rendered — do not add a no-op `fullnameOverride`.
   - For `servicemonitor` / `podmonitor`: if no Service/pod exposes a **named**
     metrics port and the app serves no `/metrics`, STOP — report that the app
     exposes no scrapeable metrics (needs an exporter or the chart's metrics
     option first; that's the `argocd-observability` workflow, not this command).
4. Scaffold:
   - starter kind: copy
     `${CLAUDE_PLUGIN_ROOT}/skills/argocd-extra-manifests/reference/starters/<kind>.yaml`
     → `charts/<app>/templates/<kind>.yaml` verbatim.
   - free-text kind: author `charts/<app>/templates/<slug>.yaml` from the
     `argocd-extra-manifests` checklist (gated, no subchart `_helpers`).
5. Add the gating values stanza to `charts/<app>/values.yaml` as a **top-level**
   key (not nested under the subchart) — for a ServiceMonitor:
   `serviceMonitor: {enabled: true, selectorLabels: {...}, port: <name>, path: /metrics, interval: 30s}`
   with `selectorLabels` / `port` filled from step 3.
6. CRD check: if the kind needs a CRD (ServiceMonitor/PodMonitor → Prometheus
   Operator), verify the owning app (`kube-prometheus-stack`) is in
   `environments/<env>/apps/` and its sync-wave is lower than `<app>`'s. If not,
   report it and stop before committing.
7. Verify:
   ```bash
   helm template <app> charts/<app>            # your manifest renders
   helm template <app> charts/<app> | kubectl apply --dry-run=server -f -   # CRD accepts it (if a cluster is reachable)
   ```
8. Bump `charts/<app>/Chart.yaml` `version`.
9. Checkpoint → commit → push → `gh pr create` (title `Add <kind> to <app>`,
   body: what it selects/scrapes, the values stanza, `helm template … | head`).
10. Suggest `/argocd-sync <app> <env>` to roll it out. For a ServiceMonitor /
    PodMonitor, name the functional check: after sync, the target shows in
    Prometheus `/api/v1/targets` and `up{...}` returns 1.

## Notes

- Opt-in only. `/argocd-add-chart` and `/argocd-deploy` never call this.
- One file per kind. Re-running for the same kind edits the existing file.
- Never `include` a subchart `_helpers` template.
