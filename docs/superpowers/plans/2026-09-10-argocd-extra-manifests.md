# Custom Manifests in Wrapper Charts — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in `/argocd-add-manifest` command + `argocd-extra-manifests` skill to `argocd-gitops-plugin` for placing your own templated manifests (starting with `ServiceMonitor` / `PodMonitor`) in `charts/<app>/templates/` alongside a pinned upstream Helm chart.

**Architecture:** A new skill directory (`SKILL.md` + `references/`) holding the mechanism, conventions, two starter templates, and reference docs. A new command markdown file. Small edits to four existing components + the README. Tests: structural checks on the starters (pure pytest), a helm-render smoke script, and the component-inventory test.

**Tech Stack:** Markdown (skill/command), Helm-templated YAML (starters), Bash + Helm (smoke test), Python 3 + pytest (structural tests). No new runtime dependencies.

**Spec:** `docs/superpowers/specs/2026-09-10-argocd-extra-manifests-design.md`

**Repo:** `C:\claude\argocd-gitops-plugin`, branch `feat/extra-manifests-spec` (the spec is already committed here as `901e7a9` + `ec0ab0a`). Continue on this branch.

**Environment (verified this session):** `git`, `helm` v3.19, `kubectl` v1.32 (context `docker-desktop`, live cluster with the Prometheus-Operator CRDs already installed via the `kube-prometheus-stack` app in `test-k8s-configs`), `python` 3.12, `gh` authenticated. Run pytest as `python -m pytest`.

**Conventions for every task:**
- Work on branch `feat/extra-manifests-spec`. Commit after each task.
- Commit trailer (required):
  ```
  Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
  ```
- LF line endings; the repo's `.gitattributes` normalises.
- All paths relative to `C:\claude\argocd-gitops-plugin`.
- Every command/skill file that references a plugin file uses `${CLAUDE_PLUGIN_ROOT}/...`, never an absolute or home path (a test forbids it).

---

## File Structure

Created / edited by this plan:

```
argocd-gitops-plugin/
├── commands/
│   ├── argocd-add-manifest.md                         # CREATE — the command
│   ├── argocd-add-chart.md                            # EDIT — one line
│   └── argocd-deploy.md                               # EDIT — one line
├── skills/
│   ├── argocd-extra-manifests/
│   │   ├── SKILL.md                                   # CREATE — mechanism + conventions + checklist
│   │   └── references/
│   │       ├── starters/
│   │       │   ├── servicemonitor.yaml                # CREATE — Helm-templated ServiceMonitor
│   │       │   └── podmonitor.yaml                    # CREATE — Helm-templated PodMonitor
│   │       ├── prometheus-operator.md                 # CREATE — label rules, named ports, verification
│   │       └── hooks-and-waves.md                     # CREATE — sync-waves first; hook traps
│   ├── argocd-repo-conventions/SKILL.md               # EDIT — "Custom manifests" section
│   └── argocd-rollout/SKILL.md                        # EDIT — functional-check table row
├── tests/
│   ├── test_plugin_components.py                      # EDIT — add to EXPECTED_*
│   ├── test_starters.py                               # CREATE — structural checks on starters
│   ├── fixtures/starter.vars.json                     # CREATE — fixture values for the smoke test
│   └── smoke/extra_manifest_smoke.sh                  # CREATE — helm render + assert
└── README.md                                          # EDIT — command table + roadmap
```

---

## Task 1: `argocd-extra-manifests` skill — `SKILL.md`

**Files:**
- Create: `skills/argocd-extra-manifests/SKILL.md`

- [ ] **Step 1: Write `skills/argocd-extra-manifests/SKILL.md`**

```markdown
---
name: argocd-extra-manifests
description: Add your own templated Kubernetes manifests (ServiceMonitor, PodMonitor, IngressRoute, NetworkPolicy, extra RBAC, a CronJob…) to a wrapper chart's templates/ directory, alongside a pinned upstream Helm chart, without editing or vendoring the upstream. Load when a public chart lacks a resource your platform needs and you want to add it as a first-class part of the wrapper.
---

# Extra manifests in a wrapper chart

## Mechanism

A wrapper chart (`charts/<app>/`) is itself a real Helm chart. It can carry its
own `templates/` directory. Helm — and Argo CD's repo-server — renders those
templates **alongside** every template from the pinned dependency `.tgz`, into
one manifest stream. You never touch, unpack, or fork the upstream chart; you add
sibling templates to *your* wrapper.

```
charts/<app>/
├── Chart.yaml        # dependency: <upstream> pinned
├── values.yaml       # overrides under <upstream>:  +  your own top-level keys
├── charts/           # git-ignored: the downloaded <upstream>-x.y.z.tgz
└── templates/        # YOUR manifests — one file per kind
    └── servicemonitor.yaml
