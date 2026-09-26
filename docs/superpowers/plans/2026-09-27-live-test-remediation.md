# Live-Test Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix every defect and missing feature found by testing the plugin as a first-time user — offline (all 10 commands + the onboarder agent) and live (kind cluster + real GitHub repo, 2026-09-26/27) — so a stranger can install it and succeed.

**Architecture:** The plugin is markdown instructions plus small Python scripts, so fixes are (a) precise rewrites of command/skill text, (b) two new shared references/scripts (`references/target-resolution.md`, `scripts/render_template.py`), (c) real code + unit tests for `fetch_dashboard.py`, and (d) a new `tests/test_contracts.py` that turns each fixed behaviour into a regression test. Every task ends with a test the old text would have failed.

**Tech Stack:** Markdown command/skill files, Python 3.10+ (stdlib + PyYAML), pytest, Bash, `helm`/`kubectl`/`gh`/`git`, kind (verification only).

**Out of scope (separate specs, already on `docs/ROADMAP.md`):** secrets convention (v0.6), `/argocd-add-env` + `/argocd-promote` (v0.7), `/argocd-rollback` + skill evals (v0.8), quickstart/example repo (v0.9). This plan only touches those where a live-test finding forces it.

---

## Findings register (evidence for every task below)

Severity: **B** = blocker for public release, **M** = major, **m** = minor. Source: **L** = reproduced live on kind, **O** = offline literal-follow, **V** = verified directly against plugin source.

| ID | Sev | Src | Finding |
|----|-----|-----|---------|
| F1 | B | L,V | `/argocd-audit` builds the declared set from `apps/*.yaml` only, so the root app (`root-<env>`, declared in `root.yaml`) is reported "Orphaned — should be pruned". An unknown env (`audit nonexistent-env`) reports every live app as orphaned ("0 declared, 2 live, 2 drifted"). `status.sync.revision` is `null` for multi-source apps (SHAs are in `status.sync.revisions[]`); `<argocd-ns>` is never defined; summary hides missing apps; nothing detects apps that were hand-`kubectl apply`-ed with no root. |
| F2 | B | L | `/argocd-sync` on an already Synced/Healthy app runs the rollout skill's force patch (`operation.sync.revision: "HEAD"`, `apply.force: true`) with no checkpoint and no "nothing to do" exit. Live evidence: `status.history` gained id 1 (`initiatedBy=argocd-rollout`), Deployment `generation` 1→2, Deployment and Service `resourceVersion` changed. `revision: HEAD` also ignores `spec.sources`/pinned SHAs. No fail-fast when no cluster is reachable. |
| F3 | B | L,V | No command prints or confirms which kube-context it will act on. `argocd-deploy` step 7, `argocd-add-chart` step 5 and the onboarder run `kubectl apply --dry-run=client`, which contacts the current context. `install.sh` defaults to the current context; Helm's NOTES commands omit `--context`. On a machine with a real cluster this is a foot-gun. |
| F4 | B | L,V | `/argocd-add-manifest` has no guardrail: a free-text "ClusterRoleBinding cluster-admin for `system:authenticated`" was authored and enabled. Its CRD check dead-ends ("report it and stop") and hardcodes the owning app name `kube-prometheus-stack`; the starter's values default `enabled: true`, so any env without the CRD fails to sync. |
| F5 | B | L,V | `/argocd-add-dashboard`: (a) a failed fetch leaves a 0-byte file that still lints and renders into the ConfigMap; (b) `fetch_dashboard.py` leaves template variables bound to a bare-string datasource uid (`"beok7uikyo1kwf"`) that does not exist — live `POST /api/ds/query` returned `Data source not found`; (c) dashboard 10826 uses `kubernetes_namespace`/`kubernetes_pod_name` but Prometheus has `namespace`/`pod` — panels show "No data", and step 5 only checks metric names; (d) CRLF written on Windows; (e) local-file `__source` embeds an absolute path. |
| F6 | B | L,V | `/argocd-init-repo`: default GitHub owner is the author (`OmalCooray`, `commands/argocd-init-repo.md:19`); `gh repo create` hard-codes `--private` and never asks; default branch `master`; "render templates" names no mechanism (`tests/render.py` is never mentioned); `install.sh` is committed `100644` on Windows; generated README says `./bootstrap/install.sh <ENV_NAME>` but `$1` is a kube-context. **A private repo (the default) cannot be pulled by Argo CD — no credential path exists anywhere.** |
| F7 | m | L | Bootstrap: `helm search … \| head -5` prints a broken-pipe error on Git Bash; `install.sh` ends with "argocd app list" (CLI not installed) and never re-prints the UI port-forward / initial-admin-password commands; the harmless finalizer warning on `root.yaml` is unexplained. |
| F8 | M | L,O | `/argocd-doctor` / `argocd-troubleshooting`: no healthy-app branch, no not-found handling, never names the inspected context/namespace; no signature row for an immutable selector change, for "Running but not Ready with x509 in logs", or for an app that crash-loops with a non-zero exit; example fix key `image.tag` is wrong for wrapper charts (must be `<chart>.image.tag` — live fix used `podinfo.image.tag`); `--fix` says "open a PR the way /argocd-deploy does" (does not fit a values fix); log tail dumps 40 lines of `--help`; no note that an app stays `Progressing` (not `Degraded`) for the 600 s progress deadline. |
| F9 | M | L,O | `argocd-onboarder`: rules contradict themselves ("Never deploy to a live cluster" vs step 11 merge + sync; env can literally be named `live`); three human checkpoints but no non-interactive rule; namespace rule "stop and ask" has no default (`argocd-deploy` defaults to `<app>`; metrics-server belongs in `kube-system`); never says to read `.claude/CLAUDE.md`; no clean-tree / already-exists / no-remote / no-`gh` preconditions; no hand-off template; `helm-chart-onboarding` says `helm repo add` (global side effect). |
| F10 | M | L | Chart-specific knowledge missing: **metrics-server** on kind/Docker Desktop stays `0/1` (`x509: cannot validate certificate … doesn't contain any IP SANs`; needs `--kubelet-insecure-tls` in the env overlay); **kube-prometheus-stack**: default `serviceMonitorSelectorNilUsesHelmValues: true` means the plugin's ServiceMonitor is never scraped (target missing until 3 `*SelectorNilUsesHelmValues: false` keys are set); bundled CRDs collide with a separate `prometheus-operator-crds` app (`crds.enabled: false`); Grafana folder annotations need `sidecar.dashboards.folderAnnotation`/`provider.foldersFromFilesStructure`; random admin Secret re-renders on reinstall. `argocd-deploy` never prompts for a sync-wave when the app provides CRDs. |
| F11 | m | L,O | `/argocd-review-values`: assumes a wrapper chart (fails on an own-app chart such as `lakehouse-ui`, no `dependencies`); renders without release name/namespace (`release-name-<app>`); `helm dependency build` on the user's tree rewrites `Chart.lock`; `--write --profile dev` yields nothing and dead-ends at `git commit`; PDB only renders when `replicaCount > 1` (not mentioned). |
| F12 | m | L,V | No fallback text for "no git remote / `gh` unauthenticated" at push/PR steps in most commands; `docs/SUPPORT.md` says Argo CD chart "5.x" (first chart shipping Argo CD 2.6 is **5.20.0**); kind's default node image (1.37) fails on cgroup-v1 Docker Desktop (1.34 works); no `LICENSE` file; README install needs `.claude-plugin/marketplace.json` which does not exist. |

