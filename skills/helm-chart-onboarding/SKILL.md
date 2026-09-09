---
name: helm-chart-onboarding
description: How to take an upstream Helm chart into the Argo CD catalog — locate it (ArtifactHub / helm repo search), choose and pin an exact version, pull its default values, and produce a minimal override file. Load when adding a chart to a GitOps repo's charts/ directory.
---

# Helm chart onboarding

## Goal

Produce `charts/<app>/Chart.yaml` (wrapper) and `charts/<app>/values.yaml`
(minimal override) for an upstream chart, with an **exact** pinned version.

## Step 1 — locate the chart

If the user gave a repo URL, use it. Otherwise search:

- `helm search hub <term> --max-col-width 0` — searches ArtifactHub.
- Or query the ArtifactHub REST API for the canonical repo URL and versions —
  see `reference/artifacthub-api.md`. Use WebFetch; no API key needed.

Prefer the **official / vendor** repo over re-packagers. Record the
`repository` URL (the Helm repo, e.g. `https://charts.bitnami.com/bitnami`, not
the ArtifactHub page).

## Step 2 — choose a version

- List versions: `helm search repo <repo>/<chart> --versions` (after
  `helm repo add`), or the ArtifactHub API.
- Default to the **latest stable** (non-`-rc`, non-`-beta`) unless the user names
  one, or unless the latest requires a Kubernetes version newer than the target
  cluster (`helm show chart ... | grep kubeVersion`).
- Pin the **exact** version. Never a range, never `*`, never omit.

## Step 3 — pull upstream defaults

```bash
helm show values <chart> --repo <repo-url> --version <version> > /tmp/<app>-upstream-values.yaml
```

Read it. Identify the handful of keys that matter for a first deploy:
image/tag (if you want to pin harder), ingress, persistence, resources,
replica count, service type. **Do not** copy the whole file.

## Step 4 — write the wrapper

Render `templates/Chart.yaml.tmpl` and `templates/values.yaml.tmpl` from the
plugin with: `APP_NAME`, `CHART_NAME`, `CHART_VERSION`, `CHART_REPO_URL`.

The override file nests everything under the **chart name** (the dependency
name), because that is how Helm routes subchart values:

```yaml
<chart-name>:
  <only the keys you are changing>
```

## Step 5 — verify locally before committing

```bash
helm dependency build charts/<app>
helm lint charts/<app>
helm template charts/<app> | kubectl apply --dry-run=client -f -   # if a cluster is reachable
```

All three must pass. `helm dependency build` writes `Chart.lock` and
`charts/*.tgz` — add `charts/<app>/charts/` and `Chart.lock` handling per the
repo's `.gitignore` (default: commit `Chart.lock`, ignore the `.tgz`).

## Step 6 — update the catalog inventory

Add a row to `.claude/CLAUDE.md`'s "Catalog inventory" table:
`| <app> | <chart> | <version> | <repo-url> |`.
