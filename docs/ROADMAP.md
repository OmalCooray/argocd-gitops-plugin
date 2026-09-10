# Roadmap to 1.0

**Status:** active plan of record
**Baseline:** commit `ef1c8e2` — 10 commands, 1 agent, 8 skills, 8 templates, 1 script; 37 unit tests + 4 smoke scripts; Phase 1 + partial Phase 2 shipped.
**Source:** the CTO assessment (2026-09). Every "must-fix" and "should-fix" from that assessment maps to a milestone below; nothing is dropped.

## How to read this

- Milestones are **cut in order**. Each is a release (`v0.5` → `v1.0`) with a hard gate.
- **Feature milestones** (v0.6 secrets, v0.7 multi-env) each run the full cycle:
  `superpowers:brainstorming` → `superpowers:writing-plans` →
  `superpowers:subagent-driven-development` → **live dogfood on the cluster** →
  `superpowers:finishing-a-development-branch`. They get their own
  `docs/superpowers/specs/` + `docs/superpowers/plans/` pair.
- **Infra / release items** (CI, CHANGELOG, marketplace manifest, quickstart) are
  smaller; they may skip formal brainstorming but still land behind a PR + review.
- A milestone's gate must be **fully** true before the next milestone starts.
- Rough sizing: S ≈ ½–1 day, M ≈ 2–4 days, L ≈ 1–2 weeks. Total ≈ 3–5 focused weeks.

---

## v0.5 — Trustworthy (foundations)

*Make "all green" mean something and make releases traceable. No new plugin features.*

### 0.5.1 — CI pipeline  · S · assessment item #1
- GitHub Actions workflow, triggered on PR and push to `master`.
- Jobs: `python -m pytest`; `helm lint` on every `templates/*.tmpl` rendered with the fixture; the three fast smoke scripts (`helm_smoke.sh`, `extra_manifest_smoke.sh`, `dashboard_smoke.sh`) against network-only Helm (no cluster).
- A separate opt-in job spins a `kind` cluster and runs `argocd_e2e.sh` (allowed to be slow / manually triggered).
- Branch protection on `master`: require the PR job green before merge.
- **Done when:** a PR that breaks any test cannot be merged.

### 0.5.2 — Cross-platform validation + support matrix  · M · assessment item #2
- CI matrix: `ubuntu-latest`, `macos-latest`, `windows-latest` for the pytest + smoke jobs.
- Fix everything that breaks (expect: path handling, LF/CRLF, shell assumptions, `python` stdout encoding — the bug history says this is where it fails).
- Add `docs/SUPPORT.md`: minimum verified versions of `git`, `gh`, `helm`, `kubectl`, `argocd`, `python`, and the Argo CD Helm chart / server (multi-source `$values` needs Argo CD ≥ 2.6 — already documented, consolidate here).
- **Done when:** the pytest + fast-smoke CI matrix is green on Linux, macOS, and Windows.

### 0.5.3 — Release discipline (part 1)  · S · assessment item #5
- `CHANGELOG.md` (Keep a Changelog format), backfilled from the 11 merged PRs into an `[0.4.0]` "Unreleased history" section.
- Bump `.claude-plugin/plugin.json` `version` to `0.5.0`.
- Tag `v0.5.0` on the merge commit. Every subsequent milestone ends with a `CHANGELOG` entry + a tag.
- Add `docs/CONTRIBUTING.md`: the spec→plan→execute→dogfood→PR flow, the interaction-contract rule, "a `templates/` change bumps the wrapper chart version," "no active `.mcp.json`."
- **Done when:** `v0.5.0` is tagged with a CHANGELOG entry; contribution flow is written down.

### 0.5.4 — Documentation ownership  · S · assessment item #9
- Split `skills/values-review/reference/prod-readiness-checklist.md`:
  - keep the generic dev/prod rubric in `prod-readiness-checklist.md`
  - move per-chart specifics (Airflow, MySQL-per-client-auth, exporter notes) to `reference/chart-notes.md`
- Add a one-line "owner + last-reviewed date" header to each `reference/*.md`.
- **Done when:** no single reference file mixes generic rubric with chart-specific trivia.

