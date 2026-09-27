# Changelog

All notable changes to this project. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project follows semantic versioning.

## [Unreleased]

## [0.6.0] — 2026-09-27

Live-test remediation: fixes for every defect found by running the plugin as a first-time user (F1–F12).

### Added
- `references/target-resolution.md`: one procedure to resolve and confirm the kube-context; `--context <name>` on every cluster command (F3).
- `references/no-remote-fallback.md`: shared handling for no `origin` remote, missing or unauthenticated `gh`, and nothing to push (F12).
- `scripts/render_template.py` (deterministic `{{ KEY }}` renderer for init-repo/bootstrap), `scripts/helm_deps.sh` and `scripts/render_chart.sh` (dependency build and release-name renders without touching the user's Helm repo list or tree), `scripts/list_crds.sh` (one tested CRD-provider scan) (F6, F10, F11).
- `fetch_dashboard.py --out`, `--labels`, `--relabel`: atomic output, rewrite of bare datasource uids, label scan and relabelling of legends and grouping clauses (F5).
- Chart notes for metrics-server and kube-prometheus-stack, a CRD-ownership check and a sync-wave prompt in `/argocd-deploy` (F10).
- Deploy-key path for private GitOps repos in `/argocd-bootstrap` (`ssh-keygen`, Argo CD repo Secret), visibility choice in `/argocd-init-repo` (F6).
- `LICENSE` (MIT) and `.claude-plugin/marketplace.json` so `/plugin marketplace add` works (F12).
- `tests/test_contracts.py`, `tests/test_render_template.py`, `tests/test_helm_scripts.py`, `tests/test_list_crds.py`: contract tests for each fixed behaviour.
- README: Safety model and Limitations sections; a test keeps every command's `argument-hint` in the README.

### Changed
- The plugin is now shell-only: every command and agent works through `git`, `gh`, `helm`, `kubectl`, and (optionally) `argocd`.
- README "Requirements" replaced by a full **Prerequisites** section (environment, per-tool minimums and which commands need them, cluster/accounts, a one-line setup check); adds `ssh-keygen` and the POSIX tools the scripts use.
- `docs/SUPPORT.md`: Argo CD row now `2.6 / argo-cd chart 5.20` (5.0-5.19 ship 2.4/2.5), Helm verified on 3.19, kind/cgroup note, PyYAML and `ssh-keygen` rows (F12).
- `/argocd-add-manifest`: privileged-kind guardrail (cluster-admin, `system:masters` refused), provider-agnostic CRD check, gate off without CRDs (F4).
- `/argocd-review-values`: works on own-app charts, renders with release name and namespace in a temp copy, explicit no-op `--write` handling and PR body (F11).
- `/argocd-doctor` and `argocd-troubleshooting`: healthy and not-found branches, target line, new signatures, wrapper-chart key nesting, explicit `--fix` flow (F8).
- `argocd-onboarder`: consistent guardrails, non-interactive rules, preconditions, fuller hand-off, `helm_deps.sh` instead of `helm repo add` (F9, F11).
- `install.sh` requires an explicit context and prints access hints; committed executable (F6, F7).
- Every push/PR step follows the shared no-remote fallback (F12).

### Fixed
- `/argocd-audit`: root app no longer reported orphaned, unknown environments are rejected, multi-source `revisions[]` are used, unmanaged apps are reported (F1).
- `/argocd-sync`: exits early on a healthy app, checkpoints before triggering, plain sync then force ladder, never pins `revision: HEAD` (F2).
- No command acts on an unconfirmed kube-context; `$ARGOCD_NS` and `$CTX` used consistently (F3).
- `/argocd-add-dashboard`: no 0-byte or unusable output, datasource uids rewritten, legends relabelled to labels the metrics carry, LF line endings, no absolute paths in `__source` (F5).
- `/argocd-init-repo`: no author-derived owner default, explicit visibility, renderer script for templates (F6).
- Bootstrap: broken-pipe noise, missing UI/password hints, unexplained finalizer warning (F7).

### Removed
- The optional Argo CD MCP integration: `.mcp.json.example`, its README section, the "use `mcp__argocd__*` if present" instructions in `argocd-audit`, `argocd-doctor`, `argocd-sync`, and `argocd-onboarder`; `test_plugin_is_shell_only_no_mcp` guards against it returning.

## [0.5.0] — 2026-09-10

### Added
- PR-blocking CI (`ci.yml`): pytest + cluster-free helm smokes on Linux, macOS, Windows; `actionlint`.
- Opt-in `kind` e2e workflow (`e2e.yml`): `argocd_e2e.sh` on dispatch / `e2e` label / push to master.
- `tests/requirements.txt`, `docs/SUPPORT.md` (tool + version matrix), `docs/CONTRIBUTING.md`, this changelog.
- `skills/values-review/reference/chart-notes.md` — chart-specific operational notes split out of the prod-readiness checklist.

### Changed
- `prod-readiness-checklist.md` now holds only the generic dev/prod rubric.
- Every `skills/*/reference/*.md` carries an owner + last-reviewed header.
- Branch protection on `master` requires the CI checks.

## [0.4.0] — prior history (pre-changelog)

Built via PRs #1–#12. Summary:
- **Phase 1:** `/argocd-init-repo`, `/argocd-bootstrap`, `/argocd-add-chart`, `/argocd-deploy`, `/argocd-audit`; the `argocd-onboarder` agent; `argocd-repo-conventions` + `helm-chart-onboarding` skills; the wrapper-chart templates.
- **Phase 2 (partial):** `values-review` / `/argocd-review-values`; `argocd-troubleshooting` / `/argocd-doctor`; `argocd-rollout` / `/argocd-sync` (drive-to-healthy loop); the interaction contract (`references/interaction-style.md`).
- **Extensions:** `argocd-extra-manifests` / `/argocd-add-manifest` (ServiceMonitor/PodMonitor starters + free-text); `argocd-grafana-dashboards` / `/argocd-add-dashboard` (`fetch_dashboard.py` — grafana.com/url/file → normalized JSON).
- Dogfooded end-to-end on a live cluster: Argo CD bootstrap + Airflow, MySQL, Metabase, kube-prometheus-stack, Trino to production-readiness.

[Unreleased]: https://github.com/OmalCooray/argocd-gitops-plugin/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/OmalCooray/argocd-gitops-plugin/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/OmalCooray/argocd-gitops-plugin/releases/tag/v0.5.0
