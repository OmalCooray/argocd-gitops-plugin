# argocd-gitops-plugin

[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![ci](https://github.com/OmalCooray/argocd-gitops-plugin/actions/workflows/ci.yml/badge.svg)](https://github.com/OmalCooray/argocd-gitops-plugin/actions/workflows/ci.yml)

A Claude Code plugin for running applications on Argo CD with GitOps. A Git repo
becomes the single source of truth for what runs on your cluster; the plugin
scaffolds that repo, onboards Helm charts, deploys them, drives each app to
healthy, and audits drift between git and the live cluster. It
scaffolds and operates a repo with a **catalog** of Helm wrapper charts and one
folder per **environment**, wired together with the app-of-apps pattern.

## What it does

| Command | Purpose |
|---------|---------|
| `/argocd-init-repo` | Scaffold a new GitOps repo and (optionally) create + push the GitHub repo. |
| `/argocd-bootstrap` | Generate `bootstrap/install.sh` — installs Argo CD and applies the root app. |
| `/argocd-add-chart` | Research an upstream Helm chart, pin it, scaffold `charts/<app>/`, open a PR. |
| `/argocd-deploy` | Wire a catalog app into an environment (`Application` + values overlay), open a PR, then drive it to Healthy. |
| `/argocd-sync` | Drive an already-declared app to Synced + Healthy + a passing functional check — diagnose → fix in git → re-sync on any stall. |
| `/argocd-add-manifest` | Add your own templated manifest (ServiceMonitor/PodMonitor, or any kind via free text) to a wrapper chart's `templates/`, gated + verified, open a PR. Opt-in. |
| `/argocd-add-dashboard` | Import a community Grafana dashboard (grafana.com id / URL / file) for a scraped app — normalized + rendered as a sidecar ConfigMap in a per-app folder. Opt-in. |
| `/argocd-review-values` | Check a chart's values against a dev/prod readiness rubric; optionally open a PR with a hardened overlay. |
| `/argocd-doctor` | Diagnose a stuck / Degraded / OutOfSync app — one-shot inspection, root cause, and the fix. |
| `/argocd-audit` | Read-only drift report: repo vs live Argo CD. |

Usage (arguments in `[]` are optional; `--context <name>` pins the kube-context, otherwise the plugin resolves and confirms one):

```
/argocd-init-repo <repo-name> [environment-name]
/argocd-bootstrap [kube-context | --context <name>] [--env <environment>]
/argocd-add-chart <app-name> [chart-version] [--repo <helm-repo-url>] [--context <name>]
/argocd-deploy <app-name> <environment-name> [--context <name>]
/argocd-sync <app-name> [environment-name] [--context <name>]
/argocd-add-manifest <app> <kind>   (kind: servicemonitor | podmonitor | free text) [--context <name>]
/argocd-add-dashboard <app> <source>   (source: grafana.com id | https URL | local .json) [--context <name>]
/argocd-review-values <app-name> [environment-name] [--profile dev|prod] [--write] [--context <name>]
/argocd-doctor [app-name]  (omit to triage every app in the env) [--fix] [--context <name>]
/argocd-audit [environment-name] [--context <name>]
```

Plus the `argocd-onboarder` agent, which does add-chart -> deploy -> PR in one run.

Every command follows an [interaction contract](references/interaction-style.md):
each step is announced, commands and their key output are shown, long operations
(installs, syncs) run in the foreground with visible progress, and there's a
one-line checkpoint before anything that changes a cluster or opens a PR — no
silent background work, no health-polling loops.

## Prerequisites

Everything runs through your shell — no MCP servers, daemons, or extra services.
The commands shell out to standard CLIs, so those must be installed and on `PATH`.

**Environment**

- [Claude Code](https://claude.com/claude-code) with plugin support.
- A **Bash** shell. macOS/Linux work out of the box; on Windows use **Git Bash or
  WSL** (`cmd.exe` and PowerShell are not supported).
- Network access to GitHub, your Helm chart repositories, and (for
  `/argocd-add-dashboard`) grafana.com.

**Tools** (minimums match [docs/SUPPORT.md](docs/SUPPORT.md))

| Tool | Min | Needed for | Verify |
|------|-----|------------|--------|
| `git` | 2.30 | every command | `git --version` |
| `gh` (GitHub CLI), logged in | 2.40 | creating the repo and opening PRs (`init-repo`, `add-chart`, `deploy`, `add-manifest`, `add-dashboard`, `review-values --write`). Without it the commands print manual steps instead. | `gh auth status` |
| `helm` | 3.14 | `add-chart`, `deploy`, `add-manifest`, `add-dashboard`, `review-values`, and the generated `bootstrap/install.sh` | `helm version --short` |
| `kubectl` | 1.28 | `bootstrap`, `audit`, `doctor`, `sync` | `kubectl version --client` |
| `python` **+ PyYAML** | 3.10 | PyYAML is needed by `deploy` (YAML validation) and `scripts/helm_deps.sh` (used by `add-chart`, `review-values`, `doctor`, `add-manifest`, the onboarder); `add-dashboard`'s fetch script and the template renderer use only the standard library | `python -c "import yaml"` |
| `ssh-keygen` (OpenSSH) | any | private GitOps repos only — `bootstrap` generates the Argo CD deploy key | `ssh -V` |
| `awk`, `sed`, `grep`, `sort`, `comm`, `tr`, `mktemp`, `base64` | any | the helper scripts in `scripts/` and the inline commands in `bootstrap`, `add-chart`, `add-dashboard`, `review-values`; ship with Git Bash, WSL, macOS and Linux. `shred` is optional (`bootstrap` falls back to `rm`) | `awk 'BEGIN{print 1}'` |
| `argocd` CLI | 2.10 | *optional* — the commands read state with `kubectl`; the CLI is only a convenience for you | `argocd version --client` |
| `curl` | any | *optional* — checking that Prometheus is scraping a new ServiceMonitor or that a dashboard's metrics exist (`jq` is optional: used only in a Prometheus verification example) | `curl --version` |

Install PyYAML with `python -m pip install pyyaml`.

**Cluster and accounts**

- A Kubernetes cluster you can administer (kind, Docker Desktop, minikube, or a
  managed cluster), reachable from your kubeconfig. Needed only for `bootstrap`,
  `audit`, `doctor`, and `sync` — scaffolding (`init-repo`, `add-chart`, `deploy`)
  works without one.
- Argo CD **2.6 or newer** on the cluster (multi-source Applications are a hard
  floor). `/argocd-bootstrap` installs it for you.
- A GitHub account with permission to create repos and push branches.

**Check your setup**

```
git --version && gh auth status && helm version --short && kubectl version --client && python -c "import yaml; print('pyyaml ok')"
```

## Safety model

- **Target first.** Before touching a cluster, a command resolves the kube-context, prints a `Target:` line and asks
  for a checkpoint; every cluster call (`kubectl`, `helm install/upgrade`) then carries an explicit context
  ([details](references/target-resolution.md)).
- **No needless syncs.** `/argocd-sync` refreshes before syncing, exits when the app is already Synced and Healthy,
  and never force-syncs a healthy app.
- **Privileged manifests are refused.** `/argocd-add-manifest` will not author cluster-admin bindings, `system:masters`
  grants and similar.
- **Secrets stay out of output.** A generated deploy key's private half is never printed or committed.
- **Nothing is pushed silently.** Pushes and PRs sit behind a checkpoint; with no remote or no `gh`, the plugin prints
  the manual steps ([details](references/no-remote-fallback.md)).

## Install

```
/plugin marketplace add OmalCooray/argocd-gitops-plugin
/plugin install argocd-gitops-plugin@argocd-gitops-plugin
```

The plugin and its marketplace share the same name, hence `<plugin>@<marketplace>`. Restart Claude Code or run
`/reload-plugins` to pick it up. Update later with `/plugin marketplace update`.

For development, point Claude Code at a local checkout with `--plugin-dir`:
`claude --plugin-dir <path-to-checkout>`.

## Typical flow

From nothing to a running, audited app:

```
/argocd-init-repo data-platform-k8s-configs data-platform
cd data-platform-k8s-configs
/argocd-bootstrap docker-desktop --env data-platform   # then run ./bootstrap/install.sh
/argocd-add-chart podinfo               # review + merge the PR
/argocd-deploy podinfo data-platform    # review + merge the PR
/argocd-audit data-platform
```

## Limitations

- **One environment per scaffold.** The generated repo starts with a single environment; multi-environment
  scaffolding and promotion are planned (see the [roadmap](docs/ROADMAP.md)).
- **Secrets are not managed.** Create them out-of-band with `kubectl create secret`; the Argo CD deploy-key Secret for
  a private repo is the only one the plugin creates.
- **No rollback command.** Revert in git and re-sync.
- **Argo CD only.** Flux is not supported.
- **Bash-based.** Commands run through Bash (Git Bash or WSL on Windows).
- **Behaviour is verified by contract tests and live runs.** The commands and skills are instructions followed by
  the model; there is no formal eval suite yet.

## License

[MIT](LICENSE).

## Design & roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md) for the full roadmap and design doc.
[Supported tools & versions](docs/SUPPORT.md) — tool matrix and OS coverage.
[Contributing](docs/CONTRIBUTING.md) — dev flow, tests, release process.
[Changelog](CHANGELOG.md) — release history.

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
