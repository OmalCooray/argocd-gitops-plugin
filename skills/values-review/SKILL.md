---
name: values-review
description: Review a wrapper chart's values against a dev-ready or prod-ready rubric for an Argo CD GitOps repo — resources, replicas/PDB, probes, security context, persistence, anti-affinity, HPA, image pinning, external datastores, backups. Load when hardening a chart's values.yaml or a per-environment overlay, or when the user asks whether a config is production ready.
---

# Values review

Assess a chart's effective values (base `charts/<app>/values.yaml` merged with an
optional `environments/<env>/values/<app>.yaml` overlay) against one of two
profiles and produce a findings list. Optionally emit a hardened overlay.

## How to run

1. Load `argocd-repo-conventions` (needed for the overlay file layout and the
   dev/prod revision model).
2. Get the **effective values** the way Argo CD will see them:
   ```bash
   helm show values <chart> --repo <repo-url> --version <version> > upstream.yaml   # reference
   helm template charts/<app> \
     -f environments/<env>/values/<app>.yaml \
     --api-versions policy/v1/PodDisruptionBudget \
     > rendered.yaml
   ```
   Review `rendered.yaml` (actual manifests) plus the two values files. Upstream
   defaults tell you which knobs exist.
3. Walk the checklist for the chosen profile (below; full detail and per-workload
   notes in `reference/prod-readiness-checklist.md`; chart-specific notes in
   `reference/chart-notes.md`).
4. Report findings as a table: `severity | area | finding | fix (values key)`.
   Severity: **blocker** (would fail or lose data in that profile), **warn**
   (works but risky), **note** (nice to have).
5. If asked, write the hardened settings into
   `environments/<env>/values/<app>.yaml` (never the base `values.yaml` for
   env-specific values), nested under the subchart name. Show a diff, don't apply
   to a cluster.

## Profiles

### dev-ready (cost-optimized, single-node friendly)

Pass if the chart will come up and stay up on a small cluster without wasting
resources. Do **not** flag missing HA here.

- Requests set (small), limits optional. No request on a Deployment is a **warn**
  (it can be evicted first / scheduled badly).
- 1 replica is fine. Bundled single-instance datastore (the chart's Postgres/
  MySQL subchart) is fine.
- Persistence: enabled for stateful data you care about keeping between restarts;
  `emptyDir` acceptable for scratch/dev.
- Probes: keep the chart defaults. Only flag if the chart ships none.
- Image: a pinned tag or the chart's default appVersion tag. `latest` / no tag is
  a **warn**.
- Ingress usually off; `NodePort`/`ClusterIP` + port-forward is fine.

### prod-ready

- **Resources**: requests **and** limits on every workload. Missing either =
  **blocker**. Limits within ~2x requests unless the app is bursty.
- **Availability**: stateless components ≥ 2 replicas **and** a
  `PodDisruptionBudget` (`minAvailable: 1` or `maxUnavailable: 1`). Missing PDB
  with >1 replica = **warn**; 1 replica for a component that supports more =
  **blocker**.
- **Anti-affinity**: `podAntiAffinity` (at least `preferredDuringScheduling`) on
  multi-replica components so replicas don't share a node. Missing = **warn**.
- **Datastore**: do **not** use the chart's bundled DB subchart in prod — point
  the app at an external database (its own Argo CD app, or a managed instance).
  Bundled DB in prod = **blocker**. The external DB itself must have persistence,
  resources, and a backup story.
- **Persistence**: every PVC has an explicit `storageClass` (not "" / default)
  and a deliberate size. `ReadWriteOnce` volumes on a multi-replica Deployment =
  **blocker** (use per-replica StatefulSet volumes or RWX).
- **Probes**: liveness **and** readiness on every workload; startup probe for
  slow-booting apps (Airflow webserver, databases). Missing readiness =
  **blocker** (traffic to unready pods); missing liveness = **warn**.
- **Security context**: `runAsNonRoot: true`, a numeric `runAsUser`, drop `ALL`
  capabilities, `readOnlyRootFilesystem` where the app allows, `seccompProfile:
  RuntimeDefault`. Running as root = **blocker**.
- **Autoscaling**: HPA for components with variable load (web frontends,
  Airflow/Celery workers). Missing where clearly beneficial = **note**.
- **Image**: exact tag or digest pin, `pullPolicy: IfNotPresent`. Floating tag =
  **blocker**. A private registry needs `imagePullSecrets`.
- **Secrets**: no plaintext passwords/keys/tokens in `values.yaml` or the
  overlay. Reference an existing `Secret` (`existingSecret:` / `*SecretName:`) or
  an External Secrets / Sealed Secrets object. Plaintext secret = **blocker**.
- **Backups**: stateful apps (databases, anything with a PVC holding state of
  record) need a backup mechanism — a CronJob, the chart's backup option, or a
  documented external process. None = **warn** (**blocker** for a primary DB).
- **Updates**: `strategy: RollingUpdate` with sane `maxUnavailable`/`maxSurge`;
  `Recreate` on a user-facing service = **warn**.

## Output contract

- Always produce the findings table, even if empty ("no blockers for <profile>").
- Group by severity, blockers first.
- Each fix names the concrete values key path, e.g.
  `airflow.workers.resources.limits.memory`, and a suggested value.
- If emitting an overlay, the file must still be valid when the app has never
  been deployed (comment-only is valid; a partial map is valid).
