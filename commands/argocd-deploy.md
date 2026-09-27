---
name: argocd-deploy
description: Deploy a catalog app to an environment — generate environments/<env>/apps/<app>.yaml (multi-source Argo CD Application) plus an empty per-env values overlay, verify, and open a PR.
argument-hint: "<app-name> <environment-name> [--context <name>]"
---

Wire an existing catalog chart into an environment.

**Follow the interaction contract:** `${CLAUDE_PLUGIN_ROOT}/references/interaction-style.md`
— announce each step, show commands + key output, checkpoint before `git push` /
opening the PR, never force a sync or apply the Application by hand, end with a
summary.

## Inputs

- `$1` — app name; must already exist at `charts/<app>/`.
- `$2` — environment name; must already exist at `environments/<env>/`.

## Preconditions

0. **Resolve the target:** follow `${CLAUDE_PLUGIN_ROOT}/references/target-resolution.md`; use its `CTX` and `ARGOCD_NS` in every command below. Accept an optional `--context <name>` argument.
- CWD is a GitOps repo. `charts/<app>/Chart.yaml` exists — if not, tell the user
  to run `/argocd-add-chart` first.
- `environments/<env>/` exists. If it does not: Phase 1 has no command to add an
  environment — create the folder manually (`environments/<env>/root.yaml` from
  the plugin's `root.yaml.tmpl`, plus empty `apps/` and `values/` dirs) or re-run
  `/argocd-init-repo` for a fresh repo. Then retry.
- If `environments/<env>/apps/<app>.yaml` already exists, stop — the app is
  already deployed to that env; edits go through a normal PR, not this command.
- Read `.claude/CLAUDE.md`: `GITOPS_REPO_URL` = the "GitOps repo URL" line,
  `ARGOCD_NAMESPACE` = "Argo CD namespace", `DEST_SERVER` = "Destination cluster for
  <env>", default branch = "Default branch".

## Steps

1. Load skill `argocd-repo-conventions`.
2. `git switch -c deploy/<app>-<env>`. (branch-exists rule: `${CLAUDE_PLUGIN_ROOT}/references/interaction-style.md`)
3. Determine `TARGET_REVISION`:
   - dev-like environment (name in {`dev`, `data-platform`, `staging`} or the
     repo's single env) → the default branch.
   - `prod` / `production` → the current default-branch HEAD SHA
     (`git fetch origin <branch>` then `git rev-parse origin/<branch>`; if
     `origin/<branch>` is unknown — e.g. the repo was never pushed — ask the user
     for the revision to pin), and note in the PR that this pin must be bumped to
     promote future changes.
   - Otherwise ask.
4. Ask for the destination namespace (default: `<app>`).
5. Render with the renderer script (errors on a missing or unused variable). Read
   from `.claude/CLAUDE.md`: `GITOPS_REPO_URL` from the "GitOps repo URL" line,
   `ARGOCD_NAMESPACE` from "Argo CD namespace", `DEST_SERVER` from "Destination
   cluster for <env>". `TARGET_REVISION` is the value computed in step 3;
   `<app-namespace>` is the destination namespace from step 4:
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/render_template.py" "${CLAUDE_PLUGIN_ROOT}/templates/application.yaml.tmpl" environments/<env>/apps/<app>.yaml \
     APP_NAME=<app> ENV_NAME=<env> NAMESPACE=<app-namespace> ARGOCD_NAMESPACE=<argocd-namespace> \
     GITOPS_REPO_URL=<gitops-repo-url> TARGET_REVISION=<rev> DEST_SERVER=<server>
   ```
5a. **Sync-wave for CRD providers.** Decide whether `<app>` provides CRDs: (1) its row in the `.claude/CLAUDE.md`
   catalog inventory carries the `(CRD provider)` marker (set by `/argocd-add-chart`); or, when the marker is absent
   (chart added by hand or before this feature), (2) re-run the detector on it:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/list_crds.sh" charts/<app> --namespace <app-namespace>      --values environments/<env>/values/<app>.yaml   # omit --values if that file does not exist yet
   ```
   (non-empty output = provider; a non-zero exit prints an `error:` line: show it and ask the user). Known CRD/operator
   charts (`prometheus-operator-crds`, `cert-manager`, `kube-prometheus-stack`) are only a fallback hint if the script
   cannot run. If `<app>` provides CRDs, ask
   `> This app provides CRDs. Add sync-wave "-1" so it syncs before apps that use them? (yes/no)` (default yes).
   On yes, after rendering, add under `metadata.annotations:` of `environments/<env>/apps/<app>.yaml` (the template has
   no annotations slot; add the key `annotations:` between `namespace:` and `finalizers:` only if it is absent):
   ```yaml
   metadata:
     annotations:
       argocd.argoproj.io/sync-wave: "-1"
   ```
   Idempotence: read `metadata.annotations["argocd.argoproj.io/sync-wave"]` first; if already `"-1"` do nothing, if
   another value ask before changing it, never duplicate the key. Waves order lowest first, so the provider's `"-1"`
   must be LOWER than the consumers' (default `0` when the annotation is absent). Confirm `ServerSideApply=true` is in
   `syncOptions` (the template sets it; CRDs are large and need it). Do not edit the template's placeholders.
6. Create `environments/<env>/values/<app>.yaml` if absent, with content:
   ```yaml
   # Per-environment overrides for <app> in <env>. Nest under the chart name.
   ```
   If a chart-notes section (`${CLAUDE_PLUGIN_ROOT}/skills/values-review/reference/chart-notes.md`) names a
   "local clusters only" override for this chart (e.g. metrics-server `--kubelet-insecure-tls`) and `$CTX` is a local
   cluster, put it here, commented `# local clusters only — do not copy to prod`.
7. Verify:
   ```bash
   kubectl --context "$CTX" apply --dry-run=client -f environments/<env>/apps/<app>.yaml
   ```
   (If Argo CD CRDs aren't on the reachable cluster, fall back to a YAML parse
   check: `python -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" environments/<env>/apps/<app>.yaml`.)
8. Update `.claude/CLAUDE.md` deployment matrix (mark `<app>` × `<env>`). Commit.
9. Show the user the rendered file(s) and the drafted PR title + body, and ask
   them to confirm before pushing. If they decline, leave the commits on the
   local branch and stop.
   Push, `gh pr create`:
   - title: `Deploy <app> to <env>`
   - body: source paths, target revision (and pin caveat for prod), destination
     namespace, and `helm template charts/<app> -f environments/<env>/values/<app>.yaml | head -60`.
   - No remote, or `gh` missing/unauthenticated: follow
     `${CLAUDE_PLUGIN_ROOT}/references/no-remote-fallback.md`.
10. Print the PR URL (or manual steps).
11. **Drive it to healthy.** Once the PR is merged (checkpoint: ask if you should
    merge it now, or wait for them to), run the `/argocd-sync <app> <env>` flow:
    load the `argocd-rollout` skill and take the app from declared → Synced →
    Healthy → a passing functional check, diagnosing and fixing (further PRs) any
    stall. A deploy is not done at "PR merged" — it's done when the app works.
    If the user said not to merge, stop after the PR and tell them to run
    `/argocd-sync <app> <env>` after merging.

## Notes

- Never `kubectl apply` the Application to a live cluster from here — merging the
  PR is the deploy. Applying by hand is the user's decision.
- **Ordering between apps:** if `<app>` depends on another app in the same env
  (e.g. Airflow needs its external database first), add
  `argocd.argoproj.io/sync-wave: "-1"` (lower = earlier) under
  `metadata.annotations` of the dependency's `Application`, so the root app syncs
  it before the dependent one.
- Never adds `charts/<app>/templates/`. To add your own manifests (ServiceMonitor, IngressRoute, …) use `/argocd-add-manifest`.
