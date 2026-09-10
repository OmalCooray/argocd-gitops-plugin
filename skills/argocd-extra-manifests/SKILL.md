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
