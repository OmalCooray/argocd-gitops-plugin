# Supported tools & versions

The plugin's commands shell out to these. Versions below are what CI verifies
(the `smoke` job) or what the plugin was developed and dogfooded against.

| Tool | Minimum | CI-verified | Notes |
|------|---------|-------------|-------|
| `git` | 2.30 | — | any modern git |
| `gh` (GitHub CLI) | 2.40 | — | authenticated (`gh auth login`); needed for repo creation + PRs |
| `helm` | 3.14 | 3.16.2 | v3.8+ for multi-source `$values`; `helm dependency build` needs a `Chart.lock` (else `helm dependency update`) |
| `kubectl` | 1.28 | (kind-action default) | only for bootstrap, audit, doctor, sync |
| `argocd` CLI | 2.10 | — | optional — the commands fall back to `kubectl` |
| `python` | 3.10 | 3.10, 3.12 | for `fetch_dashboard.py` and the test suite |
| Argo CD (server / chart) | 2.6 / argo-cd chart 5.x | 3.5 / chart 10.8 | **2.6 is a hard floor** — multi-source Applications |
| Prometheus Operator | 0.7x | 0.9x | for `/argocd-add-manifest` ServiceMonitor/PodMonitor |

## Operating systems

CI runs the unit tests and the cluster-free smoke scripts on
**ubuntu-latest, macos-latest, and windows-latest** (Windows via Git Bash).
The `argocd_e2e.sh` cluster test runs on Ubuntu + `kind`.

## Not supported

- Flux (the skills are Argo CD-specific).
- Windows `cmd.exe` / PowerShell for the smoke scripts — they are Bash; on Windows
  use Git Bash / WSL.
