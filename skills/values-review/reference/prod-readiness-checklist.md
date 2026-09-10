# Prod-readiness checklist — detail and per-workload notes

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

## Airflow-specific prod checklist

The `apache-airflow/airflow` chart:

- `executor`: `LocalExecutor` for dev; `CeleryExecutor` (or `KubernetesExecutor`)
  for prod. `LocalExecutor` in prod = **warn** (scheduler is a single point of
  task execution, no isolation).
- `postgresql.enabled` / bundled DB → set `false`, configure
  `data.metadataSecretName` or `data.metadataConnection` pointing at the external
  DB. Bundled Postgres in prod = **blocker**.
- `redis.enabled` with `CeleryExecutor`: bundled redis is acceptable but give it
  persistence off + resources, or externalize it.
- `webserverSecretKey` / `webserverSecretKeySecretName`: MUST be set and stable
  (a rotating key logs everyone out and breaks running tasks). Unset = **blocker**.
- `fernetKey` / `fernetKeySecretName`: MUST be set and stable (encrypts
  connections/variables in the DB). Unset or default = **blocker**.
- `scheduler.replicas: 2`, `triggerer.replicas: 2`.
- `workers.persistence` (for `CeleryExecutor` worker logs) or a remote logging
  backend (`config.logging.remote_logging: 'True'` + an S3/GCS connection) —
  without remote logging, worker logs vanish when the pod dies = **warn**.
- `dags.gitSync` or a baked image for DAG delivery; `gitSync` needs a
  credentials secret for private repos.
- `migrateDatabaseJob.enabled: true` (runs `airflow db upgrade` as a pre-sync
  hook) — required whenever the Airflow version or schema changes.
- Resource floors that actually work: webserver ~1Gi, scheduler ~1Gi,
  each worker ~1Gi+, triggerer ~512Mi. Below these Airflow OOMs under load.

## MySQL for Airflow — the gotchas

- Airflow requires `explicit_defaults_for_timestamp=1` on the MySQL server.
  Bitnami MySQL: set it under `primary.configuration` or
  `primary.extraFlags`.
- Use the `mysql` (not `mysql+mysqldb`) driver family the chart expects; the
  Airflow chart builds the SQLAlchemy URL from `data.metadataConnection.protocol`
  — set it to `mysql`.
- Character set `utf8mb4`.
- Create the `airflow` database and user via `auth.database` / `auth.username`
  in the MySQL chart; put the password in a `Secret` both apps reference.
