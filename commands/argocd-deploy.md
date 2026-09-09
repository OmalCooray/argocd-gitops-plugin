---
name: argocd-deploy
description: Deploy a catalog app to an environment — generate environments/<env>/apps/<app>.yaml (multi-source Argo CD Application) plus an empty per-env values overlay, verify, and open a PR.
argument-hint: "<app-name> <environment-name>"
---

Wire an existing catalog chart into an environment.

## Inputs

- `$1` — app name; must already exist at `charts/<app>/`.
- `$2` — environment name; must already exist at `environments/<env>/`.

## Preconditions

- CWD is a GitOps repo. `charts/<app>/Chart.yaml` exists. `environments/<env>/`
  exists. If either is missing, tell the user which command to run first
  (`/argocd-add-chart` or `/argocd-add-env`).
- Read `.claude/CLAUDE.md` for `GITOPS_REPO_URL`, `ARGOCD_NAMESPACE`,
  `DEST_SERVER`, and the default branch.

## Steps

1. Load skill `argocd-repo-conventions`.
2. `git switch -c deploy/<app>-<env>`.
3. Determine `TARGET_REVISION`:
   - dev-like environment (name in {`dev`, `data-platform`, `staging`} or the
     repo's single env) → the default branch.
   - `prod` / `production` → the current default-branch HEAD SHA
     (`git rev-parse origin/<branch>`), and note in the PR that this pin must be
     bumped to promote future changes.
   - Otherwise ask.
4. Ask for the destination namespace (default: `<app>`).
5. Render `${CLAUDE_PLUGIN_ROOT}/templates/application.yaml.tmpl` →
   `environments/<env>/apps/<app>.yaml` with `APP_NAME`, `ARGOCD_NAMESPACE`,
   `GITOPS_REPO_URL`, `TARGET_REVISION`, `ENV_NAME`, `NAMESPACE`, `DEST_SERVER`.
6. Create `environments/<env>/values/<app>.yaml` if absent, with content:
   ```yaml
   # Per-environment overrides for <app> in <env>. Nest under the chart name.
   ```
7. Verify:
   ```bash
   kubectl apply --dry-run=client -f environments/<env>/apps/<app>.yaml
   ```
   (If Argo CD CRDs aren't on the reachable cluster, fall back to a YAML parse
   check: `python -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" environments/<env>/apps/<app>.yaml`.)
8. Update `.claude/CLAUDE.md` deployment matrix (mark `<app>` × `<env>`). Commit.
9. Push, `gh pr create`:
   - title: `Deploy <app> to <env>`
   - body: source paths, target revision (and pin caveat for prod), destination
     namespace, and `helm template charts/<app> -f environments/<env>/values/<app>.yaml | head -60`.
   - `gh` missing → print branch + PR body, stop.
10. Print the PR URL (or manual steps) and remind the user that merge → the
    environment's root app picks it up automatically.

## Notes

- Never `kubectl apply` the Application to a live cluster from here — merging the
  PR is the deploy. Applying by hand is the user's decision.
