# Changelog

All notable changes to this project. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project follows semantic versioning.

## [Unreleased]

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

[Unreleased]: https://github.com/OmalCooray/argocd-gitops-plugin/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/OmalCooray/argocd-gitops-plugin/releases/tag/v0.5.0