### v0.5 gate
- [ ] PR-blocking CI, green on Linux + macOS + Windows for pytest + fast smokes.
- [ ] `docs/SUPPORT.md` with a verified tool/version matrix.
- [ ] `CHANGELOG.md` exists; `v0.5.0` tagged.
- [ ] `docs/CONTRIBUTING.md` exists.
- [ ] `prod-readiness-checklist.md` split; reference files have owners.

---

## v0.6 — Secure (secrets convention)

*A GitOps repo the plugin produces must need zero hand-created Secrets. This is the #1 external-adoption blocker.*  · **assessment item #3** · L

### Scope (settle in brainstorming)
- Default mechanism: **External Secrets Operator** (most portable; SOPS and Sealed Secrets as documented alternatives, not built).
- New: a `secrets/` convention in `argocd-repo-conventions` — where the `SecretStore`/`ClusterSecretStore` lives, how an app declares the external secrets it needs, sync-wave ordering (ESO app before the apps that consume its secrets).
- New skill `argocd-secrets` — the convention, the ESO wrapper-chart pattern, the `ExternalSecret` template (a wrapper-chart `templates/` file, gated, following the extra-manifests primitive), backend options (a cluster secret store, a cloud provider, or a bootstrap-only in-cluster `fake`/`kubernetes` backend for local).
- New command `/argocd-add-secret <app> <key>...` (or fold into a broader `/argocd-onboard-secrets`) — scaffold the `ExternalSecret`, wire the values, verify it renders + resolves.
- `/argocd-init-repo` gains an optional "add ESO + a SecretStore" step.
- `values-review` learns to flag a plaintext secret / an `existingSecret` with no backing `ExternalSecret`.
- `argocd-rollout` functional check: the target `Secret` exists and the `ExternalSecret` reports `SecretSynced`.

### Dogfood
Convert one existing `test-k8s-configs` app (candidate: `metabase`, whose DB creds are hand-made) from a `kubectl`-created Secret to an `ExternalSecret` backed by an in-cluster store. Prove the app still comes up Healthy with no manual `kubectl create secret`.

### v0.6 gate
- [ ] `argocd-secrets` skill + `/argocd-add-secret` command, tested + smoke-covered, CI green.
- [ ] `argocd-repo-conventions` documents the `secrets/` convention and sync-wave ordering.
- [ ] `values-review` flags unbacked secret references.
- [ ] Dogfood: a live app runs with its Secret sourced entirely through an `ExternalSecret` — no out-of-band `kubectl`.
- [ ] `CHANGELOG` + `v0.6.0` tag.

---

## v0.7 — Promotable (multi-environment)

*Single-env GitOps is a demo. dev→prod promotion is the point of the pattern.*  · **assessment item #4** · L

### Scope (settle in brainstorming)
- New command `/argocd-add-env <name>` — scaffold `environments/<name>/` (root app, `apps/`, `values/`), apply the release-vs-fast-iteration revision rule (fast-iteration → track branch; release → pinned SHA/tag).
- `templates/application.yaml.tmpl` gains a real `targetRevision` story for release environments (pinned SHA or a `env-*` tag), not just the branch.
- New command `/argocd-promote <app> <from-env> <to-env>` — diff the two envs' `values/<app>.yaml`, generate the target-env-adjusted change (or bump the target env's `targetRevision`), open a PR. Never a blind copy.
- `CODEOWNERS` enforcement: `/argocd-init-repo` and `/argocd-add-env` write `CODEOWNERS` rules for `environments/<prod>/**`; document the branch-protection setup.
- `argocd-repo-conventions` — the dev/prod revision-tracking model gets exercised and any gaps fixed.
- `argocd-audit` learns to report per-environment (declared vs live for each env).

### Dogfood
Add a `prod` environment to `test-k8s-configs`. Deploy `airflow` (or a lighter app) to `dev`, then `/argocd-promote airflow dev prod` — a real PR bumping a pinned revision, merged, synced, `airflow` Healthy in `prod` on the live cluster with a subset of dev's config.

