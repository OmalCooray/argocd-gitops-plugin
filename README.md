# argocd-gitops-plugin

A Claude Code plugin for running applications on Argo CD with GitOps. It
scaffolds and operates a repo with a **catalog** of Helm wrapper charts and one
folder per **environment**, wired together with the app-of-apps pattern.

## What it does (Phase 1)

| Command | Purpose |
|---------|---------|
| `/argocd-init-repo <name> [env]` | Scaffold a new GitOps repo and (optionally) create + push the GitHub repo. |
| `/argocd-bootstrap [kube-context]` | Generate `bootstrap/install.sh` — installs Argo CD and applies the root app. |
| `/argocd-add-chart <app> [version]` | Research an upstream Helm chart, pin it, scaffold `charts/<app>/`, open a PR. |
| `/argocd-deploy <app> <env>` | Wire a catalog app into an environment (`Application` + values overlay), open a PR. |
| `/argocd-audit [env]` | Read-only drift report: repo vs live Argo CD. |

Plus the `argocd-onboarder` agent, which does add-chart -> deploy -> PR in one run.

## Requirements

Install and put on `PATH`:

- `git`
- `gh` (GitHub CLI) — authenticated (`gh auth login`). Needed for repo creation
  and PRs. Without it, commands print manual instructions instead of failing.
- `helm` v3.8+
- `kubectl`
- `argocd` CLI — only for `/argocd-audit` against a live instance.

A reachable Kubernetes cluster is needed only for bootstrap and audit, not for
scaffolding.

## Install

```
/plugin marketplace add OmalCooray/argocd-gitops-plugin
/plugin install argocd-gitops-plugin
```

Or point Claude Code at a local checkout during development.

## Typical flow

```
/argocd-init-repo data-platform-k8s-configs data-platform
cd data-platform-k8s-configs
/argocd-bootstrap docker-desktop        # then run ./bootstrap/install.sh
/argocd-add-chart podinfo               # review + merge the PR
/argocd-deploy podinfo data-platform    # review + merge the PR
/argocd-audit data-platform
```

## Optional: Argo CD MCP

`.mcp.json` ships a disabled entry for
[Akuity's Argo CD MCP server](https://github.com/akuity/argocd-mcp). The plugin
does not need it. To enable: remove the `"_disabled": true` line, set
`ARGOCD_BASE_URL` and `ARGOCD_API_TOKEN` in your environment, restart Claude
Code. Useful for richer interactive troubleshooting once the Phase 2 doctor
agent lands.

## Design & roadmap

See `docs/superpowers/specs/2026-09-10-argocd-gitops-plugin-design.md`.
Phase 2: `values-review`, `/argocd-doctor`. Phase 3: `/argocd-add-env`,
`/argocd-promote`, secrets.

## Development

```
python -m pytest        # structural + template tests (no cluster needed)
bash tests/smoke/helm_smoke.sh     # renders a wrapper chart, helm lint/template
bash tests/smoke/argocd_e2e.sh     # installs Argo CD on the current context (destructive-ish)
```
