---
name: argocd-add-chart
description: Add an upstream Helm chart to the GitOps repo catalog — research it, pin an exact version, generate the wrapper Chart.yaml and a minimal values.yaml under charts/<app>/, verify with helm lint, and open a PR. Does not deploy anything.
argument-hint: "<app-name> [chart-version] [--repo <helm-repo-url>] [--context <name>]"
---

Add a chart to `charts/<app>/` in the current GitOps repo.

**Follow the interaction contract:** `${CLAUDE_PLUGIN_ROOT}/references/interaction-style.md`
— announce each step, show commands + key output, checkpoint before `git push` /
opening the PR, end with a summary.

## Inputs

- `$1` — app/catalog name (kebab-case, required).
- `$2` — exact chart version (optional; if omitted, pick latest stable).
- `--repo <url>` — Helm repo URL (optional; if omitted, discover via ArtifactHub).

## Preconditions

0. **Resolve the target:** follow `${CLAUDE_PLUGIN_ROOT}/references/target-resolution.md`; use its `CTX` and `ARGOCD_NS` in every command below. Accept an optional `--context <name>` argument.
- CWD is a GitOps repo (`charts/` and `.claude/CLAUDE.md` exist).
- Working tree is clean (or ask before proceeding).
- If `charts/<app>/` already exists, stop — tell the user to pick a different
  name or edit the existing entry directly.

## Steps

1. Load skills `helm-chart-onboarding` and `argocd-repo-conventions`.
2. Create a branch: `git switch -c add-chart/<app>`.
3. Follow `helm-chart-onboarding` steps 1–4 to determine `CHART_NAME`,
   `CHART_VERSION` (exact), `CHART_REPO_URL`.
4. Render with the renderer script (errors on a missing or unused variable):
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/render_template.py" "${CLAUDE_PLUGIN_ROOT}/templates/Chart.yaml.tmpl" charts/<app>/Chart.yaml \
     APP_NAME=<app> CHART_NAME=<chart> CHART_VERSION=<version> CHART_REPO_URL=<repo-url>
   python "${CLAUDE_PLUGIN_ROOT}/scripts/render_template.py" "${CLAUDE_PLUGIN_ROOT}/templates/values.yaml.tmpl" charts/<app>/values.yaml \
     CHART_NAME=<chart> CHART_VERSION=<version> CHART_REPO_URL=<repo-url>
   ```
5. Verify (must pass — do not skip):
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/helm_deps.sh" charts/<app>   # builds in place; private Helm repo config
   helm lint charts/<app>
   ```
   If a cluster is reachable also run
   `helm template charts/<app> | kubectl --context "$CTX" apply --dry-run=client -f -`.
5a. **Chart notes.** If `${CLAUDE_PLUGIN_ROOT}/skills/values-review/reference/chart-notes.md` has a section for
   this chart (heading starts with the chart name, e.g. `metrics-server`, `kube-prometheus-stack`), read it and apply
   its **base-values block** to `charts/<app>/values.yaml`. Apply only the environment-agnostic parts. Anything the
   note marks "local clusters only" (e.g. metrics-server `--kubelet-insecure-tls`, the kube-prometheus-stack light
   demo profile) never goes in the catalog: tell the user it belongs in the env overlay and is added by
   `/argocd-deploy`. Re-run step 5's `helm lint` afterwards.
5b. **CRD ownership check.** (Does the chart render any `CustomResourceDefinition`?) One script does the detection (temp-copy render with `--include-crds`; your tree and
   `Chart.lock` are untouched; prints only the CRD names, sorted, one per line):
   ```bash
   o="$(mktemp -d)"
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/list_crds.sh" charts/<app> --namespace <ns> > "$o/mine"; cat "$o/mine"
   ```
   If it exits non-zero, show its `error:` line and stop. If the list is empty, nothing more to do. Otherwise this app
   is a **CRD provider**: tell the user, remember it for step 7, and say `/argocd-deploy` will offer a sync-wave `"-1"`.
   Then check for overlap with every other catalog chart:
   ```bash
   for c in charts/*/; do n="$(basename "$c")"; [ "$n" = "<app>" ] && continue
     bash "${CLAUDE_PLUGIN_ROOT}/scripts/list_crds.sh" "$c" > "$o/other" || continue
     comm -12 "$o/mine" "$o/other" | sed "s/^/$n also renders: /"; done
   ```
   (`<ns>` is only a render namespace; it does not affect CRD names. Delete `$o` afterwards.) If a line prints, name the
   roles: the chart that OWNS standalone CRDs (e.g. `prometheus-operator-crds`) is the **provider**; a chart that
   BUNDLES the same CRDs (e.g. `kube-prometheus-stack`) is the **consumer**. On the consumer set
   `<dependency-name>.crds.enabled: false` in its env overlay, but only after confirming with `helm show values` that the
   chart has a top-level `crds:` with `enabled`. If the key is absent, or is per-CRD (like `crds.<name>.enabled`),
   do NOT guess: tell the user about the overlap and stop for a decision. Do not edit the other chart here.
6. Commit `charts/<app>/Chart.yaml`, `charts/<app>/values.yaml`,
   `charts/<app>/Chart.lock`. (Do not commit `charts/<app>/charts/*.tgz`.)
7. Update `.claude/CLAUDE.md` catalog inventory table; commit that too. If step 5b found CRDs, append ` (CRD provider)`
   to the app's cell in its row (e.g. `prometheus-operator-crds (CRD provider)`): `/argocd-deploy` reads this marker.
8. Show the user the rendered file(s) and the drafted PR title + body, and ask
   them to confirm before pushing. If they decline, leave the commits on the
   local branch and stop.
   Push the branch and open a PR with `gh pr create`:
   - title: `Add <app> to catalog (<chart> <version>)`
   - body: chart source, version, why this version, and the output of
     `helm template charts/<app> | head -60` in a fenced block.
   - If `gh` is missing/unauthenticated: print the branch name and the PR body
     text, tell the user to open the PR manually. Do not fail silently.
9. Print: chart version pinned, files created, PR URL (or manual instructions).

## Notes

- Never deploy here. Deployment is `/argocd-deploy <app> <env>`.
- Never commit to the default branch directly.
- Never adds `charts/<app>/templates/`. To add your own manifests (ServiceMonitor, IngressRoute, …) use `/argocd-add-manifest`.
