# Sync-waves vs Argo CD hooks

<!-- owner: argocd-extra-manifests skill · last reviewed: 2026-09-10 -->

## Reach for sync-waves first

`argocd.argoproj.io/sync-wave: "N"` (a string; lower runs first, default `"0"`,
negatives allowed) orders resources **within one sync**. The resources stay
normal — visible in the tree, health-tracked, pruned normally. This covers almost
every ordering need:

- a CRD (or the operator app that owns it) before the custom resources that use it
- a namespace / Secret / ConfigMap before the workload that mounts it
- a database app before the app that connects to it

For an extra manifest that needs a CRD (ServiceMonitor → Prometheus-Operator),
the controller app just needs a lower wave than the app shipping the CR. Put the
wave on the **Application** (`environments/<env>/apps/<app>.yaml` metadata) or, if
the CR is inside a wrapper chart's `templates/`, it inherits the app's wave —
which is fine as long as the operator app is earlier.

## Use a hook only for a transient lifecycle task

A hook is a resource that runs *as part of* the sync and is not a persistent part
of desired state.

| `argocd.argoproj.io/hook` | Runs | Use for |
|---|---|---|
| `PreSync` | before the main sync | DB schema migration; backup-before-upgrade |
| `Sync` | with the main wave (own sub-wave) | a Job you must apply every sync but want recreated/cleaned (its K8s-mutated selector would otherwise drift `OutOfSync`) |
| `PostSync` | after all resources are Healthy | smoke test; cache warm; deploy notification |
| `SyncFail` | when the sync fails | cleanup / alert |

`argocd.argoproj.io/hook-delete-policy`: `BeforeHookCreation` (default — keeps the
last run so you can read its logs), `HookSucceeded` (delete on success),
`HookFailed`.

## Traps (all seen in this plugin's e2e)

1. **PostSync deadlock.** If the main workloads *wait on* what a PostSync hook
   produces (e.g. init containers that block until a migration Job runs, and the
   migration is a PostSync hook), the workloads never go Healthy → PostSync never
   fires → deadlock. **Rule: a PreSync/Sync hook may unblock the main resources;
   a PostSync hook must only depend on them, never the reverse.**
2. **Helm hooks are translated.** Argo CD maps `helm.sh/hook: pre-install,pre-upgrade`
   → `PreSync` and `post-install,post-upgrade` → `PostSync`. Other Helm hook
   phases (`test`, `pre-delete`, `post-delete`) are ignored or only partially
   honored — relevant only if the free-text path adds a Job carrying those. A
   chart's `post-install` migration Job becomes a PostSync hook and can hit
   trap 1. Fix: `<chart>.<job>.useHelmHooks: false` in values (makes it a plain
   resource) — if the chart exposes such a toggle (Bitnami and some others do);
   otherwise disable the Helm hook by patching the annotation off, or accept the
   PreSync/PostSync behavior and design around it. Then re-annotate it
   `argocd.argoproj.io/hook: Sync`, `hook-delete-policy: BeforeHookCreation`.
3. **`prune: false` + hooks.** On an app with pruning disabled (e.g. one that
   manages CRDs), leftover hook ServiceAccounts / RBAC show as "requiresPruning"
   noise — harmless but confusing.

## For this plugin's starters

`servicemonitor.yaml` / `podmonitor.yaml` are **plain resources** — no hook
annotation. They only need the Prometheus-Operator CRD to exist first, which is a
sync-wave concern handled by the `kube-prometheus-stack` app being deployed and
at an earlier wave. Hooks enter only if someone adds a *Job* manifest via the
free-text path.
