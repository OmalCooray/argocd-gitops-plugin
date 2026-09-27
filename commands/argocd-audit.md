---
name: argocd-audit
description: Read-only drift report — compare the Argo CD Applications declared in environments/<env>/apps/ against what a live cluster actually has, and against each app's sync/health status. Changes nothing.
argument-hint: "[environment-name] [--context <name>]"
---

Report drift between the GitOps repo and a live Argo CD instance.

**Follow the interaction contract:** `${CLAUDE_PLUGIN_ROOT}/references/interaction-style.md`
— announce each step, show commands + key output, one-shot (no polling), end with
a summary. This command is read-only, so no checkpoints are needed.

## Inputs

- `$1` — environment to audit (optional; default: audit every `environments/*/`).

## Preconditions

0. **Resolve the target:** follow `${CLAUDE_PLUGIN_ROOT}/references/target-resolution.md`; use its `CTX` and `ARGOCD_NS` in every command below. Accept an optional `--context <name>` argument.
- CWD is a GitOps repo.
- A reachable cluster/Argo CD. Prefer the `argocd` CLI if logged in; else
  `kubectl` against the Argo CD namespace. If neither works, run in **offline
  mode**: ask the user to paste `argocd app list -o json` (or
  `kubectl --context "$CTX" get applications -n "$ARGOCD_NS" -o json`) output.

## Steps

0. **Validate the environment.** If `$1` is given and `environments/$1/` does not exist, print
   `environment "$1" not found; available environments: <ls environments/>` and stop. (Never audit an empty declared set.)
1. Build the **declared set** per environment: every `environments/<env>/apps/*.yaml` (`metadata.name`,
   each `spec.sources[]`/`spec.source` `targetRevision` + `path`) **plus the root app** declared in
   `environments/<env>/root.yaml` (mark it `role=root`). The root app is *expected* to be live and is
   never "orphaned".
2. Build the **live set** from `kubectl --context "$CTX" -n "$ARGOCD_NS" get applications -o json`
   (accept both shapes: the `kubectl` List with `items[]`, and `argocd app list -o json`, a top-level array).
   In offline mode use the pasted JSON the same way (both shapes; the `Managed by` table then uses the pasted
   annotations). Per app: name, `spec.sources[]` (or `spec.source`), `status.sync.status`, `status.health.status`,
   **`status.sync.revisions[]`** (multi-source apps; `status.sync.revision` is null for them, so use it only
   for single-source apps), and the `argocd.argoproj.io/tracking-id` annotation prefix.
3. Compare revisions **per source**: `status.sync.revisions[i]` corresponds to `spec.sources[i]`. Resolve each
   source's `targetRevision` with the per-source comparison rules in `commands/argocd-sync.md` step 3
   (branch/HEAD via `git ls-remote`, tag peeled, 40-hex SHA direct, Helm-repo chart version). `git ls-remote` is
   not a cluster command, so it runs locally even in offline mode. On a mismatch report "behind HEAD". If
   `ls-remote` fails, report "unknown (could not reach the repo)" for that source and never flag drift on unknown.
   Also compare `spec.sources[].targetRevision`/`path` against the repo's manifest, source by source.
4. Report these tables (omit an empty one, but always print the summary):
   - **Missing in cluster**: declared but not live. If the root app is also missing, every declared app is
     Missing and the cause is "root app never applied — run `/argocd-bootstrap`"; otherwise
     "root app has not synced yet — refresh `root-<env>`".
   - **Orphaned in cluster**: live, not declared, and not the root app.
   - **Managed by**: for every live app, who manages it. The tracking-id prefix if it names a live app that is the
     env's root app (`root-<env>`); otherwise "kubectl apply (no root app)" when the app carries a
     `kubectl.kubernetes.io/last-applied-configuration` annotation. Any app not managed by the env's root app is
     **unmanaged by GitOps**: say so.
   - **Drift / unhealthy**: `OutOfSync`, `Degraded`, `Missing`, behind HEAD, or a source differs from the repo.
5. For each row give the one-line likely cause and the corrective action ("merge PR #NN", "refresh root-<env>",
   "delete `apps/<x>.yaml`", "run `/argocd-bootstrap`"). Never run `argocd app sync` for an app that is missing.
6. Print: `<n> declared (+root), <m> live, <a> missing, <b> orphaned, <c> drifted, <d> unhealthy, <u> unmanaged`,
   or `No drift: everything declared is live, in sync and healthy.` when all are zero.

## Notes

- **Read-only.** Never `sync`, `apply`, `delete`, or edit anything. Offer to
  generate the fix PR via `/argocd-deploy` but do not act.
- This replaces the hand-written `applications.txt` reconcile loop.
