# Prod-readiness checklist — detail and per-workload notes

<!-- owner: values-review skill · last reviewed: 2026-09-10 -->

This expands the `prod-ready` profile in `SKILL.md`. Use it when the summary
checklist isn't specific enough for the chart in front of you.

## Reading the chart

Different charts expose the same concept under different keys. Before reviewing,
map these for the specific chart (from `helm show values`):

| Concept | Common key patterns |
|---|---|
| Per-component resources | `<component>.resources`, `resources`, `<component>.resourcesPreset` (Bitnami) |
| Replicas | `<component>.replicas`, `replicaCount`, `<component>.replicaCount` |
| PDB | `<component>.podDisruptionBudget`, `pdb.create`, `<component>.pdb` |
| Probes | `<component>.livenessProbe`, `startupProbe`, `customLivenessProbe` |
| Security context | `podSecurityContext`, `containerSecurityContext`, `<component>.securityContext` |
| Persistence | `persistence`, `<component>.persistence`, `primary.persistence` (Bitnami) |
| External DB | `externalDatabase`, `<db>.enabled: false` + `externalDatabase.*`, `metadataConnection` |
| Image | `image.repository`/`image.tag`, `<component>.image` |
| HPA | `autoscaling.enabled`, `<component>.hpa`, `<component>.autoscaling` |

## Per-workload guidance

### Web / API frontends (Airflow webserver, Grafana, Metabase, Kafka UI)

- ≥ 2 replicas, PDB `minAvailable: 1`, `podAntiAffinity` preferred.
- Readiness probe on the HTTP health path; startup probe if first boot runs
  migrations (Airflow webserver: `airflow db check` can take 60–120s).
- HPA on CPU (target ~70%) if traffic varies.
- Session affinity or stateless sessions — if the app keeps in-memory sessions,
  either enable sticky sessions at the ingress or move sessions to the DB/redis.

### Schedulers / controllers / operators (Airflow scheduler, cert-manager)

- Usually **active/standby** or **leader-elected**, not horizontally scaled.
  Airflow supports multiple active schedulers (2 is the common prod number) —
  set `scheduler.replicas: 2` only if the chart wires up the DB row locking
  (the official chart does).
- Liveness probe present; if the component has no HTTP endpoint, an `exec` probe
  on a CLI health command.
- PDB `maxUnavailable: 1` so a drain doesn't take all schedulers at once.

### Workers / executors (Celery workers, Airflow workers)

- HPA or KEDA on queue depth. At minimum a fixed `>= 2`.
- `terminationGracePeriodSeconds` long enough to finish in-flight tasks
  (Airflow: `celery.worker_termination_grace_period`, often 600).
- Resources sized to one task's footprint × concurrency.

### Databases (MySQL, PostgreSQL — deployed as their own Argo CD app)

- **StatefulSet**, not Deployment. One primary; add replicas only if the app
  reads from replicas.
- `persistence.enabled: true`, explicit `storageClass`, size with headroom
  (2–3× current data), `ReadWriteOnce` is correct here.
- Resources: give the DB real memory (buffer pool / shared buffers). A blocker if
  `limits.memory` < a few hundred MiB for anything real.
- `runAsNonRoot`, non-root `fsGroup` so the data dir is writable.
- **Backups**: the chart's backup CronJob if it has one (Bitnami MySQL:
  not built in — add a CronJob running `mysqldump` to a PVC or object store),
  or document the external backup. A primary DB with no backup is a **blocker**.
- Credentials via `auth.existingSecret` — never `auth.password` inline.
- `PodDisruptionBudget` `maxUnavailable: 0` for a single-primary DB (a voluntary
  eviction of the only primary is an outage).

### Message brokers / caches (Redis, Kafka)

- Redis for Celery: at least persistence off is acceptable (it's a queue, not
  state of record) but sizing and `maxmemory-policy` matter.
- Kafka: `>= 3` brokers, `replicationFactor >= 3`, `minInsyncReplicas: 2`,
  anti-affinity across nodes/zones, persistence per broker.

## Chart-specific gotchas

Chart-specific gotchas (Airflow, MySQL auth, …) live in `chart-notes.md`.