```

## Conventions

- **One file per resource kind**, kebab-named (`templates/servicemonitor.yaml`).
- **The wrapper's base `values.yaml` MUST set `<chart>.fullnameOverride: <app>`.**
  A parent chart cannot call a subchart's `_helpers.tpl`, so this is how your
  templates reference chart-generated Services / pods / labels — by the
  predictable name `<app>-<component>`. If it is missing, add it (and warn the
  user: it can rename resources on the next sync).
- **Gate every added manifest on a values flag** — `{{- if .Values.serviceMonitor.enabled }}`
  … `{{- end }}` — default sensible (monitors on), overridable per environment
  through the `$values` overlay in `environments/<env>/values/<app>.yaml`.
- **A resource lives with whatever it is about.** App route/monitor →
  `charts/<app>/`. A shared middleware every app uses → the controller's wrapper
  (`charts/traefik/`). Cluster-wide alert rules → `charts/kube-prometheus-stack/`.
- **CRD-exists is a sync-wave concern.** A ServiceMonitor needs the
  Prometheus-Operator CRD (from the `kube-prometheus-stack` app). That app must
  sit at a lower `argocd.argoproj.io/sync-wave` than apps that ship its CRs — not
  in the same folder. See `references/hooks-and-waves.md`.
- **A `templates/` change is a chart change** — bump `charts/<app>/Chart.yaml`
  `version`.

## Template context

Available: `.Values` (including `.Values.<chart>.*`), `.Release.Name`,
`.Release.Namespace`, the wrapper's `.Chart`, `.Capabilities`,
`.Values.global.*`.
**Not available:** the upstream chart's `_helpers.tpl` named templates — never
`{{ include "<upstream>.fullname" . }}`.

## Authoring checklist

1. Confirm `<chart>.fullnameOverride: <app>` is in `charts/<app>/values.yaml`;
   add it if missing.
2. `helm template charts/<app>` once. Read the real Service names, the **named**
   ports (a ServiceMonitor `endpoints[].port` must be a *name*, not a number),
   and the pod/Service labels the new manifest must select.
3. For `servicemonitor` / `podmonitor`: copy the matching
   `references/starters/<kind>.yaml` into `charts/<app>/templates/` verbatim —
   it is fully values-driven — then write the values stanza (step 4). For any
   other kind: author the template against these conventions.
4. Add the gating values stanza to `charts/<app>/values.yaml` as a **top-level**
   key (not nested under the subchart), e.g.:
   ```yaml
   serviceMonitor:
     enabled: true
     selectorLabels: {app.kubernetes.io/name: <app>, app.kubernetes.io/component: <c>}
     port: metrics
     path: /metrics
     interval: 30s
   ```
5. Never `include` a subchart helper (step "Template context").
6. Verify: `helm dependency build charts/<app>` → `helm template charts/<app>`
   renders your manifest. If a cluster with the CRD is reachable:
   `helm template charts/<app> | kubectl apply --dry-run=server -f -`.
7. Bump `charts/<app>/Chart.yaml` `version`.

## References

- `references/prometheus-operator.md` — how the operator selects ServiceMonitors,
  the named-port rule, defaults, and how to confirm a target is actually scraped.
- `references/hooks-and-waves.md` — sync-waves vs Argo CD hooks; the traps.

## When an app exposes no metrics

Many apps (Metabase, a bare MySQL) serve no Prometheus endpoint. `helm template`
shows no named `metrics`/`http-metrics` port and no `/metrics`. A ServiceMonitor
then scrapes nothing. Say so and stop — the app needs an exporter sidecar or the
chart's own metrics option first. Wiring that up is the observability workflow
(`argocd-observability`, separate), not this primitive.
```

- [ ] **Step 2: Verify frontmatter parses**

Run: `python -c "import re,pathlib; t=pathlib.Path('skills/argocd-extra-manifests/SKILL.md').read_text(); m=re.match(r'^---\n(.*?)\n---\n', t, re.DOTALL); assert m and 'name: argocd-extra-manifests' in m.group(1) and 'description:' in m.group(1); print('frontmatter OK')"`
Expected: `frontmatter OK`

- [ ] **Step 3: Commit**

```bash
git add skills/argocd-extra-manifests/SKILL.md
git commit -m "feat: add argocd-extra-manifests skill

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 2: `references/prometheus-operator.md`

**Files:**
- Create: `skills/argocd-extra-manifests/references/prometheus-operator.md`

- [ ] **Step 1: Write the file**

```markdown
# Prometheus Operator — ServiceMonitor / PodMonitor rules

## How the operator picks up a ServiceMonitor

The `Prometheus` CR has `spec.serviceMonitorSelector` and
`spec.serviceMonitorNamespaceSelector`. A `ServiceMonitor` is scraped only if it
matches **both**.

The `kube-prometheus-stack` chart, with these values (set in this plugin's
prod overlay):

```yaml
prometheus:
  prometheusSpec:
    serviceMonitorSelectorNilUsesHelmValues: false
    podMonitorSelectorNilUsesHelmValues: false
    ruleSelectorNilUsesHelmValues: false
```

makes the selectors **empty = match everything, in every namespace**. So a
ServiceMonitor with any labels, in any namespace, is picked up. Good default for
a platform where apps ship their own monitors.

A stricter install (selectors not nil) usually requires the label
`release: <kube-prometheus-stack release name>` on the ServiceMonitor. The
starter templates take `serviceMonitor.labels` so you can add it if needed.

## The named-port rule

`ServiceMonitor.spec.endpoints[].port` and
`PodMonitor.spec.podMetricsEndpoints[].port` are the **name** of a port on the
Service / pod, not a number. If the app's Service exposes
`ports: [{name: metrics, port: 9102}]` you write `port: metrics`. `helm template
charts/<app> | grep -A3 'kind: Service'` shows the names. If a port has no name,
there is nothing to reference — the app or chart must name it first.

## Selector

`ServiceMonitor.spec.selector.matchLabels` selects **Services** (not pods). Use
the labels the chart puts on the Service you want scraped — usually
`app.kubernetes.io/name: <app>` plus `app.kubernetes.io/component: <c>` or the
chart's `app`/`release` labels. `PodMonitor.spec.selector` selects **pods**
directly (use pod labels).

## Endpoint defaults the starters apply

| Field | Default | Notes |
|---|---|---|
| `path` | `/metrics` | override for apps that expose elsewhere |
| `scheme` | `http` | `https` needs `tlsConfig` |
| `interval` | `30s` | |
| `scrapeTimeout` | (unset → Prometheus default) | must be < interval |
| `honorLabels` | false | true only for federation / pushgateway-style sources |

`relabelings` run before the scrape (drop targets, rewrite `__address__`);
`metricRelabelings` run after (drop noisy series). Both are pass-through lists in
the starters.

## Confirming it actually works

After the sync (via `/argocd-sync <app>`):

```bash
# target registered and up:
curl -s 'http://<prometheus>/api/v1/targets?state=active' \
  | jq '.data.activeTargets[] | select(.scrapePool | test("<app>")) | {scrapePool, health}'
# a metric from the app is present:
curl -s 'http://<prometheus>/api/v1/query?query=up{job=~".*<app>.*"}' | jq '.data.result'
```

