---
name: argocd-audit
description: Read-only drift report — compare what a GitOps repo declares (environments/<env>/apps/*.yaml plus the root app in environments/<env>/root.yaml) against what a live cluster actually has, and against each app's sync/health status. Changes nothing.
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
- Validate `$1` (Step 0) first — before resolving the target; it needs no cluster.
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
   never "orphaned". Also read the names declared in every other `environments/*/apps/*.yaml` and every
   other env's root app: they are needed to classify apps that belong elsewhere (step 2).
2. Build the **live set** from `kubectl --context "$CTX" -n "$ARGOCD_NS" get applications -o json`
   (accept both shapes: the `kubectl` List with `items[]`, and `argocd app list -o json`, a top-level array).
   In offline mode use the pasted JSON the same way (both shapes; the `Managed by` table then uses the pasted
   annotations). Per app: name, `spec.sources[]` (or `spec.source`), `status.sync.status`, `status.health.status`,
   **`status.sync.revisions[]`** (multi-source apps; `status.sync.revision` is null for them, so use it only
   for single-source apps), and the tracking-id annotation `argocd.argoproj.io/tracking-id` prefix (with
   `trackingMethod=label` the same information is in the `app.kubernetes.io/instance` label; read whichever is present).
   Classify each live app: audited env's declared app or root, **belongs to <env>** (declared in another env's
   `apps/*.yaml`, or another env's root app), or neither (candidate orphan). Apps that belong to another env are
   listed on one informational line (`belongs to <env>: <names>`), are NOT counted as orphaned or drifted here,
   and are excluded from `<m> live`; print how many were excluded.
3. Compare revisions **per source**: `status.sync.revisions[i]` corresponds to `spec.sources[i]`. Resolve each
   source's `targetRevision` with the per-source comparison rules in `${CLAUDE_PLUGIN_ROOT}/commands/argocd-sync.md` step 3
   (branch/HEAD via `git ls-remote`, tag peeled, 40-hex SHA direct, Helm-repo chart version). `git ls-remote` is
   not a cluster command, so it runs locally even in offline mode. On a mismatch report "behind HEAD" for a git
   source and "chart version differs" for a Helm-repo source. If `ls-remote` fails, report
   "unknown (could not reach the repo)" for that source and never flag drift on unknown.
   Also compare `spec.sources[].targetRevision`/`path` against the repo's manifest, source by source.
4. Report these tables (omit an empty one, but always print the summary):
   - **Missing in cluster**: declared apps (not the root) that are not live. Print a separate line
     `root app: LIVE|MISSING`. If the root app is MISSING, every declared app is Missing and the cause is
     "root app never applied — run `/argocd-bootstrap`"; otherwise "root app has not synced yet — refresh `root-<env>`".
     A missing root is reported on the `root app:` line and is NOT included in `<a>`.
   - **Orphaned in cluster**: live, not declared in **any** `environments/*/apps/*.yaml`, and not any env's root app.
   - **Managed by**: for every live app of this env, who manages it:
     (a) tracking-id prefix equals this env's root app name: `managed by root-<env>`;
     (b) prefix names another live app or another env's root: `managed by <x>, not this env's root`, counted as unmanaged;
     (c) tracking-id absent, empty or unparseable: `manually applied / unknown` (add "(kubectl apply)" when the
     `kubectl.kubernetes.io/last-applied-configuration` annotation exists), counted as unmanaged.
     The root app itself (`role=root`) is exempt from the Managed-by test and from the unmanaged count; list it as
     `root (bootstrap)`. Every counted app is **unmanaged by GitOps**: say so.
   - **Drift / unhealthy**: `<c> drifted` = sync status is not `Synced`, OR behind HEAD / chart version differs,
     OR a source differs from the repo. `<d> unhealthy` = health is not `Healthy`. An app can count in both.
5. For each row give the one-line likely cause and the corrective action ("merge PR #NN", "refresh root-<env>",
   "run `/argocd-bootstrap`"). For an orphan: either declare it (`/argocd-deploy`) or delete the live Application
   deliberately — that removes its workloads via the finalizer; audit never does either.
   Never run `argocd app sync` for an app that is missing.
6. Print: `<n> declared (+root), <m> live, <a> missing, <b> orphaned, <c> drifted, <d> unhealthy, <u> unmanaged, <k> unknown`.
   `<m>` counts every live app this env's audit covers, including the root, and excludes apps that belong to other envs.
   `<k>` counts sources whose comparison could not be made. Print
   `No drift: everything declared is live, in sync and healthy.` ONLY when every count is 0 (in particular unknown is 0);
   if `<k>` is not 0, print the summary line with the unknown count and say to check repo access.

## Notes

- **Read-only.** Never `sync`, `apply`, `delete`, or edit anything. Offer to
  generate the fix PR via `/argocd-deploy` but do not act.
- This replaces the hand-written `applications.txt` reconcile loop.
