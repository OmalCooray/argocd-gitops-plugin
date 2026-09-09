---
name: argocd-repo-conventions
description: Conventions for an Argo CD GitOps repo managed by argocd-gitops-plugin — the catalog + environments layout, file naming, how Application manifests wire charts to per-environment values, and the dev/prod revision-tracking model. Load before creating or editing any file in such a repo.
---

# Argo CD GitOps repo conventions

## Mental model

Two separate concerns, two separate directory trees:

1. **Catalog** (`charts/<app>/`) — a Helm *wrapper chart* per app. Declares the
   upstream chart as a dependency and holds environment-agnostic base overrides.
   A folder here deploys **nothing** by itself.
2. **Deployment set** (`environments/<env>/`) — which apps run on which cluster.
   An `Application` manifest in `environments/<env>/apps/` is the *fact* that
   `<app>` is deployed to `<env>`.

The **root application** (`environments/<env>/root.yaml`) is an app-of-apps that
syncs every `Application` in that environment's `apps/` folder. Applying it once
replaces any hand-run reconcile script.

## Directory layout

See `reference/repo-layout.md` for the annotated tree. Summary:

```
charts/<app>/{Chart.yaml,values.yaml}
environments/<env>/root.yaml
environments/<env>/apps/<app>.yaml
environments/<env>/values/<app>.yaml      # optional overlay
bootstrap/install.sh
.claude/CLAUDE.md
CODEOWNERS
```

## Naming rules

- `<app>` — kebab-case, matches the catalog folder name, the `Application`
  `metadata.name`, and the file stem in `apps/` and `values/`.
- One upstream chart per catalog entry. If you need two, make two entries.
- `<env>` — kebab-case cluster/environment name (e.g. `data-platform`, `prod`).
- Wrapper chart `version` starts at `0.1.0` and is bumped when the *wrapper*
  changes; `appVersion` mirrors the upstream chart version (an intentional
  traceability convention for this repo — Helm's own convention is that
  `appVersion` is the deployed app's version; don't "correct" it and drift from
  `templates/Chart.yaml.tmpl`).

## Wrapper chart

`Chart.yaml` — `apiVersion: v2`, one entry under `dependencies` pinning the
upstream chart by exact version (never a range, never `*`).

`values.yaml` — overrides nest under the **dependency name** so Helm routes them
to the subchart:

```yaml
<chart-name>:
  image:
    tag: "x.y.z"
```

Get upstream defaults with `helm show values <chart> --repo <url> --version <v>`
(for `oci://` charts: `helm show values oci://<registry>/<chart> --version <v>`,
no `--repo`) and copy only the keys you change.

## Application manifest

Multi-source spec — see `reference/application-manifest.md` for every field.
Key points:
- source 1: `path: charts/<app>`, `helm.valueFiles: [$values/environments/<env>/values/<app>.yaml]`
- source 2: same repo, `ref: values` (this is what `$values` resolves to)
- `syncPolicy.automated` with `prune: true`, `selfHeal: true`
- `syncOptions: [CreateNamespace=true, ServerSideApply=true]`
- requires **Argo CD ≥ 2.6** (multi-source apps). Note this in the repo README.

## Revision-tracking model

Key off the environment's **role**, not its literal name (see
`commands/argocd-deploy.md` for the classification):

- Fast-iteration / non-release environment (e.g. `dev`, `data-platform`,
  `staging`) → `targetRevision: <default-branch>` — auto-syncs on merge.
- Release / production environment (`prod`, `production`) →
  `targetRevision: <git-sha-or-tag>` — moves only via an explicit PR that bumps
  the pin.
- Environments are **directories, not branches**. Promotion is a PR editing the
  target env's `values/<app>.yaml` or bumping its `targetRevision`. Never
  merge one environment branch into another.

## When editing an existing repo

Read `.claude/CLAUDE.md` first for repo-specific facts (repo URL, env names,
Argo CD namespace, catalog inventory). Follow the existing file style exactly.
