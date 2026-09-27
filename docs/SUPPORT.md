# Supported tools & versions

The plugin's commands shell out to these. Versions below are what CI verifies
(the `smoke` job) or what the plugin was developed and dogfooded against.

| Tool | Minimum | CI-verified | Notes |
|------|---------|-------------|-------|
| `git` | 2.30 | — | any modern git |
| `gh` (GitHub CLI) | 2.40 | — | authenticated (`gh auth login`); needed for repo creation + PRs |
| `helm` | 3.14 | 3.16.2 (also verified on 3.19, 2026-09-27) | v3.8+ for multi-source `$values`; `helm dependency build` needs a `Chart.lock` (else `helm dependency update`) |
| `kubectl` | 1.28 | (kind-action default) | only for bootstrap, audit, doctor, sync |
| `argocd` CLI | 2.10 | — | optional — the commands fall back to `kubectl` |
| `python` + PyYAML | 3.10 | 3.10, 3.12 | `scripts/helm_deps.sh` and `/argocd-deploy` validation need PyYAML; `fetch_dashboard.py` and `render_template.py` are stdlib only; also the test suite |
| `ssh-keygen` (OpenSSH) | any | — | private GitOps repos only (Argo CD deploy key in `/argocd-bootstrap`) |
| `bash` + POSIX tools (`awk`, `sort`, `comm`, `tr`, `mktemp`) | any | — | used by `scripts/*.sh`; ship with Git Bash, WSL, macOS, Linux. `jq` is NOT required |
| Argo CD (server / chart) | 2.6 / argo-cd chart 5.20 (first chart shipping Argo CD 2.6.0; 5.0–5.19 ship 2.4/2.5) | 3.5 / chart 10.8 | **2.6 is a hard floor** — multi-source Applications. `/argocd-bootstrap` pins the newest stable chart at run time (10.9.2 / v3.5.3, verified live 2026-09-27) |
| Prometheus Operator | 0.7x | 0.9x | for `/argocd-add-manifest` ServiceMonitor/PodMonitor |

## Operating systems

CI runs the unit tests and the cluster-free smoke scripts on
**ubuntu-latest, macos-latest, and windows-latest** (Windows via Git Bash).
The `argocd_e2e.sh` cluster test runs on Ubuntu + `kind`.

## Local test clusters

kind's default node image (Kubernetes 1.37 for kind v0.33) needs cgroup v2. On Docker Desktop with cgroup v1,
use `kindest/node:v1.34.x` (verified 2026-09-27).

## Not supported

- Flux (the skills are Argo CD-specific).
- Windows `cmd.exe` / PowerShell for the smoke scripts — they are Bash; on Windows
  use Git Bash / WSL.
