---
name: argocd-audit
description: Read-only drift report — compare the Argo CD Applications declared in environments/<env>/apps/ against what a live cluster actually has, and against each app's sync/health status. Changes nothing.
argument-hint: "[environment-name]"
---

Report drift between the GitOps repo and a live Argo CD instance.

**Follow the interaction contract:** `${CLAUDE_PLUGIN_ROOT}/references/interaction-style.md`
— announce each step, show commands + key output, one-shot (no polling), end with
a summary. This command is read-only, so no checkpoints are needed.

## Inputs

- `$1` — environment to audit (optional; default: audit every `environments/*/`).

## Preconditions

- CWD is a GitOps repo.
- A reachable cluster/Argo CD. Prefer the `argocd` CLI if logged in; else
  `kubectl` against the Argo CD namespace. If neither works, run in **offline
  mode**: ask the user to paste `argocd app list -o json` (or
  `kubectl get applications -n argocd -o json`) output.
- If `mcp__argocd__*` tools are available, use them instead of shelling out.

## Steps

1. Build the **declared set**: for each `environments/<env>/apps/*.yaml`, the
   `metadata.name` and its `spec.source(s).targetRevision` + `path`.
2. Build the **live set**:
   - `argocd app list -o json` → name, `spec`, `status.sync.status`,
     `status.health.status`, `status.sync.revision`.
   - or `kubectl get applications -n <argocd-ns> -o json`.
3. Report three tables:
   - **Missing in cluster**: declared but not live → root app not synced, or
     never bootstrapped.
   - **Orphaned in cluster**: live but not declared → left over; should be
     pruned (or was created outside GitOps).
   - **Drift / unhealthy**: live and declared but `OutOfSync`, `Degraded`,
     `Missing`, or `targetRevision`/`path` differs from the repo.
4. For each row, give the one-line likely cause and the corrective command
   (e.g. `argocd app sync <name>`, "merge PR #NN", "delete `apps/<x>.yaml`").
5. Print a summary line: `<n> declared, <m> live, <k> drifted`.

## Notes

- **Read-only.** Never `sync`, `apply`, `delete`, or edit anything. Offer to
  generate the fix PR via `/argocd-deploy` but do not act.
- This replaces the hand-written `applications.txt` reconcile loop.