### v0.7 gate
- [ ] `/argocd-add-env` + `/argocd-promote` commands, tested + smoke-covered, CI green.
- [ ] Release-env `targetRevision` pinning works in the Application template.
- [ ] `CODEOWNERS` for prod paths is generated; branch-protection setup documented.
- [ ] `/argocd-audit` reports per-environment.
- [ ] Dogfood: a live `dev` → `prod` promotion via `/argocd-promote`, prod app Healthy.
- [ ] `CHANGELOG` + `v0.7.0` tag.

---

## v0.8 — Hardened (recovery, agent, evals)

*Prove the failure paths and the autonomous path.*

### 0.8.1 — GitOps-repo rollback  · M · assessment item #8
- New `/argocd-rollback <app> [--to <revision>]` (or `/argocd-doctor --fix` extended):
  identify the last Synced+Healthy revision for an app, generate the git change to
  return to it (revert the offending PR, or move the pinned `targetRevision` back),
  open a PR, and — with explicit confirmation — expedite it.
- `argocd-troubleshooting` gains a "prod is broken, get it back" recipe distinct
  from "diagnose the root cause."
- **Done when:** a deliberately broken app is recovered to its last-good state via
  `/argocd-rollback` on the live cluster.

### 0.8.2 — Exercise the agent  · M · assessment item #8
- Run `argocd-onboarder` end-to-end, unattended, for a brand-new app on the live
  cluster (research chart → scaffold → deploy → drive to Healthy → PR).
- Fix whatever breaks: the fix-cycle cap, the checkpoint-before-push behavior in a
  non-interactive context, the hand-off to `/argocd-sync`.
- **Done when:** `argocd-onboarder` completes a full onboard with no human step
  except merge approval, and the app is Healthy + functional.

### 0.8.3 — Skill-triggering evals  · M · assessment item #7
- Use `skill-creator`'s eval tooling to build a small eval set: for a corpus of
  realistic prompts, does Claude load the right skill (and not the wrong one)?
- Record a baseline; fix any skill description below threshold; wire the eval into
  CI as a non-blocking report.
- **Done when:** a skill-triggering eval baseline exists, is reproducible, and no
  skill scores below the agreed threshold.

### 0.8.4 — Pin external couplings  · S
- `.mcp.json.example`: pin `argocd-mcp` to an exact version; add a note that the
  "use `mcp__argocd__*` if present" skill instructions are validated against that
  version (or mark them unvalidated).
- `fetch_dashboard.py`: document the grafana.com endpoint dependency in the module
  docstring; confirm the URL/local-path fallbacks are the supported path if it
  changes.

### v0.8 gate
- [ ] `/argocd-rollback` proven on a broken live app.
- [ ] `argocd-onboarder` proven unattended end-to-end.
- [ ] Skill-triggering eval baseline recorded; in CI as a report.
- [ ] External couplings (MCP, grafana.com) pinned / documented.
- [ ] `CHANGELOG` + `v0.8.0` tag.

---

## v0.9 — Documented & Releasable

*Someone who isn't the author can install it and succeed.*  · **assessment item #6** + item #5 (part 2)

### 0.9.1 — Curated example repo  · M
- A `examples/` directory (or a separate `argocd-gitops-example` repo) produced by
  `/argocd-init-repo` and populated with 2–3 clean apps — **not** the
  Docker-Desktop-workaround-laden `test-k8s-configs`.
- CI job: from the example, run `init-repo → bootstrap → add-chart → deploy →
  sync` against a `kind` cluster and assert an app reaches Healthy.
- **Done when:** the example repo is CI-verified end-to-end on `kind`.

### 0.9.2 — 10-minute quickstart  · S
- `docs/QUICKSTART.md`: the shortest real path from zero to one app on Argo CD,
  every command copy-pasteable, verified by the 0.9.1 CI job.
- README trimmed to point at it.
- **Done when:** the quickstart's commands are exactly what CI runs.

### 0.9.3 — Marketplace + install  · S · assessment item #5
- Marketplace manifest (`.claude-plugin/marketplace.json` or the repo's
  `marketplace` entry) so `/plugin marketplace add` + `/plugin install` work.
- `docs/INSTALL.md`: install from the marketplace, and from a local checkout for
  development.