A `ServiceMonitor` that renders and applies but produces no target usually means:
the selector labels don't match any Service; the port name is wrong; or the
namespaceSelector excludes the app's namespace.
```

- [ ] **Step 2: Commit**

```bash
git add skills/argocd-extra-manifests/references/prometheus-operator.md
git commit -m "docs: prometheus-operator reference for extra-manifests

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 3: `references/hooks-and-waves.md`

**Files:**
- Create: `skills/argocd-extra-manifests/references/hooks-and-waves.md`

- [ ] **Step 1: Write the file**

```markdown
# Sync-waves vs Argo CD hooks

## Reach for sync-waves first

`argocd.argoproj.io/sync-wave: "N"` (a string; lower runs first, default `"0"`,
negatives allowed) orders resources **within one sync**. The resources stay
normal — visible in the tree, health-tracked, pruned normally. This covers almost
every ordering need:

- a CRD (or the operator app that owns it) before the custom resources that use it
- a namespace / Secret / ConfigMap before the workload that mounts it
- a database app before the app that connects to it

For an extra manifest that needs a CRD (ServiceMonitor → Prometheus-Operator),
the controller app just needs a lower wave than the app shipping the CR. Put the
wave on the **Application** (`environments/<env>/apps/<app>.yaml` metadata) or, if
the CR is inside a wrapper chart's `templates/`, it inherits the app's wave —
which is fine as long as the operator app is earlier.

## Use a hook only for a transient lifecycle task

A hook is a resource that runs *as part of* the sync and is not a persistent part
of desired state.

| `argocd.argoproj.io/hook` | Runs | Use for |
|---|---|---|
| `PreSync` | before the main sync | DB schema migration; backup-before-upgrade |
| `Sync` | with the main wave (own sub-wave) | a Job you must apply every sync but want recreated/cleaned (its K8s-mutated selector would otherwise drift `OutOfSync`) |
| `PostSync` | after all resources are Healthy | smoke test; cache warm; deploy notification |
| `SyncFail` | when the sync fails | cleanup / alert |

`argocd.argoproj.io/hook-delete-policy`: `BeforeHookCreation` (default — keeps the
last run so you can read its logs), `HookSucceeded` (delete on success),
`HookFailed`.

## Traps (all seen in this plugin's e2e)

1. **PostSync deadlock.** If the main workloads *wait on* what a PostSync hook
   produces (e.g. init containers that block until a migration Job runs, and the
   migration is a PostSync hook), the workloads never go Healthy → PostSync never
   fires → deadlock. **Rule: a PreSync/Sync hook may unblock the main resources;
   a PostSync hook must only depend on them, never the reverse.**
2. **Helm hooks are translated.** Argo CD maps `helm.sh/hook: pre-install,pre-upgrade`
   → `PreSync` and `post-install,post-upgrade` → `PostSync`. A chart's
   `post-install` migration Job becomes a PostSync hook and can hit trap 1. Fix:
   `<chart>.<job>.useHelmHooks: false` in values (makes it a plain resource) plus
   re-annotating it `argocd.argoproj.io/hook: Sync`,
   `hook-delete-policy: BeforeHookCreation`.
3. **`prune: false` + hooks.** On an app with pruning disabled (e.g. one that
   manages CRDs), leftover hook ServiceAccounts / RBAC show as "requiresPruning"
   noise — harmless but confusing.

## For this plugin's starters

`servicemonitor.yaml` / `podmonitor.yaml` are **plain resources** — no hook
annotation. They only need the Prometheus-Operator CRD to exist first, which is a
sync-wave concern handled by the `kube-prometheus-stack` app being deployed and
at an earlier wave. Hooks enter only if someone adds a *Job* manifest via the
free-text path.
```

- [ ] **Step 2: Commit**

```bash
git add skills/argocd-extra-manifests/references/hooks-and-waves.md
git commit -m "docs: hooks-and-waves reference for extra-manifests

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 4: Starter — `servicemonitor.yaml`

**Files:**
- Create: `skills/argocd-extra-manifests/references/starters/servicemonitor.yaml`

- [ ] **Step 1: Write the file exactly**

```yaml
{{- /*
ServiceMonitor for {{ .Chart.Name }} — added by /argocd-add-manifest.
Verified against monitoring.coreos.com/v1 (Prometheus Operator 0.7x–0.9x).

Requires: the ServiceMonitor CRD, installed by the `kube-prometheus-stack` app.
That app must be deployed to this environment and at an earlier sync-wave.

Values (charts/<app>/values.yaml, TOP-LEVEL key `serviceMonitor:`):
  enabled            bool   — gate (default here: rendered only when true)
  name               string — ServiceMonitor name (default: the chart name)
  namespace          string — where to create it (default: the app's namespace)
  labels             map    — extra labels (e.g. release: <kps-release> for a strict install)
  selectorLabels     map    — REQUIRED — labels of the Service(s) to scrape
  namespaceSelector  list   — namespaces to look in (default: same namespace)
  port               string — REQUIRED — the NAMED port on the Service (not a number)
  path               string — default /metrics
  scheme             string — default http
  interval           string — default 30s
  scrapeTimeout      string — optional (must be < interval)
  honorLabels        bool   — default false
  relabelings        list   — optional, pass-through
  metricRelabelings  list   — optional, pass-through
*/ -}}
{{- if .Values.serviceMonitor.enabled }}
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: {{ .Values.serviceMonitor.name | default .Chart.Name }}
  {{- with .Values.serviceMonitor.namespace }}
  namespace: {{ . }}
  {{- end }}
  labels:
    app.kubernetes.io/name: {{ .Chart.Name }}
    app.kubernetes.io/managed-by: argocd-gitops-plugin
    {{- with .Values.serviceMonitor.labels }}
    {{- toYaml . | nindent 4 }}
    {{- end }}
