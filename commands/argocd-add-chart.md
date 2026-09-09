---
name: argocd-add-chart
description: Add an upstream Helm chart to the GitOps repo catalog — research it, pin an exact version, generate the wrapper Chart.yaml and a minimal values.yaml under charts/<app>/, verify with helm lint, and open a PR. Does not deploy anything.
argument-hint: "<app-name> [chart-version] [--repo <helm-repo-url>]"
---

Add a chart to `charts/<app>/` in the current GitOps repo.

## Inputs

- `$1` — app/catalog name (kebab-case, required).
- `$2` — exact chart version (optional; if omitted, pick latest stable).
- `--repo <url>` — Helm repo URL (optional; if omitted, discover via ArtifactHub).

## Preconditions

- CWD is a GitOps repo (`charts/` and `.claude/CLAUDE.md` exist).
- Working tree is clean (or ask before proceeding).

## Steps

1. Load skills `helm-chart-onboarding` and `argocd-repo-conventions`.
2. Create a branch: `git switch -c add-chart/<app>`.
3. Follow `helm-chart-onboarding` steps 1–4 to determine `CHART_NAME`,
   `CHART_VERSION` (exact), `CHART_REPO_URL`.
4. Render `${CLAUDE_PLUGIN_ROOT}/templates/Chart.yaml.tmpl` →
   `charts/<app>/Chart.yaml` and `values.yaml.tmpl` → `charts/<app>/values.yaml`.
5. Verify (must pass — do not skip):
   ```bash
   helm dependency build charts/<app>
   helm lint charts/<app>
   ```
   If a cluster is reachable also run
   `helm template charts/<app> | kubectl apply --dry-run=client -f -`.
6. Commit `charts/<app>/Chart.yaml`, `charts/<app>/values.yaml`,
   `charts/<app>/Chart.lock`. (Do not commit `charts/<app>/charts/*.tgz`.)
7. Update `.claude/CLAUDE.md` catalog inventory table; commit that too.
8. Push the branch and open a PR with `gh pr create`:
   - title: `Add <app> to catalog (<chart> <version>)`
   - body: chart source, version, why this version, and the output of
     `helm template charts/<app> | head -60` in a fenced block.
   - If `gh` is missing/unauthenticated: print the branch name and the PR body
     text, tell the user to open the PR manually. Do not fail silently.
9. Print: chart version pinned, files created, PR URL (or manual instructions).

## Notes

- Never deploy here. Deployment is `/argocd-deploy <app> <env>`.
- Never commit to the default branch directly.