- Verify `/plugin install` from a clean machine / container.
- **Done when:** a clean machine can `/plugin install argocd-gitops-plugin` and
  run `/argocd-init-repo`.

### 0.9.4 — Full regression dogfood  · M
- From scratch: `/argocd-init-repo` a fresh repo, bootstrap a fresh `kind`
  cluster, bring up the 5-app reference stack (with secrets via ESO and a `prod`
  env), using only plugin commands + merge approvals.
- File every rough edge; fix or ticket each.
- **Done when:** the fresh-repo → 5-app-stack run completes with no undocumented
  manual step.

### v0.9 gate
- [ ] CI-verified example repo + quickstart.
- [ ] Marketplace manifest; `/plugin install` verified from clean.
- [ ] Full regression dogfood from a fresh repo passes.
- [ ] `CHANGELOG` + `v0.9.0` tag.

---

## v1.0 — Definition of Done

Cut `v1.0.0` when **every** box is checked:

**Trust**
- [ ] PR-blocking CI green on Linux + macOS + Windows (pytest + fast smokes); `kind` e2e job available.
- [ ] `docs/SUPPORT.md` tool/version matrix, verified in CI.
- [ ] Full test suite + all four smoke scripts green; every command still references the interaction contract (enforced by test).

**Features (the "real GitOps" bar)**
- [ ] **Secrets:** no GitOps repo the plugin produces requires a hand-created Secret; ESO convention documented and dogfooded.
- [ ] **Multi-env:** `/argocd-add-env` + `/argocd-promote` proven with a live dev→prod promotion; release-env revision pinning + CODEOWNERS enforcement in place.
- [ ] **Rollback:** a proven "get prod back to last-good" workflow.
- [ ] **Agent:** `argocd-onboarder` proven unattended end-to-end.

**Quality**
- [ ] Skill-triggering eval baseline recorded; no skill below threshold.
- [ ] External couplings (Argo CD MCP, grafana.com API) pinned or explicitly marked unvalidated.
- [ ] Reference docs split by concern, each with an owner + review date.

**Adoption**
- [ ] CI-verified curated example repo.
- [ ] `docs/QUICKSTART.md` — exactly the commands CI runs — completed by at least one person who is not the author on their own machine.
- [ ] Marketplace manifest; `/plugin install` verified from a clean machine.
- [ ] `docs/INSTALL.md`, `docs/CONTRIBUTING.md`, `CHANGELOG.md` current.

**Hygiene**
- [ ] Zero known Sev-1 / Sev-2 defects.
- [ ] Every "must-fix" and "should-fix" from the CTO assessment closed (or explicitly deferred with a v1.x ticket and rationale).
- [ ] `v1.0.0` tagged; CHANGELOG `[1.0.0]` section written.

---

## Explicitly out of scope for 1.0 (candidate v1.x)

- Flux support (the skills are Argo-CD-specific by design).
- Own-application chart authoring (`frontend`/`backend` charts you develop) — the registry-chart source type.
- `argocd-exporters` / `/argocd-observe` — the full "provision an exporter → ServiceMonitor → dashboard" orchestrator (spec #2b). The primitives (`/argocd-add-manifest`, `/argocd-add-dashboard`) ship in 1.0; the orchestrator is a v1.x convenience.
- Alertmanager routing / receiver management.
- Cost/quota policy, OPA/Kyverno policy scaffolding.

---

## Sequencing summary

| Milestone | Theme | Size | Blocks |
|---|---|---|---|
| v0.5 | CI, cross-platform, release hygiene, doc split | ~1 wk | everything after (CI gates all PRs) |
| v0.6 | Secrets convention (ESO) | ~1 wk | v0.9 example repo (built with secrets done right) |
| v0.7 | Multi-env: add-env, promote, prod pinning | ~1–1.5 wk | v0.9 regression dogfood |
| v0.8 | Rollback, agent hardening, skill evals | ~1 wk | — |
| v0.9 | Example repo, quickstart, marketplace, regression | ~3–4 days | v1.0 |
| **v1.0** | **DoD checklist all green** | tag only | — |

Do them in order. Don't start a milestone until the previous gate is fully green.