spec:
  selector:
    matchLabels:
      {{- toYaml (required "serviceMonitor.selectorLabels is required" .Values.serviceMonitor.selectorLabels) | nindent 6 }}
  {{- with .Values.serviceMonitor.namespaceSelector }}
  namespaceSelector:
    matchNames:
      {{- toYaml . | nindent 6 }}
  {{- end }}
  endpoints:
    - port: {{ required "serviceMonitor.port (a NAMED Service port) is required" .Values.serviceMonitor.port }}
      path: {{ .Values.serviceMonitor.path | default "/metrics" }}
      scheme: {{ .Values.serviceMonitor.scheme | default "http" }}
      interval: {{ .Values.serviceMonitor.interval | default "30s" }}
      {{- with .Values.serviceMonitor.scrapeTimeout }}
      scrapeTimeout: {{ . }}
      {{- end }}
      {{- if .Values.serviceMonitor.honorLabels }}
      honorLabels: true
      {{- end }}
      {{- with .Values.serviceMonitor.relabelings }}
      relabelings:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.serviceMonitor.metricRelabelings }}
      metricRelabelings:
        {{- toYaml . | nindent 8 }}
      {{- end }}
{{- end }}
```

- [ ] **Step 2: Verify it is not accidentally valid-YAML-with-no-template (sanity)**

Run: `grep -c '{{' skills/argocd-extra-manifests/references/starters/servicemonitor.yaml`
Expected: a number ≥ 15 (it is a Helm template, must contain `{{` directives).

- [ ] **Step 3: Commit**

```bash
git add skills/argocd-extra-manifests/references/starters/servicemonitor.yaml
git commit -m "feat: servicemonitor starter template

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 5: Starter — `podmonitor.yaml`

**Files:**
- Create: `skills/argocd-extra-manifests/references/starters/podmonitor.yaml`

- [ ] **Step 1: Write the file exactly**

```yaml
{{- /*
PodMonitor for {{ .Chart.Name }} — added by /argocd-add-manifest.
Verified against monitoring.coreos.com/v1 (Prometheus Operator 0.7x–0.9x).

Use a PodMonitor (not a ServiceMonitor) when the pods you want to scrape have no
Service in front of them, or you want to scrape each pod directly.

Requires: the PodMonitor CRD, installed by the `kube-prometheus-stack` app, at
an earlier sync-wave.

Values (charts/<app>/values.yaml, TOP-LEVEL key `podMonitor:`):
  enabled            bool   — gate
  name               string — default: the chart name
  namespace          string — default: the app's namespace
  labels             map    — extra labels
  selectorLabels     map    — REQUIRED — labels of the POD(s) to scrape
  namespaceSelector  list   — default: same namespace
  port               string — REQUIRED — the NAMED container port
  path               string — default /metrics
  scheme             string — default http
  interval           string — default 30s
  scrapeTimeout      string — optional
  honorLabels        bool   — default false
  relabelings        list   — optional
  metricRelabelings  list   — optional
*/ -}}
{{- if .Values.podMonitor.enabled }}
apiVersion: monitoring.coreos.com/v1
kind: PodMonitor
metadata:
  name: {{ .Values.podMonitor.name | default .Chart.Name }}
  {{- with .Values.podMonitor.namespace }}
  namespace: {{ . }}
  {{- end }}
  labels:
    app.kubernetes.io/name: {{ .Chart.Name }}
    app.kubernetes.io/managed-by: argocd-gitops-plugin
    {{- with .Values.podMonitor.labels }}
    {{- toYaml . | nindent 4 }}
    {{- end }}
spec:
  selector:
    matchLabels:
      {{- toYaml (required "podMonitor.selectorLabels is required" .Values.podMonitor.selectorLabels) | nindent 6 }}
  {{- with .Values.podMonitor.namespaceSelector }}
  namespaceSelector:
    matchNames:
      {{- toYaml . | nindent 6 }}
  {{- end }}
  podMetricsEndpoints:
    - port: {{ required "podMonitor.port (a NAMED container port) is required" .Values.podMonitor.port }}
      path: {{ .Values.podMonitor.path | default "/metrics" }}
      scheme: {{ .Values.podMonitor.scheme | default "http" }}
      interval: {{ .Values.podMonitor.interval | default "30s" }}
      {{- with .Values.podMonitor.scrapeTimeout }}
      scrapeTimeout: {{ . }}
      {{- end }}
      {{- if .Values.podMonitor.honorLabels }}
      honorLabels: true
      {{- end }}
      {{- with .Values.podMonitor.relabelings }}
      relabelings:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.podMonitor.metricRelabelings }}
      metricRelabelings:
        {{- toYaml . | nindent 8 }}
      {{- end }}
{{- end }}
```

- [ ] **Step 2: Commit**

```bash
git add skills/argocd-extra-manifests/references/starters/podmonitor.yaml
git commit -m "feat: podmonitor starter template

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 6: `tests/test_starters.py`

The starters are Helm templates, not `{{ VAR }}` templates, so `tests/render.py`
cannot render them. This test does **structural** checks (pytest, no Helm). Real
rendering is covered by the smoke test (Task 8).

**Files:**
- Create: `tests/test_starters.py`

- [ ] **Step 1: Write the test**

```python
"""Structural checks on the extra-manifest starter templates."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
STARTERS = ROOT / "skills/argocd-extra-manifests/references/starters"

EXPECTED = {
    "servicemonitor.yaml": "ServiceMonitor",
    "podmonitor.yaml": "PodMonitor",
}


def test_expected_starters_present():
    files = {p.name for p in STARTERS.glob("*.yaml")}
    assert files == set(EXPECTED), files


def _text(name):
    return (STARTERS / name).read_text(encoding="utf-8")


def test_each_starter_is_gated_on_an_enabled_flag():
    for name in EXPECTED:
        t = _text(name)
        assert re.search(r"\{\{-?\s*if\s+\.Values\.\w+\.enabled\s*\}\}", t), name
        assert t.rstrip().endswith("{{- end }}"), name


def test_each_starter_declares_its_kind_matching_the_filename():
    for name, kind in EXPECTED.items():
        assert re.search(rf"^kind:\s*{kind}\s*$", _text(name), re.MULTILINE), name


def test_no_starter_includes_a_subchart_helper():
    # a parent chart cannot call a subchart's named templates
    for name in EXPECTED:
        assert 'include "' not in _text(name), name


def test_each_starter_uses_a_named_port_not_a_number():
    # the port value is passed straight through from .Values.<x>.port (a name)
    for name in EXPECTED:
        t = _text(name)
        assert re.search(r"port:\s*\{\{\s*required[^}]*\.Values\.\w+\.port", t), name


def test_each_starter_has_a_leading_comment_block():
    for name in EXPECTED:
        assert _text(name).startswith("{{- /*"), name
```

- [ ] **Step 2: Run it**

Run: `python -m pytest tests/test_starters.py -q`
Expected: PASS (6 passed). If a check fails, fix the starter (Task 4/5), not the test — the test encodes the spec's requirements.

- [ ] **Step 3: Commit**

```bash
git add tests/test_starters.py
git commit -m "test: structural checks for starter templates

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 7: Command — `/argocd-add-manifest`

**Files:**
- Create: `commands/argocd-add-manifest.md`

- [ ] **Step 1: Write `commands/argocd-add-manifest.md`**

```markdown
---
name: argocd-add-manifest
description: Add your own templated manifest (ServiceMonitor, PodMonitor, or any kind via free text) to a wrapper chart's templates/ directory, gated on a values flag, verified to render and to be accepted by its CRD, then open a PR. Opt-in only — nothing else adds templates.
argument-hint: "<app> <kind>   (kind: servicemonitor | podmonitor | free text)"
---

Add a custom manifest to `charts/<app>/templates/` alongside the pinned upstream
chart. Nothing about this is automatic — it runs only when invoked.

**Follow the interaction contract:** `${CLAUDE_PLUGIN_ROOT}/references/interaction-style.md`
— announce each step, show commands + key output, checkpoint before `git push` /
the PR, end with a summary.

## Inputs

- `$1` — `<app>`; `charts/<app>/Chart.yaml` must exist.
- `$2..` — `<kind>`: `servicemonitor`, `podmonitor`, or free text for any other
  resource ("a Traefik IngressRoute for the web port").
- `--env <env>` — optional; used to check the CRD's controller app is deployed
  there and to suggest the follow-up sync.

## Preconditions

- CWD is a GitOps repo (`charts/`, `environments/`, `.claude/CLAUDE.md`).
- `helm` available.

## Steps

1. Load skills `argocd-extra-manifests` and `argocd-repo-conventions`. Follow the
   authoring checklist.
2. Branch: `git switch -c add-manifest/<app>-<kind-slug>`.
3. Confirm `charts/<app>/values.yaml` sets `<chart>.fullnameOverride: <app>`.
   If missing, add it and tell the user (it can rename resources on next sync —
   they should review the diff and plan to sync soon after merge).
4. `helm dependency build charts/<app>` then `helm template charts/<app>` once.
   Read the Service names, the **named** ports, and the Service/pod labels the
   new manifest must target.
   - For `servicemonitor` / `podmonitor`: if no Service/pod exposes a **named**
     metrics port and the app serves no `/metrics`, STOP — report that the app
     exposes no scrapeable metrics (needs an exporter or the chart's metrics
     option first; that's the `argocd-observability` workflow, not this command).
5. Scaffold:
   - starter kind: copy
     `${CLAUDE_PLUGIN_ROOT}/skills/argocd-extra-manifests/references/starters/<kind>.yaml`
     → `charts/<app>/templates/<kind>.yaml` verbatim.
   - free-text kind: author `charts/<app>/templates/<slug>.yaml` from the
     `argocd-extra-manifests` checklist (gated, no subchart `_helpers`).
6. Add the gating values stanza to `charts/<app>/values.yaml` as a **top-level**
   key (not nested under the subchart) — for a ServiceMonitor:
   `serviceMonitor: {enabled: true, selectorLabels: {...}, port: <name>, path: /metrics, interval: 30s}`
   with `selectorLabels` / `port` filled from step 4.
7. CRD check: if the kind needs a CRD (ServiceMonitor/PodMonitor → Prometheus
   Operator), verify the owning app (`kube-prometheus-stack`) is in
   `environments/<env>/apps/` and its sync-wave is lower than `<app>`'s. If not,
   report it and stop before committing.
8. Verify:
   ```bash
   helm template charts/<app>            # your manifest renders
   helm template charts/<app> | kubectl apply --dry-run=server -f -   # CRD accepts it (if a cluster is reachable)
   ```
9. Bump `charts/<app>/Chart.yaml` `version`.
10. Checkpoint → commit → push → `gh pr create` (title `Add <kind> to <app>`,
    body: what it selects/scrapes, the values stanza, `helm template … | head`).
11. Suggest `/argocd-sync <app> <env>` to roll it out. For a ServiceMonitor /
    PodMonitor, name the functional check: after sync, the target shows in
    Prometheus `/api/v1/targets` and `up{...}` returns 1.

## Notes

- Opt-in only. `/argocd-add-chart` and `/argocd-deploy` never call this.
- One file per kind. Re-running for the same kind edits the existing file.
- Never `include` a subchart `_helpers` template.
```

- [ ] **Step 2: Verify no hardcoded paths**

Run: `grep -nE '/(Users|home)/[a-z]|C:\\\\Users' commands/argocd-add-manifest.md || echo "no hardcoded paths"`
Expected: `no hardcoded paths`

- [ ] **Step 3: Commit**

```bash
git add commands/argocd-add-manifest.md
git commit -m "feat: add /argocd-add-manifest command

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 8: Smoke test — `tests/smoke/extra_manifest_smoke.sh`

Renders the `servicemonitor` starter inside a real `podinfo` wrapper chart with
`helm` and asserts the output.

**Files:**
- Create: `tests/fixtures/starter.vars.json` — not used by render.py; a small
  values file the smoke test feeds to `helm template` via `--set-json`. Actually
  simpler: the smoke script writes an inline values file. So only:
- Create: `tests/smoke/extra_manifest_smoke.sh`

- [ ] **Step 1: Write `tests/smoke/extra_manifest_smoke.sh`**

```bash
#!/usr/bin/env bash
# Render the servicemonitor starter inside a real podinfo wrapper chart and
# assert the ServiceMonitor comes out correct. Needs helm + network. No cluster.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$ROOT/tests/.out/extra-manifest"
STARTER="$ROOT/skills/argocd-extra-manifests/references/starters/servicemonitor.yaml"
rm -rf "$OUT"; mkdir -p "$OUT/templates"

cat > "$OUT/Chart.yaml" <<'YAML'
apiVersion: v2
name: podinfo
version: 0.1.0
appVersion: "6.9.0"
dependencies:
  - name: podinfo
    version: 6.9.0
    repository: https://stefanprodan.github.io/podinfo
YAML

cat > "$OUT/values.yaml" <<'YAML'
podinfo:
  fullnameOverride: podinfo
serviceMonitor:
  enabled: true
  selectorLabels:
    app.kubernetes.io/name: podinfo
  port: http
  path: /metrics
  interval: 15s
  labels:
    release: kube-prometheus-stack
YAML

cp "$STARTER" "$OUT/templates/servicemonitor.yaml"

helm dependency build "$OUT" >/dev/null
helm template t "$OUT" --show-only templates/servicemonitor.yaml > "$OUT/rendered.yaml"
cat "$OUT/rendered.yaml"
echo "---"
# assertions
grep -q '^kind: ServiceMonitor$' "$OUT/rendered.yaml"                  || { echo "FAIL: not a ServiceMonitor"; exit 1; }
grep -q 'app.kubernetes.io/name: podinfo' "$OUT/rendered.yaml"         || { echo "FAIL: missing name label"; exit 1; }
grep -q 'app.kubernetes.io/managed-by: argocd-gitops-plugin' "$OUT/rendered.yaml" || { echo "FAIL: missing managed-by"; exit 1; }
grep -q 'release: kube-prometheus-stack' "$OUT/rendered.yaml"          || { echo "FAIL: extra label not applied"; exit 1; }
grep -qE '^\s+port: http$' "$OUT/rendered.yaml"                        || { echo "FAIL: named port not http"; exit 1; }
grep -qE '^\s+interval: 15s$' "$OUT/rendered.yaml"                     || { echo "FAIL: interval override lost"; exit 1; }
grep -qE '^\s+path: /metrics$' "$OUT/rendered.yaml"                    || { echo "FAIL: path"; exit 1; }
python -c "import yaml; d=yaml.safe_load(open(r'$OUT/rendered.yaml')); assert d['apiVersion']=='monitoring.coreos.com/v1'; assert d['spec']['selector']['matchLabels']['app.kubernetes.io/name']=='podinfo'; print('yaml parse + shape OK')"

# gate check: disabled -> nothing rendered
DISABLED="$(helm template t "$OUT" --set serviceMonitor.enabled=false --show-only templates/servicemonitor.yaml 2>&1 || true)"
echo "$DISABLED" | grep -q 'ServiceMonitor' && { echo "FAIL: rendered while disabled"; exit 1; } || true

echo "OK: servicemonitor starter renders, overrides apply, gate works"
```

- [ ] **Step 2: `chmod +x` and run it**

Run:
```bash
chmod +x tests/smoke/extra_manifest_smoke.sh
bash tests/smoke/extra_manifest_smoke.sh
```
Expected: ends with `OK: servicemonitor starter renders, overrides apply, gate works`.
If `helm template --show-only` errors that the template produced an empty
document when disabled, that's fine — the `|| true` handles it; the assertion is
that no `ServiceMonitor` kind appears.
If the `required` function aborts the render, a needed value is missing from the
smoke `values.yaml` — add it there, not to the starter.

- [ ] **Step 3: Commit**

```bash
git add tests/smoke/extra_manifest_smoke.sh
git commit -m "test: helm smoke for the servicemonitor starter

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 9: Wire into `test_plugin_components.py`

**Files:**
- Modify: `tests/test_plugin_components.py`

- [ ] **Step 1: Edit the expected sets**

Change:
```python
EXPECTED_COMMANDS = {
    "argocd-bootstrap", "argocd-init-repo", "argocd-add-chart",
    "argocd-deploy", "argocd-audit", "argocd-review-values", "argocd-doctor",
    "argocd-sync",
}
EXPECTED_SKILLS = {
    "argocd-repo-conventions", "helm-chart-onboarding", "values-review",
    "argocd-troubleshooting", "argocd-rollout",
}
```
to add `"argocd-add-manifest"` to `EXPECTED_COMMANDS` and
`"argocd-extra-manifests"` to `EXPECTED_SKILLS`.

- [ ] **Step 2: Run the full suite**

Run: `python -m pytest -q`
Expected: all pass (existing count + `test_starters.py`'s 6).

- [ ] **Step 3: Commit**

```bash
git add tests/test_plugin_components.py
git commit -m "test: expect argocd-add-manifest command and argocd-extra-manifests skill

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 10: Edit `argocd-repo-conventions` skill

**Files:**
- Modify: `skills/argocd-repo-conventions/SKILL.md`

- [ ] **Step 1: Add a "Custom manifests" section**

Find the "## Wrapper chart" section. Immediately after it, add:

```markdown
## Custom manifests

A wrapper chart may carry your own manifests in `charts/<app>/templates/` —
Helm renders them alongside the pinned upstream dependency, so you add resources
the upstream chart lacks (a `ServiceMonitor`, an `IngressRoute`, a
`NetworkPolicy`) without forking it.

- **Mandatory when you do this:** the wrapper's base `values.yaml` sets
  `<chart>.fullnameOverride: <app>`, so upstream-generated names are a
  predictable `<app>-<component>` your templates can target (a parent chart can't
  call a subchart's `_helpers`).
- Every added manifest is gated on a top-level values flag (`serviceMonitor.enabled`).
- A `templates/` change bumps `charts/<app>/Chart.yaml` `version`.
- This is opt-in — `/argocd-add-chart` and `/argocd-deploy` never add templates.
  Use `/argocd-add-manifest`. Full mechanism and conventions:
  the `argocd-extra-manifests` skill.
```

- [ ] **Step 2: Make `fullnameOverride` mandatory in the wrapper-chart section**

In the "## Wrapper chart" section, find the sentence about `values.yaml` /
overrides and add (or adjust) so it states: *"Always set
`<chart-name>.fullnameOverride: <app>` — it keeps generated resource names
predictable and is required if you add your own templates."*

- [ ] **Step 3: Run the skills test**

Run: `python -m pytest tests/test_plugin_components.py -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add skills/argocd-repo-conventions/SKILL.md
git commit -m "docs(conventions): custom manifests section + mandatory fullnameOverride

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 11: Edit `argocd-rollout`, `argocd-add-chart`, `argocd-deploy`, `README`

**Files:**
- Modify: `skills/argocd-rollout/SKILL.md`
- Modify: `commands/argocd-add-chart.md`
- Modify: `commands/argocd-deploy.md`
- Modify: `README.md`

- [ ] **Step 1: `argocd-rollout` functional-check table**

Find the functional-check table (the "Healthy ≠ working" section). Add a row:

```markdown
| Extra manifest (ServiceMonitor / PodMonitor / …) | it renders and the CRD accepts it; for a monitor, after sync the target appears in Prometheus `/api/v1/targets` and `up{...}` for the app returns 1 |
```

- [ ] **Step 2: `argocd-add-chart.md` one-liner**

In the `## Notes` section, add:
```markdown
- Never adds `charts/<app>/templates/`. To add your own manifests (ServiceMonitor,
  IngressRoute, …) use `/argocd-add-manifest`.
```

- [ ] **Step 3: `argocd-deploy.md` one-liner**

In the `## Notes` section, add the same line as Step 2.

- [ ] **Step 4: `README.md`**

In the command table, add after `/argocd-sync`:
```markdown
| `/argocd-add-manifest <app> <kind>` | Add your own templated manifest (ServiceMonitor/PodMonitor, or any kind via free text) to a wrapper chart's `templates/`, gated + verified, open a PR. Opt-in. |
```

In the roadmap section, add:
```markdown
Next: `argocd-observability` / `/argocd-observe` (spec #2) — the full
ServiceMonitor + Grafana dashboard + alerts onboarding workflow, built on
`/argocd-add-manifest`.
```

- [ ] **Step 5: Run tests + grep**

Run:
```bash
python -m pytest -q
grep -L 'interaction-style' commands/*.md
```
Expected: all tests pass; `grep -L` prints nothing (every command still references the contract).

- [ ] **Step 6: Commit**

```bash
git add skills/argocd-rollout/SKILL.md commands/argocd-add-chart.md commands/argocd-deploy.md README.md
git commit -m "docs: wire /argocd-add-manifest into rollout, add-chart, deploy, README

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 12: End-to-end dry run of the command

Exercise `/argocd-add-manifest` by hand-following `commands/argocd-add-manifest.md`
against the live `test-k8s-configs` repo, targeting an app that **does** expose
metrics. `trino` exposes a `http` port with `/metrics` via the JMX exporter and
the chart already ships `servicemonitor-coordinator.yaml` — so pick **`airflow`**,
whose chart ships a `statsd` exporter Service (`airflow-statsd` on port `9102`
named `metrics`) but the wrapper doesn't enable a ServiceMonitor.

**Files:**
- Modify: any starter / skill / command file the run reveals to be wrong.

- [ ] **Step 1: Locate airflow's metrics Service**

Run (from a checkout of `test-k8s-configs` on `master`):
```bash
cd /c/claude/test-k8s-configs && git checkout master && git pull
helm dependency build charts/airflow >/dev/null
helm template charts/airflow -f environments/local/values/airflow.yaml \
  | python -c "import sys,yaml; [print(d['metadata']['name'], [ (p.get('name'),p.get('port')) for p in d['spec'].get('ports',[])]) for d in yaml.safe_load_all(sys.stdin) if d and d.get('kind')=='Service']"
```
Expected: a `airflow-statsd` Service with a port named `metrics` (9102) — or
`statsd-scrape` / similar. Record the exact Service label set and port name.
If airflow's statsd exporter isn't emitting Prometheus format (older charts
expose statsd only), fall back to **`kube-state-metrics`**-style: pick `trino`
instead and add a PodMonitor for the coordinator's `http` port. Record which app
you used.

- [ ] **Step 2: Follow the command steps 1–9 by hand**

Create branch `add-manifest/airflow-servicemonitor` in `test-k8s-configs`.
Confirm `charts/airflow/values.yaml` has `airflow.fullnameOverride: airflow`
(it does — set during the earlier e2e). Copy the starter to
`charts/airflow/templates/servicemonitor.yaml`. Add to
`charts/airflow/values.yaml`:
```yaml
serviceMonitor:
  enabled: true
  selectorLabels:
    <the label set from step 1>
  port: <the port name from step 1>
  path: /metrics
  interval: 30s
```
Bump `charts/airflow/Chart.yaml` `version` to `0.1.1`.

- [ ] **Step 3: Verify render + CRD accept**

Run:
```bash
helm template charts/airflow -f environments/local/values/airflow.yaml --show-only templates/servicemonitor.yaml
helm template charts/airflow -f environments/local/values/airflow.yaml --show-only templates/servicemonitor.yaml | kubectl apply --dry-run=server -f -
```
Expected: a valid `ServiceMonitor`; `serverside dry run` succeeds (the
Prometheus-Operator CRD is installed on `docker-desktop`).
Fix the starter or skill if the CRD rejects it, then re-run Tasks 4/6/8.

- [ ] **Step 4: Commit, PR, merge, sync, functional-check**

```bash
git add charts/airflow environments/ 2>/dev/null; git -C /c/claude/test-k8s-configs add -A
git -C /c/claude/test-k8s-configs -c core.autocrlf=false commit -m "Add ServiceMonitor to airflow

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```
Push, open + merge the PR, `kubectl -n argocd annotate app airflow argocd.argoproj.io/refresh=hard --overwrite`, wait for `Synced`, then the functional check:
```bash
# port-forward prometheus (18280 already used; use 19091) then:
curl -s 'http://localhost:19091/api/v1/targets?state=active' \
  | python -c "import sys,json; d=json.load(sys.stdin); print([t['health'] for t in d['data']['activeTargets'] if 'airflow' in t['scrapePool']])"
```
Expected: at least one `up`. If the ServiceMonitor renders + applies but no
target appears, diagnose per `prometheus-operator.md` (selector labels / port
name / namespaceSelector) — the fix is a values change in `charts/airflow/`.

- [ ] **Step 5: Record findings and fix the plugin**

For every deviation (starter field the CRD rejected, skill instruction that was
ambiguous, command step that mislabelled the port), fix the plugin file. Re-run
`python -m pytest -q` and `bash tests/smoke/extra_manifest_smoke.sh`.

- [ ] **Step 6: Clean up and commit plugin fixes**

```bash
cd /c/claude/argocd-gitops-plugin
rm -rf tests/.out
git add -A
git commit -m "fix: corrections from /argocd-add-manifest dry run

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>" || echo "e2e clean, nothing to fix"
```

---

## Task 13: Validate and finalise

**Files:**
- Modify: whatever the validators flag.

- [ ] **Step 1: plugin-validator agent**

Dispatch `plugin-dev:plugin-validator` against `C:\claude\argocd-gitops-plugin`.
Expected: manifest valid, `argocd-add-manifest` command + `argocd-extra-manifests`
skill discoverable, no path issues. Fix anything flagged.

- [ ] **Step 2: skill-reviewer agent**

Dispatch `plugin-dev:skill-reviewer` for `skills/argocd-extra-manifests`.
Expected: description triggers well; body follows progressive disclosure (mechanism
+ conventions in SKILL.md, detail in `references/`). Apply reasonable suggestions.

- [ ] **Step 3: Full green run**

Run: `python -m pytest`
Expected: all pass.

Run: `bash tests/smoke/extra_manifest_smoke.sh`
Expected: `OK: servicemonitor starter renders, overrides apply, gate works`.

Run: `bash tests/smoke/helm_smoke.sh`
Expected: still `OK` (unchanged behaviour).

- [ ] **Step 4: PR + merge**

```bash
git push -u origin feat/extra-manifests-spec
gh pr create --base master --head feat/extra-manifests-spec \
  --title "Custom manifests in wrapper charts: /argocd-add-manifest + argocd-extra-manifests" \
  --body "Spec #1 of the custom-templating work. Opt-in /argocd-add-manifest adds ServiceMonitor/PodMonitor (starters) or any kind (free text) to charts/<app>/templates/ alongside the pinned upstream chart. New argocd-extra-manifests skill (mechanism, conventions, prometheus-operator + hooks-and-waves references). Edits to repo-conventions (mandatory fullnameOverride), rollout (functional-check row), add-chart/deploy (one line), README. Tests: test_starters.py + extra_manifest_smoke.sh. Exercised end-to-end adding a ServiceMonitor to airflow on the live cluster.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
gh pr merge feat/extra-manifests-spec --merge --delete-branch
git checkout master && git pull && git remote prune origin
```

- [ ] **Step 5: Report**

Summarise: files added/edited, `pytest` + smoke output, the airflow ServiceMonitor
result (target up or the diagnosed reason), and that spec #2 (`argocd-observability`)
is next.

---

## Self-Review

**1. Spec coverage**

| Spec item | Task |
|---|---|
| `argocd-extra-manifests` skill `SKILL.md` | 1 |
| `references/prometheus-operator.md` | 2 |
| `references/hooks-and-waves.md` | 3 |
| starters `servicemonitor.yaml`, `podmonitor.yaml` | 4, 5 |
| `/argocd-add-manifest` command | 7 |
| opt-in only (nothing else calls it) | 7 (stated), 11 (add-chart/deploy one-liners) |
| `fullnameOverride` mandatory | 1, 10 |
| gate on values flag | 4, 5 (starters), 6 (test enforces) |
| CRD / sync-wave precondition check | 7 step 7 |
| bump chart version on templates change | 1, 7, 12 |
| `argocd-repo-conventions` "Custom manifests" section | 10 |
| `argocd-rollout` functional-check row | 11 |
| `argocd-add-chart` / `argocd-deploy` one-liners | 11 |
| README command table + roadmap | 11 |
| `test_plugin_components.py` EXPECTED_* | 9 |
| `test_starters.py` | 6 |
| `extra_manifest_smoke.sh` | 8 |
| "app exposes no metrics → stop" behaviour | 1 (skill section), 7 step 4 |
| end-to-end verification against the live cluster | 12 |
| validation (plugin-validator, skill-reviewer) | 13 |

No gaps. `tests/fixtures/starter.vars.json` mentioned in the spec's file tree is
**not** created — Task 8's smoke script writes its values inline instead, which is
simpler; noted here so the deviation is explicit.

**2. Placeholder scan** — no "TBD"/"handle appropriately"/"similar to". Every
file's full content is in its task. The one conditional is Task 12 step 1 (pick
airflow, fall back to trino) — both branches are spelled out with the exact
commands.

**3. Type / name consistency**

- Command name `argocd-add-manifest`, skill name `argocd-extra-manifests` — used
  identically in Tasks 1, 6, 7, 9, 10, 11, 13 and `test_plugin_components.py`.
- Starter filenames `servicemonitor.yaml` / `podmonitor.yaml` — match
  `EXPECTED` in `test_starters.py` (Task 6) and the `<kind>` names in the command
  (Task 7).
- Values keys: `serviceMonitor.{enabled,selectorLabels,port,path,scheme,interval,scrapeTimeout,honorLabels,relabelings,metricRelabelings,name,namespace,labels,namespaceSelector}`
  — identical across the starter (Task 4), the skill checklist (Task 1), the
  command step 6 (Task 7), the smoke `values.yaml` (Task 8), and
  `prometheus-operator.md` (Task 2). `podMonitor.*` mirrors it (Task 5).
- `app.kubernetes.io/managed-by: argocd-gitops-plugin` label — set in both
  starters (Tasks 4, 5), asserted in the smoke test (Task 8).

Fixed during review: Task 8's smoke script now writes `helm template` output to
`$OUT/rendered.yaml` and greps/parses that file, instead of an awkward bash
variable holding a multi-line YAML doc passed inline to Python.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-10-argocd-extra-manifests.md`.