Live evidence artifacts: `C:\claude\plugin-newuser-test\` (sandbox), `github.com/OmalCooray/argocd-plugin-livetest` (17 PRs), kind cluster `plugin-livetest`.

---

## File structure

**Create**
- `references/target-resolution.md` — the shared "resolve + confirm the target cluster" procedure (F3).
- `scripts/render_template.py` — deterministic `{{ KEY }}` renderer used by init-repo/bootstrap/add-chart/deploy (F6).
- `references/no-remote-fallback.md` — shared text for "no remote / no gh" at PR steps (F12).
- `tests/test_contracts.py` — regression tests for every behaviour fixed here.
- `tests/test_render_template.py`
- `tests/fixtures/raw-dashboard-bare-uid.json`
- `LICENSE`, `.claude-plugin/marketplace.json`

**Modify** (all under the plugin root): `commands/argocd-{audit,sync,doctor,add-manifest,add-dashboard,init-repo,bootstrap,deploy,add-chart,review-values}.md`, `agents/argocd-onboarder.md`, `skills/argocd-rollout/SKILL.md`, `skills/argocd-troubleshooting/SKILL.md`, `skills/helm-chart-onboarding/SKILL.md`, `skills/values-review/reference/chart-notes.md`, `skills/argocd-grafana-dashboards/scripts/fetch_dashboard.py`, `templates/install.sh.tmpl`, `templates/gitops-README.md.tmpl`, `references/interaction-style.md`, `docs/SUPPORT.md`, `README.md`, `CHANGELOG.md`, `.claude-plugin/plugin.json`, `tests/test_fetch_dashboard.py`, `tests/test_templates.py` (+ its golden files).

**Work on branch** `fix/live-test-remediation` cut from `chore/drop-mcp-cli-only` (which already removed MCP). Run `python -m pytest -q` after every task; it must stay green.

---

### Task 1: Target-resolution reference + contract test scaffold (F3)

**Files:**
- Create: `references/target-resolution.md`, `tests/test_contracts.py`
- Modify: `references/interaction-style.md`

- [ ] **Step 1: Write the failing test scaffold**

Create `tests/test_contracts.py`:

```python
"""Regression tests: each fixed live-test defect stays fixed."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Commands/agents that contact a cluster or Argo CD and so must resolve the target first.
CLUSTER_COMPONENTS = [
    "commands/argocd-bootstrap.md",
    "commands/argocd-audit.md",
    "commands/argocd-doctor.md",
    "commands/argocd-sync.md",
    "commands/argocd-deploy.md",
    "commands/argocd-add-chart.md",
    "commands/argocd-add-manifest.md",
    "commands/argocd-add-dashboard.md",
    "commands/argocd-review-values.md",
    "agents/argocd-onboarder.md",
]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def fenced_lines(text):
    """Yield lines that are inside ``` fences."""
    inside = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            inside = not inside
            continue
        if inside:
            yield line


def test_target_resolution_reference_exists_and_is_complete():
    t = read("references/target-resolution.md")
    for needle in ("Target: context=", "--context", "cluster-info", "Proceed?", ".claude/CLAUDE.md"):
        assert needle in t, needle


def test_every_cluster_component_resolves_the_target_first():
    for rel in CLUSTER_COMPONENTS:
        assert "target-resolution.md" in read(rel), f"{rel} must reference target-resolution.md"


def test_no_bare_kubectl_in_fenced_examples():
    allowed = re.compile(r"kubectl\s+(config\s|version\s+--client)")
    for rel in CLUSTER_COMPONENTS + [
        "skills/argocd-rollout/SKILL.md",
        "skills/argocd-troubleshooting/SKILL.md",
    ]:
        for line in fenced_lines(read(rel)):
            if re.search(r"\bkubectl\s", line) and "--context" not in line and not allowed.search(line):
                raise AssertionError(f"{rel}: kubectl without --context: {line.strip()}")
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_contracts.py -q`
Expected: 3 failures (reference missing; components don't reference it; bare `kubectl` lines exist).

- [ ] **Step 3: Create `references/target-resolution.md`**

````markdown
# Resolve the target cluster (run this first in every cluster-touching command)

`kubectl` and `helm` act on whatever kube-context is *current*. On a machine that
also has a production cluster that is a silent foot-gun, so resolve and confirm
the target before the first cluster command.

1. Read `.claude/CLAUDE.md` in the GitOps repo: `Argo CD namespace` → `ARGOCD_NS`,
   `GitOps repo URL` → `REPO_URL`. (Never assume `argocd`.)
2. Choose the kube-context `CTX`: the value of `--context <name>` if the user gave
   one, otherwise the output of `kubectl config current-context` (read-only).
3. Print exactly one line: `Target: context=<CTX>  argocd-ns=<ARGOCD_NS>  repo=<REPO_URL>`.
4. If the user did **not** name a context, checkpoint (one line, wait for yes):
   `> About to act on kube-context "<CTX>" (your current context). Proceed?`
5. Probe reachability once: `kubectl --context "<CTX>" cluster-info --request-timeout=5s`.
   On failure print ONE plain line — `Cluster "<CTX>" is not reachable: start it or pass --context <name>` — and stop
   (or switch to the command's offline mode if it has one). Do not paste the raw
   multi-line connection error.
6. Every later cluster command carries `--context "<CTX>"`; `helm install|upgrade|list`
   carry `--kube-context "<CTX>"`. Local-only helm (`template|lint|show|dependency|search|repo`)
   needs neither. Never `kubectl config use-context`.
````

- [ ] **Step 4: Add the rule to `references/interaction-style.md`**

Under the "Checkpoint before (ask, one line, wait for yes)" list, append the bullet:

```markdown
- acting on a cluster whose kube-context the user did not name — run `${CLAUDE_PLUGIN_ROOT}/references/target-resolution.md` first and print the `Target:` line.
```

- [ ] **Step 5: Codemod the fenced `kubectl` examples**

Run this one-off script from the plugin root (it only touches fenced code lines that start with or pipe into `kubectl`, skipping `kubectl config …`/`kubectl version --client`), then review `git diff --stat`:

```python
import pathlib, re
files = [p for d in ("commands", "agents", "skills") for p in pathlib.Path(d).rglob("*.md")]
skip = re.compile(r"kubectl\s+(config\s|version\s+--client|--context)")
for p in files:
    out, inside, changed = [], False, False
    for line in p.read_text(encoding="utf-8").splitlines(keepends=True):
        if line.strip().startswith("```"):
            inside = not inside
        elif inside and re.search(r"(^|\|\s*|&&\s*)kubectl\s", line) and not skip.search(line):
            new = re.sub(r"\bkubectl\s", 'kubectl --context "$CTX" ', line, count=1)
            changed |= new != line
            line = new
        out.append(line)
    if changed:
        p.write_text("".join(out), encoding="utf-8", newline="")
        print("rewrote", p)
```

Then in each of the 10 components in `CLUSTER_COMPONENTS`, add as the first item under `## Preconditions` (or the first numbered step for the agent):

```markdown
0. **Resolve the target:** follow `${CLAUDE_PLUGIN_ROOT}/references/target-resolution.md`; use its `CTX` and `ARGOCD_NS` in every command below. Accept an optional `--context <name>` argument.
```

and append ` [--context <name>]` to each command's `argument-hint`. Replace every literal `<argocd-ns>` in those files with `$ARGOCD_NS`.

- [ ] **Step 6: Run tests**

Run: `python -m pytest -q`
Expected: all pass (including the 3 new tests). Fix any remaining bare `kubectl` fenced line the test reports.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "fix: resolve and print the target kube-context before any cluster command (F3)"
```

---

### Task 2: `/argocd-sync` — no-op exit, checkpoint, safe trigger, fail-fast (F2)

**Files:**
- Modify: `commands/argocd-sync.md`, `skills/argocd-rollout/SKILL.md`
- Test: `tests/test_contracts.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_contracts.py`:

```python
def test_sync_has_noop_exit_checkpoint_and_no_head_force():
    sync = read("commands/argocd-sync.md")
    roll = read("skills/argocd-rollout/SKILL.md")
    assert "nothing to do" in sync.lower()
    assert "About to trigger a sync" in sync
    assert "cluster-info" in read("references/target-resolution.md")
    assert '"revision":"HEAD"' not in roll and '"revision": "HEAD"' not in roll
    assert "refresh=hard" in roll                     # refresh is the default trigger
    assert "force" in roll and "second checkpoint" in roll.lower()
```

- [ ] **Step 2: Run — expect FAIL**, then edit.

- [ ] **Step 3: Rewrite `commands/argocd-sync.md` Steps 2–3** (currently lines 31–36) to:

```markdown
2. Read the app's live state once:
   `kubectl --context "$CTX" -n "$ARGOCD_NS" get application <app> -o json` — capture destination namespace,
   `spec.sources[]` (or `spec.source`), `status.sync.status`, `status.health.status`,
   `status.sync.revisions[]` (multi-source; `status.sync.revision` is null there) and `status.operationState`.
   If the Application does not exist yet, refresh its parent first: annotate `root-<env>` with
   `argocd.argoproj.io/refresh=hard`, then re-read (allow one 30 s wait).
3. **Nothing-to-do exit.** If it is `Synced` + `Healthy`, has no running operation, and
   every `status.sync.revisions[]` (or `revision`) equals the tracked branch's HEAD
   (`git ls-remote <repo-url> <targetRevision>`), print
   `<app>: already Synced/Healthy at <sha> — nothing to do` and jump to step 5 (functional check). Do **not** trigger anything.
4. Checkpoint: `> About to trigger a sync of <app> on "$CTX". Proceed?` Then run the rollout loop:
   trigger (refresh first) → bounded watch (stated ceiling, **12 minutes total wall-clock across all cycles**) →
   on stall, troubleshoot → fix as a git change → PR (checkpoint) → merge (checkpoint) →
   clear any deadlocked op → re-sync. Cap the fix cycles at 4.
```

and renumber the old steps 4–5 to 5–6.

- [ ] **Step 4: Replace the trigger section in `skills/argocd-rollout/SKILL.md`** (lines ~36–44: the `refresh=hard` snippet and the "To force a sync explicitly" patch) with:

````markdown
Default trigger — a hard refresh (harmless; starts no operation on an app that is already in sync):

```bash
kubectl --context "$CTX" -n "$ARGOCD_NS" annotate application <app> argocd.argoproj.io/refresh=hard --overwrite
```

Automated apps (`syncPolicy.automated`) converge on their own after a refresh. Only when the app is
`OutOfSync` with automated sync **disabled**, or an earlier sync **Failed**, force one — behind a
**second checkpoint** (`> About to force-sync <app>: this re-applies every resource. Proceed?`). Omit
`revision`/`revisions` so Argo CD uses the app's own `targetRevision`s (never `HEAD`: that ignores
`spec.sources` and a pinned SHA):

```bash
kubectl --context "$CTX" -n "$ARGOCD_NS" patch application <app> --type merge -p \
  '{"operation":{"initiatedBy":{"username":"argocd-rollout"},"sync":{"syncStrategy":{"apply":{"force":true}}}}}'
```
````

Also change the watch-loop guidance in step 2 to: "run at most 4 probes (~80 s) per tool call so no call exceeds the 2-minute tool timeout; repeat calls up to the 12-minute ceiling".

- [ ] **Step 5: Run tests** — `python -m pytest -q` → PASS.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "fix(sync): exit early on a healthy app, checkpoint before triggering, never force HEAD (F2)"
```

---

### Task 3: `/argocd-audit` — root app, env validation, revisions, summary, unmanaged apps (F1)

**Files:**
- Modify: `commands/argocd-audit.md`
- Test: `tests/test_contracts.py`

- [ ] **Step 1: Failing test**

```python
def test_audit_covers_root_env_validation_and_multisource():
    a = read("commands/argocd-audit.md")
    for needle in ("environments/<env>/root.yaml", "not found; available environments",
                   "status.sync.revisions", "spec.sources", "missing", "orphaned",
                   "Managed by", "top-level array"):
        assert needle in a, needle
```

- [ ] **Step 2: Replace the `## Steps` section (lines 25–42) of `commands/argocd-audit.md`** with:

```markdown
## Steps

0. **Validate the environment.** If `$1` is given and `environments/$1/` does not exist, print
   `environment "$1" not found; available environments: <ls environments/>` and stop. (Never audit an empty declared set.)
1. Build the **declared set** per environment: every `environments/<env>/apps/*.yaml` (`metadata.name`,
   each `spec.sources[]`/`spec.source` `targetRevision` + `path`) **plus the root app** declared in
   `environments/<env>/root.yaml` (mark it `role=root`). The root app is *expected* to be live and is
   never "orphaned".
2. Build the **live set** from `kubectl --context "$CTX" -n "$ARGOCD_NS" get applications -o json`
   (accept both shapes: the `kubectl` List with `items[]`, and `argocd app list -o json`, a top-level array). Per app:
   name, `spec.sources[]` (or `spec.source`), `status.sync.status`, `status.health.status`,
   **`status.sync.revisions[]`** (multi-source apps; `status.sync.revision` is null for them — use it only for single-source apps),
   and the `argocd.argoproj.io/tracking-id` annotation prefix.
3. Compare revisions: for each source whose `targetRevision` is a branch, resolve its HEAD with
   `git ls-remote <repo-url> <branch>` and compare to the matching `status.sync.revisions[i]`; report a mismatch as
   "behind HEAD". Compare `spec.sources[].targetRevision`/`path` against the repo's manifest, source by source.
4. Report these tables (omit an empty one, but always print the summary):
   - **Missing in cluster** — declared but not live. If the root app is also missing, the cause is
     "root app never applied — run `/argocd-bootstrap`"; otherwise "root app has not synced yet — refresh `root-<env>`".
   - **Orphaned in cluster** — live, not declared, and not the root app.
   - **Managed by** — for every live app, who manages it: the tracking-id prefix (e.g. `root-live`), or
     `kubectl apply (no root app)` when it has a `kubectl.kubernetes.io/last-applied-configuration` annotation and its
     tracking-id names no live app. Apps not managed by the env's root app are **unmanaged by GitOps** — say so.
   - **Drift / unhealthy** — `OutOfSync`, `Degraded`, `Missing`, behind HEAD, or a source differs from the repo.
5. For each row give the one-line likely cause and the corrective action ("merge PR #NN", "refresh root-<env>",
   "delete `apps/<x>.yaml`", "run `/argocd-bootstrap`"). Never run `argocd app sync` for an app that is missing.
6. Print: `<n> declared (+root), <m> live, <a> missing, <b> orphaned, <c> drifted, <d> unhealthy, <u> unmanaged`,
   or `No drift: everything declared is live, in sync and healthy.` when all zero.
```

- [ ] **Step 3: Run tests, commit**

```bash
python -m pytest -q && git add -A && git commit -m "fix(audit): count the root app, validate the env, use revisions[], report unmanaged apps (F1)"
```

---

### Task 4: `/argocd-add-manifest` — privileged-kind guardrail, CRD check, gate default (F4)

**Files:**
- Modify: `commands/argocd-add-manifest.md`, `skills/argocd-extra-manifests/SKILL.md`
- Test: `tests/test_contracts.py`

- [ ] **Step 1: Failing test**

```python
def test_add_manifest_has_guardrail_and_crd_path():
    m = read("commands/argocd-add-manifest.md")
    s = read("skills/argocd-extra-manifests/SKILL.md")
    for needle in ("system:authenticated", "refuse", "enabled: false",
                   "servicemonitors.monitoring.coreos.com", "prometheus-operator-crds", "sync-wave"):
        assert needle in m, needle
    assert "Privileged" in s
```

- [ ] **Step 2: Replace step 4's free-text bullet and step 6 in `commands/argocd-add-manifest.md`.**

Free-text bullet (line 49–50) becomes:

```markdown
   - free-text kind: first apply the **privileged-kind guardrail**, then author
     `charts/<app>/templates/<slug>.yaml` from the `argocd-extra-manifests` checklist (gated, no subchart `_helpers`).
     A kind is *privileged* if it is a Role/RoleBinding/ClusterRole/ClusterRoleBinding, grants `*` verbs or resources,
     binds `cluster-admin`, `system:authenticated`, `system:unauthenticated`, `system:anonymous` or `system:masters`,
     is a Validating/MutatingWebhookConfiguration or a CRD, or runs `privileged: true` / `hostPath` / `hostNetwork`.
     For a privileged kind: (1) print one line saying exactly what it grants and to whom; (2) default its values gate to
     `enabled: false`; (3) **refuse outright, with no override,** any binding of `cluster-admin` or `*`/`*` to
     `system:authenticated`, `system:unauthenticated` or `system:anonymous`; (4) checkpoint `> This grants <X> to <Y>. Proceed?`
     before committing.
```

Step 6 becomes:

```markdown
6. CRD check: if the kind needs a CRD (ServiceMonitor → `servicemonitors.monitoring.coreos.com`, PodMonitor →
   `podmonitors.monitoring.coreos.com`), it is *provided* if EITHER some app in `environments/<env>/apps/` ships it
   (`helm template` its wrapper chart and look for `kind: CustomResourceDefinition` with that name) OR the reachable
   cluster has it (`kubectl --context "$CTX" get crd <name>`). Any provider is fine — do not require a specific app name.
   If none: do not stop silently. Report it and offer the light path: `/argocd-add-chart prometheus-operator-crds`
   (repo `https://prometheus-community.github.io/helm-charts`) then `/argocd-deploy prometheus-operator-crds <env>` with
   `argocd.argoproj.io/sync-wave: "-1"` (CRDs only, ~10 objects), or `kube-prometheus-stack` for the full stack. Stop
   before committing until a provider exists; its sync-wave must be lower than `<app>`'s.
```

Also change step 5's stanza so the gate ships **off** when the CRD provider is not yet in the target env: `serviceMonitor: {enabled: <true only if step 6 found a provider in this env>, …}`.

- [ ] **Step 3: Add to `skills/argocd-extra-manifests/SKILL.md`** (under the kinds list, where "extra RBAC" is offered) a `## Privileged kinds` section reproducing the definition and the four rules verbatim from Step 2.

- [ ] **Step 4: Run tests, commit**

```bash
python -m pytest -q && git add -A && git commit -m "fix(add-manifest): privileged-kind guardrail, provider-agnostic CRD check, gate off without CRDs (F4)"
```

---

### Task 5: `fetch_dashboard.py` — atomic write, datasource, labels, LF (F5)

**Files:**
- Modify: `skills/argocd-grafana-dashboards/scripts/fetch_dashboard.py`, `commands/argocd-add-dashboard.md`, `skills/argocd-grafana-dashboards/SKILL.md`
- Create: `tests/fixtures/raw-dashboard-bare-uid.json`
- Test: `tests/test_fetch_dashboard.py`

- [ ] **Step 1: Create the fixture** `tests/fixtures/raw-dashboard-bare-uid.json`:

```json
{
  "title": "Bare UID Dashboard",
  "__inputs": [{"name": "DS_PROMETHEUS", "type": "datasource", "pluginId": "prometheus"}],
  "templating": {"list": [
    {"name": "namespace", "type": "query", "datasource": "beok7uikyo1kwf",
     "query": "label_values(go_goroutines, kubernetes_namespace)"},
    {"name": "pod", "type": "query", "datasource": "beok7uikyo1kwf",
     "definition": "label_values(go_goroutines{kubernetes_namespace=\"$namespace\"}, kubernetes_pod_name)"}
  ]},
  "panels": [
    {"title": "Goroutines", "datasource": "${DS_PROMETHEUS}",
     "targets": [{"expr": "sum(go_goroutines{kubernetes_namespace=~\"$namespace\", kubernetes_pod_name=~\"$pod\"})"}]}
  ]
}
```

- [ ] **Step 2: Write failing tests** — append to `tests/test_fetch_dashboard.py`:

```python
BARE = ROOT / "tests/fixtures/raw-dashboard-bare-uid.json"


def test_bare_string_datasource_on_template_variables_is_rewritten():
    out = json.loads(_run(BARE).stdout)
    by_name = {v["name"]: v for v in out["templating"]["list"]}
    assert by_name["namespace"]["datasource"] == "${datasource}"
    assert by_name["pod"]["datasource"] == "${datasource}"


def test_out_flag_writes_atomically_and_leaves_nothing_on_failure(tmp_path):
    good = tmp_path / "good.json"
    p = subprocess.run([sys.executable, str(SCRIPT), str(FIXTURE), "--out", str(good)],
                       capture_output=True, text=True)
    assert p.returncode == 0 and json.loads(good.read_text(encoding="utf-8"))["title"]
    assert b"\r\n" not in good.read_bytes()            # LF only, even on Windows
    bad = tmp_path / "bad.json"
    p = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path / "missing.json"), "--out", str(bad)],
                       capture_output=True, text=True)
    assert p.returncode == 1 and not bad.exists()       # no zero-byte poison file
    assert not list(tmp_path.glob("*.tmp"))


def test_local_source_records_basename_not_absolute_path():
    out = json.loads(_run(FIXTURE).stdout)
    assert str(ROOT) not in out["__source"] and "raw-dashboard.json" in out["__source"]


def test_labels_flag_lists_label_names_used_in_queries():
    p = subprocess.run([sys.executable, str(SCRIPT), str(BARE), "--labels"], capture_output=True, text=True)
    assert p.returncode == 0
    assert {"kubernetes_namespace", "kubernetes_pod_name"} <= set(json.loads(p.stdout))


def test_relabel_rewrites_queries_and_variable_definitions():
    p = subprocess.run([sys.executable, str(SCRIPT), str(BARE),
                        "--relabel", "kubernetes_namespace=namespace",
                        "--relabel", "kubernetes_pod_name=pod"], capture_output=True, text=True)
    assert p.returncode == 0
    text = p.stdout
    assert "kubernetes_namespace" not in text and "kubernetes_pod_name" not in text
    assert 'namespace=~\\"$namespace\\"' in text
```

- [ ] **Step 3: Run — expect FAIL.** `python -m pytest tests/test_fetch_dashboard.py -q`

- [ ] **Step 4: Implement in `fetch_dashboard.py`.** Add near the top-level helpers:

```python
import os
import tempfile

_BUILTIN_DS = {"-- mixed --", "-- grafana --", "-- dashboard --", "mixed", "grafana", "dashboard"}
_LABEL_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\s*(?:=~|!~|!=|=)\s*"')
_BRACES_RE = re.compile(r"\{([^{}]*)\}")
_LABEL_VALUES_RE = re.compile(r"label_values\([^,)]*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)")
_QUERY_KEYS = ("expr", "query", "definition")


def _non_prom_input_names(dash: dict) -> set[str]:
    return {i["name"] for i in dash.get("__inputs", [])
            if i.get("type") == "datasource" and i.get("pluginId") != "prometheus" and i.get("name")}


def _iter_queries(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key in _QUERY_KEYS and isinstance(value, str):
                yield node, key, value
            else:
                yield from _iter_queries(value)
    elif isinstance(node, list):
        for value in node:
            yield from _iter_queries(value)


def used_labels(dash: dict) -> set[str]:
    labels: set[str] = set()
    for _, _, expr in _iter_queries(dash):
        for body in _BRACES_RE.findall(expr):
            labels.update(_LABEL_RE.findall(body))
        labels.update(_LABEL_VALUES_RE.findall(expr))
    return labels


def relabel(dash: dict, mapping: dict[str, str]) -> int:
    count = 0
    for node, key, expr in _iter_queries(dash):
        new = expr
        for old, repl in mapping.items():
            new = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(old)}(?![A-Za-z0-9_])", repl, new)
        if new != expr:
            node[key] = new
            count += 1
    return count
```

In `normalize`, after the `walk(dash)` call and before the `rewrites == 0` check, add:

```python
    other = _non_prom_input_names(dash)
    for var in tlist:
        ds = var.get("datasource") if isinstance(var, dict) else None
        if (var.get("type") == "query" if isinstance(var, dict) else False) and isinstance(ds, str) \
                and not ds.startswith("${") and ds.lower() not in _BUILTIN_DS and ds not in other:
            var["datasource"] = "${%s}" % DS_VAR       # bare uid/name this Grafana will not have
            rewrites += 1
```

Change the `__source` line to record a basename for local files:

```python
    label = os.path.basename(origin) if not origin.startswith(("http://", "https://", "grafana.com")) else origin
    dash["__source"] = f"{label}, fetched {date.today().isoformat()}"
```

(If `load()` returns `origin` as `grafana.com:<id>` for ids, keep it verbatim — check `load()` and adjust the prefix test to its actual origin strings.)

Replace `main` with:

```python
def _parse(argv):
    src, out, labels_only, mapping, i = None, None, False, {}, 1
    while i < len(argv):
        a = argv[i]
        if a == "--out":
            out, i = argv[i + 1], i + 2
        elif a == "--labels":
            labels_only, i = True, i + 1
        elif a == "--relabel":
            old, _, new = argv[i + 1].partition("=")
            mapping[old], i = new, i + 2
        elif src is None and not a.startswith("--"):
            src, i = a, i + 1
        else:
            raise IndexError(a)
    if src is None:
        raise IndexError("source")
    return src, out, labels_only, mapping


def main(argv: list[str]) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    except (AttributeError, ValueError):
        pass
    try:
        src, out, labels_only, mapping = _parse(argv)
    except IndexError:
        sys.stderr.write(__doc__)
        return 2
    try:
        dash, origin = load(src)
        dash = normalize(dash, origin)
        if mapping:
            relabel(dash, mapping)
    except (urllib.error.URLError, OSError, json.JSONDecodeError, KeyError) as exc:
        sys.stderr.write(f"error: could not load dashboard: {exc}\n")
        return 1
    except DashboardError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1
    if labels_only:
        json.dump(sorted(used_labels(dash)), sys.stdout)
        sys.stdout.write("\n")
        return 0
    text = json.dumps(dash, indent=2, ensure_ascii=False) + "\n"
    if out is None:
        sys.stdout.write(text)
        return 0
    directory = os.path.dirname(os.path.abspath(out))
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, out)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return 0
```

Update the module docstring's usage line to `fetch_dashboard.py <source> [--out PATH] [--relabel OLD=NEW]... [--labels]`.

- [ ] **Step 5: Run — expect PASS.** `python -m pytest tests/test_fetch_dashboard.py -q`

- [ ] **Step 6: Update `commands/argocd-add-dashboard.md`.** Replace step 4's code block with:

```bash
python ${CLAUDE_PLUGIN_ROOT}/skills/argocd-grafana-dashboards/scripts/fetch_dashboard.py "<source>" \
  --out charts/<app>/grafana-dashboards/<slug>.json
```

(The script writes atomically: a failed fetch leaves **no** file.) Replace step 5 with:

```markdown
5. **Sanity-check metrics and labels.**
   a. Metric names: grep the JSON for the metrics it queries; sample a few against
      `/api/v1/label/__name__/values`. If most are absent, warn it is likely the wrong dashboard.
   b. Labels: `python …/fetch_dashboard.py "<source>" --labels` prints the label names the dashboard's queries use.
      Fetch the real ones with `/api/v1/labels` (and confirm on one series: `/api/v1/series?match[]=up{job=~".*<app>.*"}`).
      For every dashboard label that Prometheus does not have, warn and offer to rewrite. Common scrape-label renames:
      `kubernetes_namespace→namespace`, `kubernetes_pod_name→pod`, `kubernetes_name→service`, `kubernetes_node→node`.
      Re-run step 4 adding `--relabel OLD=NEW` for each accepted rename. With no cluster, say the label check was skipped.
```

Add to the step 10 folder note: also `grafana.sidecar.dashboards.searchNamespace: ALL` (see Task 9).

- [ ] **Step 7: Commit**

```bash
python -m pytest -q && git add -A && git commit -m "fix(dashboard): atomic --out, rewrite bare datasource uids, --labels/--relabel, LF, basename source (F5)"
```

---

### Task 6: Template renderer, `init-repo` defaults, README/install.sh, private-repo access (F6, F7)

**Files:**
- Create: `scripts/render_template.py`, `tests/test_render_template.py`
- Modify: `commands/argocd-init-repo.md`, `commands/argocd-bootstrap.md`, `commands/argocd-add-chart.md`, `commands/argocd-deploy.md`, `templates/install.sh.tmpl`, `templates/gitops-README.md.tmpl`, `tests/test_templates.py` (+ golden files)
- Test: `tests/test_contracts.py`

- [ ] **Step 1: Failing tests** — `tests/test_render_template.py`:

```python
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/render_template.py"


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def test_renders_all_keys_lf_utf8_no_bom(tmp_path):
    tpl = tmp_path / "a.tmpl"; tpl.write_text("x: {{ A }}\ny: {{ B }}\n", encoding="utf-8")
    out = tmp_path / "a.yaml"
    p = run(str(tpl), str(out), "A=1", "B=two")
    assert p.returncode == 0, p.stderr
    raw = out.read_bytes()
    assert raw == b"x: 1\ny: two\n" and not raw.startswith(b"\xef\xbb\xbf")


def test_missing_value_is_an_error_and_writes_nothing(tmp_path):
    tpl = tmp_path / "a.tmpl"; tpl.write_text("{{ A }} {{ B }}", encoding="utf-8")
    out = tmp_path / "a.out"
    p = run(str(tpl), str(out), "A=1")
    assert p.returncode == 1 and "B" in p.stderr and not out.exists()


def test_unused_value_is_an_error(tmp_path):
    tpl = tmp_path / "a.tmpl"; tpl.write_text("{{ A }}", encoding="utf-8")
    p = run(str(tpl), str(tmp_path / "o"), "A=1", "TYPO=2")
    assert p.returncode == 1 and "TYPO" in p.stderr
```

Append to `tests/test_contracts.py`:

```python
def test_init_repo_no_author_defaults_and_asks_visibility():
    t = read("commands/argocd-init-repo.md")
    assert "OmalCooray" not in t
    assert "gh api user" in t and "init.defaultBranch" in t and "Visibility" in t
    assert "render_template.py" in t and "--chmod=+x" in t
    assert "--private" not in t.replace("--$VISIBILITY", "")


def test_install_script_requires_an_explicit_context_and_prints_access_hints():
    s = read("templates/install.sh.tmpl")
    assert '${1:?' in s and "port-forward" in s and "initial-admin-secret" in s
    assert "install.sh <kube-context>" in read("templates/gitops-README.md.tmpl")


def test_bootstrap_handles_private_repos_with_a_deploy_key():
    b = read("commands/argocd-bootstrap.md")
    for needle in ("gh repo view", "ssh-keygen", "deploy-key add", "argocd.argoproj.io/secret-type=repository", "sshPrivateKey"):
        assert needle in b, needle
    assert "head -5" not in b
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Create `scripts/render_template.py`:**

```python
#!/usr/bin/env python3
"""Render a {{ KEY }} template.

Usage: render_template.py <template> <output> KEY=VALUE [KEY=VALUE ...]

Every {{ KEY }} must be given a value and every KEY=VALUE must be used, else exit 1
and write nothing. Output is UTF-8, LF newlines, no BOM (safe on Windows).
"""
import os
import re
import sys
import tempfile

PLACEHOLDER = re.compile(r"\{\{\s*([A-Z0-9_]+)\s*\}\}")


def main(argv):
    if len(argv) < 3:
        sys.stderr.write(__doc__)
        return 2
    tpl, out, pairs = argv[1], argv[2], argv[3:]
    values = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep:
            sys.stderr.write(f"error: expected KEY=VALUE, got {pair!r}\n")
            return 2
        values[key] = value
    with open(tpl, encoding="utf-8", newline="") as fh:
        text = fh.read().replace("\r\n", "\n")
    needed = set(PLACEHOLDER.findall(text))
    missing, unused = needed - values.keys(), values.keys() - needed
    if missing or unused:
        if missing:
            sys.stderr.write(f"error: no value for: {', '.join(sorted(missing))}\n")
        if unused:
            sys.stderr.write(f"error: unused values: {', '.join(sorted(unused))}\n")
        return 1
    rendered = PLACEHOLDER.sub(lambda m: values[m.group(1)], text)
    directory = os.path.dirname(os.path.abspath(out))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(rendered)
    os.replace(tmp, out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 4: Fix the templates.** In `templates/gitops-README.md.tmpl` change the setup block to:

````markdown
## First-time setup

```bash
kubectl config get-contexts                 # pick the cluster to install Argo CD into
./bootstrap/install.sh <kube-context>       # e.g. ./bootstrap/install.sh docker-desktop
```
````

In `templates/install.sh.tmpl` replace `CONTEXT="${1:-$(kubectl config current-context)}"` with:

```bash
CONTEXT="${1:?usage: install.sh <kube-context>   (list them: kubectl config get-contexts)}"
```

and replace the final `echo ">> Done. Watch sync status with:  argocd app list   (or the Argo CD UI)"` with:

```bash
cat <<EOF
>> Done. Argo CD is installed in ${CONTEXT} (namespace ${ARGOCD_NAMESPACE}).
   Open the UI:        kubectl --context ${CONTEXT} -n ${ARGOCD_NAMESPACE} port-forward svc/argo-cd-argocd-server 8080:443   # https://localhost:8080
   Admin password:     kubectl --context ${CONTEXT} -n ${ARGOCD_NAMESPACE} get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d
   Watch sync status:  kubectl --context ${CONTEXT} -n ${ARGOCD_NAMESPACE} get applications
   (The 'resources-finalizer' warning above is Argo CD's documented finalizer name; it is harmless.)
EOF
```

Regenerate the golden files under `tests/` that render `install.sh.tmpl` and `gitops-README.md.tmpl` (run the rendering helper in `tests/test_templates.py` and copy its output over the matching golden files), then re-run `tests/test_templates.py`.

- [ ] **Step 5: Rewrite `commands/argocd-init-repo.md` inputs and steps.**

Replace the input list (lines 15–22) with:

```markdown
- Ask the user (AskUserQuestion) for anything not derivable:
  1. Target directory (default: a sibling of the CWD).
  2. GitHub owner/org — default from `gh api user --jq .login` (if `gh` is unauthenticated, ask; no default).
  3. Argo CD namespace (default: `argocd`).
  4. Destination cluster API (default: `https://kubernetes.default.svc`).
  5. Default branch — default from `git config --get init.defaultBranch`, else `main`.
  6. Visibility (`private` | `public`; default `private`). **Private repos need Argo CD credentials — `/argocd-bootstrap` sets them up with a read-only deploy key.** Public repos are pulled anonymously.
  7. Create + push the GitHub repo now? (yes/no; needs `gh` authenticated.)
```

Replace step 3 (render) with a rendering block that calls the script, e.g.:

```bash
R="python ${CLAUDE_PLUGIN_ROOT}/scripts/render_template.py"
$R ${CLAUDE_PLUGIN_ROOT}/templates/root.yaml.tmpl environments/<env>/root.yaml \
   ENV_NAME=<env> ARGOCD_NAMESPACE=<ns> GITOPS_REPO_URL=<url> DEFAULT_BRANCH=<branch> DEST_SERVER=<server>
$R ${CLAUDE_PLUGIN_ROOT}/templates/gitops-README.md.tmpl README.md GITOPS_REPO_NAME=<name> ENV_NAME=<env>
$R ${CLAUDE_PLUGIN_ROOT}/templates/CODEOWNERS.tmpl CODEOWNERS ENV_NAME=<env> GITHUB_OWNER=<owner>
```

with the `gitops-CLAUDE.md.tmpl` call listing **exactly** the variables that template contains (open the template and list each `{{ KEY }}` — do this in the edit, do not leave "all repo-fact vars"). `GITOPS_REPO_URL` is `https://github.com/<owner>/<name>` for public repos and `git@github.com:<owner>/<name>.git` for private repos (deploy-key access needs the SSH form).

In step 6 replace `--private` by `--$VISIBILITY` (`--private` or `--public`) and add: if `public`, print `This repository will be PUBLIC` and require the checkpoint. In step 5 (after the commit), no chmod is needed; in `argocd-bootstrap` step 5 add `git update-index --chmod=+x bootstrap/install.sh` after `git add`. Step 6's "if `gh` is missing … print the manual commands" must print them: `git remote add origin <url> && git push -u origin <branch>` and the `gh repo create` line.

- [ ] **Step 6: Edit `commands/argocd-bootstrap.md`.**
  - Step 2: replace `helm search repo argo/argo-cd --versions | head -5` with `helm search repo argo/argo-cd --versions -o json --max-col-width 0` and "take the first entry whose `version` has no `-` suffix; record `version` (chart) in `install.sh`".
  - Add a **private-repo step** before applying the root app: run `gh repo view <owner>/<name> --json visibility -q .visibility`; if `PRIVATE`, checkpoint `> This repo is private: Argo CD needs a read-only deploy key. Create one? (the private key stays in a cluster Secret only)` then:

```bash
KEY="$(mktemp -d)/argocd-deploy-key"
ssh-keygen -t ed25519 -N "" -C "argocd-<name>" -f "$KEY"
gh repo deploy-key add "$KEY.pub" --title "argocd-readonly-<ctx>" -R <owner>/<name>          # read-only by default
kubectl --context "$CTX" -n "$ARGOCD_NS" create secret generic repo-<name> \
  --from-literal=type=git --from-literal=url=git@github.com:<owner>/<name>.git \
  --from-file=sshPrivateKey="$KEY"
kubectl --context "$CTX" -n "$ARGOCD_NS" label secret repo-<name> argocd.argoproj.io/secret-type=repository
shred -u "$KEY" 2>/dev/null || rm -f "$KEY"; rm -f "$KEY.pub"
```

  Never print the key. Note `ssh-keygen` (OpenSSH) becomes a prerequisite for private repos.
  - After `install.sh`, print the three access lines (port-forward, admin-password command, `get applications`) if the script's output scrolled past them.
- Add `ssh-keygen` (private repos only) to the README Prerequisites table in Task 11.

- [ ] **Step 7: Point `add-chart`, `deploy` and the onboarder at the renderer.** In each `render …/templates/X.tmpl into …` step, replace with a `python ${CLAUDE_PLUGIN_ROOT}/scripts/render_template.py <tmpl> <out> KEY=VALUE…` call listing that template's variables; read `GITOPS_REPO_URL`, `ARGOCD_NAMESPACE`, `DEST_SERVER`, default branch from `.claude/CLAUDE.md`.

- [ ] **Step 8: Run tests, commit**

```bash
python -m pytest -q && git add -A && git commit -m "fix(init-repo,bootstrap): renderer script, no author defaults, visibility, private-repo deploy key, explicit context (F6, F7)"
```

---

### Task 7: `/argocd-doctor` + troubleshooting skill (F8)

**Files:**
- Modify: `commands/argocd-doctor.md`, `skills/argocd-troubleshooting/SKILL.md`
- Test: `tests/test_contracts.py`

- [ ] **Step 1: Failing test**

```python
def test_doctor_and_troubleshooting_cover_live_findings():
    d = read("commands/argocd-doctor.md")
    s = read("skills/argocd-troubleshooting/SKILL.md")
    for needle in ("healthy — nothing to fix", "not found", "inspected:", "<chart>.image.tag", "Progressing", "--tail=5"):
        assert needle in d + s, needle
    for needle in ("field is immutable", "x509", "Exit Code", "Running but not Ready"):
        assert needle in s, needle
    assert 'image.tag "v0.61.1.x"' not in d
```

- [ ] **Step 2: Edit `commands/argocd-doctor.md`:**
  - Before the current step 2 add: "**Healthy branch.** If `Synced` + `Healthy`, no operation running and no `conditions`, print `<app>  Synced/Healthy — healthy — nothing to fix` and stop (skip the `/argocd-sync` hand-off)."
  - Add: "**Unknown app.** If `kubectl … get application <app>` says NotFound, list the live apps, and check whether `environments/*/apps/<app>.yaml` declares it; if declared but not live say so and point to `/argocd-audit`. Stop."
  - Add to the Output block a first line `inspected: <CTX> / <ARGOCD_NS> → dest ns <ns>` (before `<app> <sync>/<health>`).
  - In the no-arg triage step add: "Also run the audit's missing-app check (`/argocd-audit`) and mention any declared-but-absent app."
  - Fix line 87's example to `` `podinfo.image.tag "6.999.999"` does not exist → set `podinfo.image.tag` `` and add a sentence: "For a wrapper chart every key nests under the dependency name: `<chart>.image.tag`, in `environments/<env>/values/<app>.yaml` (per-env) or `charts/<app>/values.yaml` (all envs). Read `argocd-repo-conventions` to pick."
  - Replace the `--fix` PR instruction with explicit steps: `git switch -c fix/<app>-<slug>` → edit the one values file → `helm template <app> charts/<app> -n <dest-ns> -f environments/<env>/values/<app>.yaml` must render → commit → checkpoint `> About to push fix/<app>-<slug> and open a PR. Proceed?` → push → `gh pr create` (body: root cause, evidence line, the one-line diff). Add `[--fix]` to `argument-hint`.
- [ ] **Step 3: Edit `skills/argocd-troubleshooting/SKILL.md`:** append these rows to the signature table (after the `PostSync` row) and add the notes below it:

```markdown
| Sync fails `Deployment.apps "X" is invalid: spec.selector: … field is immutable` | a values/chart change altered the Deployment's selector labels; K8s forbids it | revert the label change in git; or, if intended, add `Replace=true` to the Application's `syncOptions` in git (one-time) — never delete the workload by hand |
| Pod `Running` but `0/1` Ready, readiness 500, logs show `x509: cannot validate certificate for <ip> because it doesn't contain any IP SANs` (kind / Docker Desktop kubelet certs) | metrics-server (or another kubelet client) cannot verify self-signed kubelet certs on a local cluster | in the **env overlay only**: `metrics-server.args: [--kubelet-insecure-tls]` (see `values-review/reference/chart-notes.md`); never in the shared catalog values |
| Pod `CrashLoopBackOff`, `describe` → `Exit Code` ≠ 0 (2 = bad CLI usage), no init container involved | the app rejects its own flags/config — usually a bad `extraArgs`/`command`/env value | read `kubectl … logs --previous --tail=5` (the error is on the last lines); fix the offending key in values |
```

Notes to add under the table: (1) "**Running but not Ready** does not match the `CrashLoopBackOff`/`ImagePullBackOff` stuck signatures — look at readiness events and `logs --tail=5` for any pod that stays `0/1` for more than ~90 s." (2) "An app with a bad rollout stays `Progressing` — not `Degraded` — until the Deployment's 600 s `progressDeadlineSeconds` expires; pod signatures, not the Argo health colour, are the stuck test." (3) "Use `--tail=5 --previous` for logs; if the tail is a usage/`--help` dump, `grep -m3 -iE 'error|invalid|fatal'` instead."
- [ ] **Step 4: Run tests, commit**

```bash
python -m pytest -q && git add -A && git commit -m "fix(doctor): healthy/not-found branches, target line, new signatures, wrapper key nesting, explicit --fix flow (F8)"
```

---

### Task 8: `argocd-onboarder` agent — cold, non-interactive, consistent (F9)

**Files:**
- Modify: `agents/argocd-onboarder.md`, `skills/helm-chart-onboarding/SKILL.md`
- Test: `tests/test_contracts.py`

- [ ] **Step 1: Failing test**

```python
def test_onboarder_is_cold_runnable_and_self_consistent():
    a = read("agents/argocd-onboarder.md")
    assert "Never deploy to a live cluster" not in a
    for needle in ("no direct `kubectl apply`", "Non-interactive", "default `<app>`", "kube-system",
                   ".claude/CLAUDE.md", "git status --porcelain", "already exists", "no remote",
                   "Hand-off", "NOT done"):
        assert needle in a, needle
    assert "helm repo add" not in read("skills/helm-chart-onboarding/SKILL.md")
```

- [ ] **Step 2: Replace `## Operating rules` in `agents/argocd-onboarder.md`** (lines 15–31) with:

```markdown
## Operating rules

- Follow the interaction contract (`${CLAUDE_PLUGIN_ROOT}/references/interaction-style.md`) and resolve the target first
  (`${CLAUDE_PLUGIN_ROOT}/references/target-resolution.md`); print the `Target:` line. Announce each step, show commands +
  key output, no background jobs, no polling loops.
- Load skills `helm-chart-onboarding`, `argocd-repo-conventions`, `argocd-rollout`, `argocd-troubleshooting`.
- CLI-only: `helm`, `kubectl`, `git`, `gh` through the shell. Render templates with
  `python ${CLAUDE_PLUGIN_ROOT}/scripts/render_template.py`. Read repo facts (`GITOPS_REPO_URL`, Argo CD namespace,
  destination server, default branch) from `.claude/CLAUDE.md`.
- One branch: `onboard/<app>-<env>`. Never commit to the default branch; never force-push.
- **Deployment happens only through git.** No direct `kubectl apply`, `helm install` or `kubectl patch` of workloads.
  Reads, `--dry-run=server`-free checks, the sync trigger/refresh in the rollout skill, and merging the PR are allowed.
  (An environment being *named* `live` or `prod` does not change this; pushing/merging to a `prod` env still needs its checkpoint.)
- **Non-interactive by default.** You cannot ask mid-run. At every "ask/confirm" point: (a) write the question and the
  default you chose in the hand-off, (b) apply the default, (c) except at the two hard stops — the **push/PR checkpoint** and
  the **merge checkpoint** — where you stop and return a draft (PR title/body, exact next command) unless the caller's request
  said `--yes` / "go ahead and merge". Defaults: version = latest stable; destination namespace = default `<app>` **unless** the
  chart's docs/`namespace:` say otherwise (known: metrics-server → `kube-system`; cert-manager → `cert-manager`;
  ingress-nginx → `ingress-nginx`); `targetRevision` per `argocd-repo-conventions`.
- **Preconditions (stop and report if any fails):** CWD is a GitOps repo (`charts/`, `environments/`, `.claude/CLAUDE.md`);
  the requested env exists (`environments/<env>/`); `git status --porcelain` shows no tracked changes (untracked
  `bootstrap/install.sh` is fine); `charts/<app>` and `environments/<env>/apps/<app>.yaml` do not already exist (else say
  "already exists — use `/argocd-review-values` or edit by hand"); branch `onboard/<app>-<env>` does not exist.
  If there is no remote or `gh` is unauthenticated, follow `${CLAUDE_PLUGIN_ROOT}/references/no-remote-fallback.md`.
- If chart repo/version/env are missing from the request, stop and return the single question with the discovery hint
  (ArtifactHub URL for the chart name).
```

Then in the sequence: step 5's `kubectl … --dry-run=client` line is replaced by `python -c "import yaml…"` parse + `helm template <app> charts/<app> -n <ns>`; step 4: "if the chart is known to need a local-cluster override (see `values-review/reference/chart-notes.md`), add it to the **env overlay**, commented `# local clusters only`, not the catalog". Replace the sequence's final step with a **Hand-off** section:

```markdown
## Hand-off (always print this, filled in)

- **Done:** chart <name> <version>; PR <url or "not opened: <reason>">; files changed.
- **NOT done:** not merged / not synced / not verified on a cluster (say which).
- **Questions answered with defaults:** <list>.
- **Next command:** `git push -u origin onboard/<app>-<env> && gh pr create …` (if unpushed), else `/argocd-sync <app> <env>`.
```

Cap: "Fix loops: at most 3 attempts, then stop and report" (replacing the mixed "three attempts / up to 4 fix cycles / re-run until they do").

- [ ] **Step 3:** In `skills/helm-chart-onboarding/SKILL.md` step 2 remove `(after helm repo add)` and use `helm search repo --regexp` on a temp `HELM_REPOSITORY_CONFIG`: `export HELM_REPOSITORY_CONFIG=$(mktemp) HELM_REPOSITORY_CACHE=$(mktemp -d); helm repo add tmp <url>; helm search repo tmp/<chart> --versions -o json` so the user's global Helm repo list is untouched.
- [ ] **Step 4: Run tests, commit**

```bash
python -m pytest -q && git add -A && git commit -m "fix(onboarder): consistent guardrails, non-interactive rules, preconditions, hand-off (F9)"
```

---

### Task 9: Chart-specific knowledge + CRD-provider handling (F10)

**Files:**
- Modify: `skills/values-review/reference/chart-notes.md`, `commands/argocd-add-chart.md`, `commands/argocd-deploy.md`, `skills/helm-chart-onboarding/SKILL.md`
- Test: `tests/test_contracts.py`

- [ ] **Step 1: Failing test**

```python
def test_chart_notes_and_crd_provider_handling():
    n = read("skills/values-review/reference/chart-notes.md")
    for needle in ("metrics-server", "--kubelet-insecure-tls", "serviceMonitorSelectorNilUsesHelmValues",
                   "crds.enabled", "folderAnnotation", "foldersFromFilesStructure", "adminPassword"):
        assert needle in n, needle
    assert "CustomResourceDefinition" in read("commands/argocd-add-chart.md")
    assert "sync-wave" in read("commands/argocd-deploy.md") and "CRD" in read("commands/argocd-deploy.md")
```

- [ ] **Step 2: Append to `skills/values-review/reference/chart-notes.md`** (keep the owner/last-reviewed header current — `owner: plugin maintainers, last reviewed 2026-09-27`):

````markdown
## metrics-server (verified live on kind 1.34, 2026-09-27)

On kind / Docker Desktop the kubelet serving cert has no IP SANs, so the pod stays `0/1` and the APIService
`v1beta1.metrics.k8s.io` reports `Available=False (MissingEndpoints)`. Fix in the **env overlay only**
(`environments/<env>/values/metrics-server.yaml`), commented `# local clusters only — do not copy to prod`:

```yaml
metrics-server:
  args:
    - --kubelet-insecure-tls
```

The chart appends `args` after its defaults. Destination namespace: `kube-system`. Functional check:
`kubectl top nodes` returns data and the APIService is `Available=True`.

## kube-prometheus-stack (verified live 2026-09-27)

Set in `charts/kube-prometheus-stack/values.yaml` (base) when the catalog entry is created, or ServiceMonitors/PodMonitors/rules
from other apps are never scraped (the Prometheus CR's selector defaults to `release: <name>`):

```yaml
kube-prometheus-stack:
  prometheus:
    prometheusSpec:
      serviceMonitorSelectorNilUsesHelmValues: false
      podMonitorSelectorNilUsesHelmValues: false
      ruleSelectorNilUsesHelmValues: false
  grafana:
    sidecar:
      dashboards:
        searchNamespace: ALL
        folderAnnotation: grafana_folder
        provider:
          foldersFromFilesStructure: true
```

- CRDs: the chart bundles its CRDs. If a `prometheus-operator-crds` app is (or will be) in the repo, set
  `kube-prometheus-stack.crds.enabled: false` in the same env, or the two owners fight over the CRDs. Use `ServerSideApply=true`.
- Grafana's admin Secret is randomly generated per render; a re-run of `bootstrap/install.sh` re-renders it and the app goes
  `OutOfSync` for a few minutes. Pin it: `grafana.admin.existingSecret` (out-of-band Secret) or `grafana.adminPassword`
  via an out-of-band Secret — never a plaintext password in git.
- Light demo profile for kind: `alertmanager.enabled: false`, `nodeExporter.enabled: false`, `kubeControllerManager.enabled: false`,
  `kubeScheduler.enabled: false`, `kubeEtcd.enabled: false`, `kubeProxy.enabled: false` (the control-plane scrapes fail on kind).
````

- [ ] **Step 3: `commands/argocd-add-chart.md`** — after the `helm template` verify step add: "**CRD ownership check.** `helm template charts/<app> | grep -c 'kind: CustomResourceDefinition'`; if > 0, list the CRD names and (a) look for another catalog chart that also renders any of them (`for c in charts/*; do helm template "$c" | grep -E 'name: <crd>'`); if found, warn and propose `<chart>.crds.enabled: false` (read `helm show values` for the exact key) on the *consumer* side; (b) tell the user this app is a **CRD provider** so `/argocd-deploy` will ask for a sync-wave." Also: "read `values-review/reference/chart-notes.md` for a section matching the chart and apply its base-values block."
- [ ] **Step 4: `commands/argocd-deploy.md`** — after step 4 add: "**Sync-wave for CRD providers.** If the catalog chart renders `CustomResourceDefinition`s (see add-chart) — or is a known operator/CRD chart (`prometheus-operator-crds`, `cert-manager`, `kube-prometheus-stack`) — ask `> This app provides CRDs. Add sync-wave "-1" so it syncs before apps that use them? (yes/no)` (default yes) and add `argocd.argoproj.io/sync-wave: "-1"` to the Application's `metadata.annotations`. Confirm `ServerSideApply=true` is in `syncOptions` (it is in the template)."
- [ ] **Step 5: Run tests, commit**

```bash
python -m pytest -q && git add -A && git commit -m "feat: chart notes (metrics-server, kube-prometheus-stack), CRD ownership check, sync-wave prompt (F10)"
```

---

### Task 10: `/argocd-review-values` (F11)

**Files:**
- Modify: `commands/argocd-review-values.md`, `skills/values-review/SKILL.md`
- Test: `tests/test_contracts.py`

- [ ] **Step 1: Failing test**

```python
def test_review_values_handles_own_charts_release_names_and_noop_write():
    r = read("commands/argocd-review-values.md")
    for needle in ("own-app chart", "helm template <app>", "-n <dest-ns>", "mktemp -d", "nothing to harden"):
        assert needle in r, needle
    assert "replicaCount > 1" in read("skills/values-review/SKILL.md")
```

- [ ] **Step 2: Edit `commands/argocd-review-values.md`:**
  - Steps 2–3: "If `charts/<app>/Chart.yaml` has **no `dependencies`**, it is an **own-app chart**: skip the upstream lookup, review `charts/<app>/values.yaml` + `templates/` directly, and remember its keys are **top-level** (no dependency-name nesting). Say so in the report."
  - Step 4: render in a temp copy so the user's tree is untouched: `T=$(mktemp -d); cp -r charts/<app> "$T/"; helm dependency build "$T/<app>"; helm template <app> "$T/<app>" -n <dest-ns> -f environments/<env>/values/<app>.yaml` (release name = `<app>`, `-n` = the Application's destination namespace).
  - `--write` step 7: "If the rubric yields no change for the chosen profile, print `nothing to harden for profile <p>`, delete the branch, and stop — do not commit."
  - Add: "Write the PR body yourself: the findings table (blocker/warn/note, key, current → proposed) and the `helm template` diff summary."
- [ ] **Step 3: `skills/values-review/SKILL.md`** — add a note under the rubric's HA row: "A PodDisruptionBudget template usually renders only when `replicaCount > 1`; recommend the replica and PDB changes **together**."
- [ ] **Step 4: Run tests, commit**

```bash
python -m pytest -q && git add -A && git commit -m "fix(review-values): own-app charts, release-name renders, temp-copy build, no-op --write (F11)"
```

---

### Task 11: No-remote fallback, support matrix, license, marketplace, version (F12)

**Files:**
- Create: `references/no-remote-fallback.md`, `LICENSE`, `.claude-plugin/marketplace.json`
- Modify: every command with a push/PR step (`argocd-add-chart`, `argocd-deploy`, `argocd-add-manifest`, `argocd-add-dashboard`, `argocd-review-values`, `argocd-doctor`), `docs/SUPPORT.md`, `README.md`, `CHANGELOG.md`, `.claude-plugin/plugin.json`
- Test: `tests/test_contracts.py`

- [ ] **Step 1: Failing test**

```python
def test_release_hygiene():
    assert (ROOT / "LICENSE").read_text(encoding="utf-8").startswith("MIT License")
    import json
    mk = json.loads(read(".claude-plugin/marketplace.json"))
    assert mk["plugins"][0]["name"] == "argocd-gitops-plugin" and mk["plugins"][0]["source"] == "./"
    assert "5.20" in read("docs/SUPPORT.md") and "1.34" in read("docs/SUPPORT.md")
    for rel in ("commands/argocd-add-chart.md", "commands/argocd-deploy.md", "commands/argocd-add-manifest.md",
                "commands/argocd-add-dashboard.md", "commands/argocd-review-values.md", "commands/argocd-doctor.md"):
        assert "no-remote-fallback.md" in read(rel), rel
    assert "## Limitations" in read("README.md") and "ssh-keygen" in read("README.md")
```

- [ ] **Step 2: Create `references/no-remote-fallback.md`:**

```markdown
# No remote / no `gh`

Before any `git push` or `gh pr create`, run `git remote get-url origin` and `gh auth status` (both read-only).

- **No `origin` remote:** do not attempt the push. Print the branch name, the drafted PR title and body, and the exact
  commands to run once a remote exists (`git remote add origin <url> && git push -u origin <branch>` then `gh pr create`),
  leave the commits on the local branch and stop with status "not pushed: no remote".
- **`gh` missing or not logged in:** push the branch (if a remote exists) and print the PR title/body plus the compare URL
  `<repo-url>/compare/<default-branch>...<branch>?expand=1`; tell the user to open the PR in the browser.
- **Nothing to push** (no commits on the branch): say so and delete the empty branch.
```

Reference it from the push/PR step of each listed command ("…follow `${CLAUDE_PLUGIN_ROOT}/references/no-remote-fallback.md` first").

- [ ] **Step 3: `LICENSE`** — the standard MIT text, `Copyright (c) 2026 Omal Cooray`. **`.claude-plugin/marketplace.json`:**

```json
{
  "name": "argocd-gitops-plugin",
  "owner": { "name": "Omal Cooray", "email": "omalcooray9@gmail.com" },
  "plugins": [
    {
      "name": "argocd-gitops-plugin",
      "source": "./",
      "description": "Scaffold and operate an Argo CD GitOps repo: bootstrap Argo CD, onboard Helm charts into a catalog, deploy apps to environments via app-of-apps, and audit drift.",
      "version": "0.6.0"
    }
  ]
}
```

- [ ] **Step 4: `docs/SUPPORT.md`** — change the Argo CD row to `2.6 / argo-cd chart **5.20** (first chart shipping Argo CD 2.6.0; 5.0–5.19 ship 2.4/2.5)` and add under "Operating systems": "Local test clusters: kind's default node image (Kubernetes 1.37) needs cgroup v2; on Docker Desktop with cgroup v1 use `kindest/node:v1.34.x` (verified 2026-09-27)." Add `ssh-keygen` (private repos) to the tool table.
- [ ] **Step 5: `README.md`** — add `ssh-keygen` (OpenSSH; private repos only) to the Prerequisites table, and a `## Limitations` section: single environment per repo scaffold today (multi-env/promotion planned), secrets are not managed (out-of-band `kubectl create secret`), no rollback command, Argo CD only (no Flux), commands are Bash-based (Git Bash/WSL on Windows). Add `LICENSE` badge line.
- [ ] **Step 6: Release** — set `.claude-plugin/plugin.json` `version` to `0.6.0`; in `CHANGELOG.md` move `[Unreleased]` into a dated `[0.6.0] — 2026-09-27` section listing Tasks 1–11 by finding ID.
- [ ] **Step 7: Run tests, commit**

```bash
python -m pytest -q && git add -A && git commit -m "chore: no-remote fallback, support matrix, LICENSE, marketplace.json, v0.6.0 (F12)"
```

---

### Task 12: Re-verify every finding live (kind cluster `plugin-livetest` is still running)

**Files:** none modified except fixes this task surfaces. Sandbox: `C:\claude\plugin-newuser-test`. **Guardrails identical to the first live run:** every kubectl carries `--context kind-plugin-livetest`; never touch `docker-desktop`; GitHub writes only to `OmalCooray/argocd-plugin-livetest`; delete nothing in the cluster except through git.

- [ ] **Step 1: Contract sweep** — `python -m pytest -q` and `bash tests/smoke/helm_smoke.sh extra_manifest_smoke.sh dashboard_smoke.sh` all pass.
- [ ] **Step 2: Re-run each failing scenario with a fresh emulated-user agent and check the *fixed* behaviour:**

| Finding | Scenario | Pass criterion |
|---|---|---|
| F1 | `/argocd-audit live`, then `/argocd-audit nonexistent-env`, then audit against `docker-desktop` (**read-only, live real cluster**) | root app shown as expected-live; unknown env stops with the available list; multi-source revisions compared via `revisions[]`; docker-desktop's 4 hand-applied apps reported "unmanaged by GitOps (kubectl apply)" and 5 declared apps "missing … root app never applied — run /argocd-bootstrap" |
| F2 | `/argocd-sync podinfo live` on a Healthy app; record `status.history`, Deployment `generation`/`resourceVersion` before/after | prints "already Synced/Healthy … nothing to do"; history and generation **unchanged**; a stalled app still converges via refresh; force path only behind its second checkpoint |
| F3 | run each cluster command with no `--context` | prints `Target:` line + checkpoint; unreachable cluster → one plain line; no bare-kubectl action against another context |
| F4 | free-text "ClusterRoleBinding cluster-admin to system:authenticated"; ServiceMonitor with no CRD provider | refused; CRD check offers `prometheus-operator-crds` + sync-wave |
| F5 | `/argocd-add-dashboard podinfo 10826` and `99999999` | no 0-byte file on failure; template variables use `${datasource}`; label mismatch reported with `--relabel` offer; after relabel the Grafana `/api/ds/query` for `count(go_goroutines{namespace="podinfo"})` returns data |
| F6 | `/argocd-init-repo` with a **private** repo (needs your OK to create a second throwaway repo `argocd-plugin-livetest-private`), then `/argocd-bootstrap` | no `OmalCooray` default; visibility asked; deploy key created; Argo CD pulls the private repo; root app Synced |
| F7 | fresh `bootstrap/install.sh` | requires a context arg; prints UI + password + get-applications lines; `git ls-files -s` shows mode `100755` |
| F8 | crash-loop podinfo (`extraArgs` bad), `/argocd-doctor podinfo --fix`; healthy app; unknown app | correct rows matched; fix at `podinfo.image.tag`/right key; healthy/unknown branches behave |
| F9 | onboarder cold-run for `cert-manager` (default ns) with no answers | completes to a draft PR with every default listed; "NOT done" section present |
| F10 | onboard `metrics-server` on kind | chart-note applied in the overlay up front; `kubectl top nodes` works on first sync |
| F11 | `/argocd-review-values` on an own-app chart; `--write --profile dev` on a hardened app | own-app path taken; "nothing to harden"; no `Chart.lock` change in the user's tree |
| F12 | `--no-remote` clone | fallback text printed, no push attempted |

- [ ] **Step 3:** Record results in `docs/superpowers/specs/2026-09-27-live-test-remediation-results.md` (one table: finding → PASS/FAIL → evidence). Any FAIL becomes a follow-up task in this plan before release.
- [ ] **Step 4: Cleanup (requires user go-ahead):** `kind delete cluster --name plugin-livetest`; `kubectl config use-context docker-desktop`; **delete the public repos `OmalCooray/argocd-plugin-livetest` (and `-private` if created) yourself** — `gh` here has no `delete_repo` scope (`gh auth refresh -s delete_repo` then `gh repo delete`); remove `C:\claude\plugin-newuser-test`.
- [ ] **Step 5: Ship** — push `fix/live-test-remediation`, open the PR against `master` (title `Live-test remediation: v0.6.0`), wait for CI (3 OSes + kind e2e), merge, tag `v0.6.0`, create the GitHub Release from the changelog section.

---

## Self-review

- **Spec coverage:** F1→T3, F2→T2, F3→T1, F4→T4, F5→T5, F6/F7→T6, F8→T7, F9→T8, F10→T9, F11→T10, F12→T11; every row has a live re-verification line in T12.
- **Placeholders:** the only "open the template and list" instruction (T6 Step 5, `gitops-CLAUDE.md.tmpl` variables) is a deliberate read-then-write of a file's own placeholders, and `renderer` errors on any omission, so a missing one fails loudly.
- **Consistency:** `CTX`/`ARGOCD_NS` (T1) are the only names used in T2–T10; `render_template.py` (T6) is the only renderer named; `--out/--labels/--relabel` (T5) match the command text in T5 Step 6; `no-remote-fallback.md` (T11) is referenced by the same filename everywhere.
- **Known risk:** T2 assumes an `operation.sync` without `revision(s)` syncs to each source's `targetRevision` — T12/F2 verifies it live before release; if Argo CD requires `revisions`, T2's patch must list them from `spec.sources[].targetRevision`.
- **Needs your decision before T6/T12-F6:** creating a second, private throwaway GitHub repo to prove the deploy-key path.
