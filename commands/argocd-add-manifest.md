---
name: argocd-add-manifest
description: Add your own templated manifest (ServiceMonitor, PodMonitor, or any kind via free text) to a wrapper chart's templates/ directory, gated on a values flag, verified to render and to be accepted by its CRD, then open a PR. Opt-in only — nothing else adds templates.
argument-hint: "<app> <kind>   (kind: servicemonitor | podmonitor | free text) [--context <name>]"
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

0. **Resolve the target:** follow `${CLAUDE_PLUGIN_ROOT}/references/target-resolution.md`; use its `CTX` and `ARGOCD_NS` in every command below. Accept an optional `--context <name>` argument.
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
   - If the render shows the names are already `<app>-<component>`, use them
     as-is and do not add a no-op `fullnameOverride`; if not and the chart honors
     `fullnameOverride`, add `<chart>.fullnameOverride: <app>` to
     `charts/<app>/values.yaml` (tell the user — may rename on next sync).
   - For `servicemonitor` / `podmonitor`: if no Service/pod exposes a **named**
     metrics port and the app serves no `/metrics`, STOP — report that the app
     exposes no scrapeable metrics (needs an exporter or the chart's metrics
     option first; that's the `argocd-observability` workflow, not this command).
4. Scaffold:
   - starter kind: copy
     `${CLAUDE_PLUGIN_ROOT}/skills/argocd-extra-manifests/reference/starters/<kind>.yaml`
     → `charts/<app>/templates/<kind>.yaml` verbatim.
   - free-text kind: first apply the **privileged-kind guardrail** below, then
     author `charts/<app>/templates/<slug>.yaml` from the `argocd-extra-manifests` checklist (gated, no subchart `_helpers`).
     A kind is *privileged* if it is: a ClusterRole or ClusterRoleBinding (always); a namespaced Role/RoleBinding that has `*` in verbs, resources or apiGroups, grants any of `secrets`, `pods/exec`, `pods/attach`, `serviceaccounts/token`, or the verbs `escalate`, `bind`, `impersonate`, or binds a ClusterRole other than the built-in read-only `view`; any rule with `*` verbs or resources; any binding of `cluster-admin`, `system:authenticated`, `system:unauthenticated`, `system:anonymous` or `system:masters`; a Validating/MutatingWebhookConfiguration; a CRD; or a workload running `privileged: true` / `hostPath` / `hostNetwork`. A benign namespaced Role (e.g. read ConfigMaps in its own namespace) is not privileged: it needs no extra checkpoint but still follows the normal gate/values pattern. For a privileged kind:
     - print one line saying exactly what it grants and to whom;
     - default its values gate to `enabled: false`;
     - refuse outright, with no override, even if the user insists or says it is intentional, any binding of `cluster-admin` or `*` on `*` to `system:authenticated`, `system:unauthenticated`, `system:anonymous` or `system:masters` (do not author it);
     - judge the effective grant, not names: a binding is refused if the role it references, whether defined in this manifest or an existing ClusterRole, resolves to `cluster-admin` or to `*` on `*` (any `apiGroups`/`resources`/`verbs` all `*`). Subject spelling is irrelevant: kind `Group`, `User` or `ServiceAccount`, with or without the `system:` prefix, including `system:serviceaccounts` and `system:serviceaccounts:<ns>`;
     - checkpoint `> This grants <X> to <Y>. Proceed?` before committing.
5. Add the gating values stanza to `charts/<app>/values.yaml` as a **top-level**
   key (not nested under the subchart) — for a ServiceMonitor:
   `serviceMonitor: {enabled: <bool>, selectorLabels: {...}, port: <name>, path: /metrics, interval: 30s}`
   with `selectorLabels` / `port` filled from step 3. `enabled` is finalized in step 6: it ships `true` only if
   the CRD check found a provider already in this env, otherwise `false`. A privileged kind always ships `false`.
6. CRD check: if the kind needs a CRD (ServiceMonitor → `servicemonitors.monitoring.coreos.com`, PodMonitor →
   `podmonitors.monitoring.coreos.com`), it is *provided* if EITHER some app in `environments/<env>/apps/` ships it
   OR the reachable cluster has it (`kubectl --context "$CTX" get crd <name>`). Accept any provider — do not require a
   specific app name.
   - **Declared provider:** for each other app, render in a temp copy, never on the user's tree (`helm dependency build`
     rewrites `Chart.lock`): `T=$(mktemp -d); cp -r charts/<other> "$T/"`, then `helm dependency build "$T/<other>"`, then
     `helm template <other> "$T/<other>" -n <its-dest-ns> -f environments/<env>/values/<other>.yaml --include-crds`
     (add `-f` only if that values file exists), and grep the output for `kind: CustomResourceDefinition` together with
     `name: <crd>`. `--include-crds` is required: `helm template` skips a chart's `crds/` directory without it. The env
     values must be included because an overlay setting `crds.enabled: false` legitimately removes the CRD.
   - **Sync-wave:** read each app's wave from `metadata.annotations["argocd.argoproj.io/sync-wave"]` in
     `environments/<env>/apps/<app>.yaml`; a missing annotation means wave 0. The provider's wave must be strictly lower
     than `<app>`'s; if not, tell the user to set the provider app to `"-1"` (do not edit it in this command). A provider
     found only on the live cluster (not declared in this env) needs no ordering, but say the CRD may disappear if that
     provider is removed.
   - If a provider exists, set `enabled: true` in step 5.
   - If none: do not stop silently. Set `enabled: false`, report it, and offer the light path:
     `/argocd-add-chart prometheus-operator-crds` (repo `https://prometheus-community.github.io/helm-charts`) then
     `/argocd-deploy prometheus-operator-crds <env>` with `argocd.argoproj.io/sync-wave: "-1"` (CRDs only, ~10 objects),
     or `kube-prometheus-stack` for the full stack. Then tell the user how to turn it on later: set
     `serviceMonitor.enabled: true` (PodMonitor: `podMonitor.enabled`) in `environments/<env>/values/<app>.yaml` (or the
     chart values for all envs) **after** the provider app has synced, and re-run this command to have it verify.
7. Verify:
   ```bash
   helm template <app> charts/<app>            # your manifest renders
   helm template <app> charts/<app> | kubectl --context "$CTX" apply --dry-run=server -f -   # CRD accepts it (if a cluster is reachable)
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
