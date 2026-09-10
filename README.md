# argocd-gitops-plugin

A Claude Code plugin for running applications on Argo CD with GitOps. It
scaffolds and operates a repo with a **catalog** of Helm wrapper charts and one
folder per **environment**, wired together with the app-of-apps pattern.

## What it does

| Command | Purpose |
|---------|---------|
| `/argocd-init-repo <name> [env]` | Scaffold a new GitOps repo and (optionally) create + push the GitHub repo. |
| `/argocd-bootstrap [kube-context]` | Generate `bootstrap/install.sh` — installs Argo CD and applies the root app. |
| `/argocd-add-chart <app> [version]` | Research an upstream Helm chart, pin it, scaffold `charts/<app>/`, open a PR. |
| `/argocd-deploy <app> <env>` | Wire a catalog app into an environment (`Application` + values overlay), open a PR, then drive it to Healthy. |
| `/argocd-sync <app> [env]` | Drive an already-declared app to Synced + Healthy + a passing functional check — diagnose → fix in git → re-sync on any stall. |
| `/argocd-add-manifest <app> <kind>` | Add your own templated manifest (ServiceMonitor/PodMonitor, or any kind via free text) to a wrapper chart's `templates/`, gated + verified, open a PR. Opt-in. |
| `/argocd-add-dashboard <app> <source>` | Import a community Grafana dashboard (grafana.com id / URL / file) for a scraped app — normalized + rendered as a sidecar ConfigMap in a per-app folder. Opt-in. |
| `/argocd-review-values <app> [env] [--profile dev\|prod] [--write]` | Check a chart's values against a dev/prod readiness rubric; optionally open a PR with a hardened overlay. |
| `/argocd-doctor [app]` | Diagnose a stuck / Degraded / OutOfSync app — one-shot inspection, root cause, and the fix. |
| `/argocd-audit [env]` | Read-only drift report: repo vs live Argo CD. |

Plus the `argocd-onboarder` agent, which does add-chart -> deploy -> PR in one run.

Every command follows an [interaction contract](references/interaction-style.md):
each step is announced, commands and their key output are shown, long operations
(installs, syncs) run in the foreground with visible progress, and there's a
one-line checkpoint before anything that changes a cluster or opens a PR — no
silent background work, no health-polling loops.

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

`.mcp.json.example` ships the config for
[Akuity's Argo CD MCP server](https://github.com/akuity/argocd-mcp). The plugin
does not need it — every command and agent works with the `argocd`/`kubectl`
CLIs. To enable it: copy `.mcp.json.example` to `.mcp.json` in the plugin root,
set `ARGOCD_BASE_URL` and `ARGOCD_API_TOKEN` in your environment, and restart
Claude Code. Useful for richer interactive troubleshooting once the Phase 2
doctor agent lands.

## Design & roadmap

See `docs/superpowers/specs/2026-09-10-argocd-gitops-plugin-design.md`.
Phase 2 shipped: `values-review` / `/argocd-review-values`,
`argocd-troubleshooting` / `/argocd-doctor`,
`argocd-rollout` / `/argocd-sync` (drive-to-healthy loop).
Phase 3: `/argocd-add-env`, `/argocd-promote`, secrets.

Next (planned, not yet built): `argocd-exporters` / `/argocd-observe` (spec #2b)
— provision an exporter for apps that emit no metrics (Metabase, bare MySQL) and
tie exporter → ServiceMonitor → dashboard into one command.

## Development

```
python -m pytest        # structural + template tests (no cluster needed)
bash tests/smoke/helm_smoke.sh     # renders a wrapper chart, helm lint/template
bash tests/smoke/argocd_e2e.sh     # installs Argo CD on the current context (destructive-ish)
```
