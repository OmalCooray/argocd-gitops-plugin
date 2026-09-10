# Chart-specific operational notes

<!-- owner: values-review skill · last reviewed: 2026-09-10 -->

Hard-won specifics for individual upstream charts, moved here so
`prod-readiness-checklist.md` stays a generic rubric. Add a section when a chart
bites you; keep each self-contained.

## Apache Airflow (`apache-airflow/airflow`)

### Airflow-specific prod checklist

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
- `migrateDatabaseJob.enabled: true` (runs `airflow db upgrade`) — required
  whenever the Airflow version or schema changes.
- Resource floors that actually work: webserver ~1Gi, scheduler ~1Gi,
  each worker ~1Gi+, triggerer ~512Mi. Below these Airflow OOMs under load.
- `apiServer.*` is the Airflow 3 replacement for `webserver.*`; on Airflow 3 the
  webserver secret key value is `apiSecretKeySecretName`, plus `jwtSecretName`.

#### Airflow on Argo CD — the deployment gotchas

Verified against `apache-airflow/airflow` 1.22.0 + Argo CD 3.5 (`airflow: {}`
plain deploy hangs on "Waiting for migrations" without these):

- **Helm hooks don't run.** The chart's `migrateDatabaseJob` and `createUserJob`
  ship as `helm.sh/hook: pre-install`. Argo CD does not run Helm's install hooks,
  so the DB is never migrated and every component's `wait-for-airflow-migrations`
  init container crash-loops forever. Set
  `migrateDatabaseJob.useHelmHooks: false` and `createUserJob.useHelmHooks: false`
  (also `applyCustomEnv: false`).
- **Jobs then drift `OutOfSync` forever.** A started Job gets a
  `batch.kubernetes.io/controller-uid` selector that the rendered manifest lacks.
  Re-annotate both jobs as Argo CD hooks so they're recreated each sync:
  `jobAnnotations: {argocd.argoproj.io/hook: Sync,
  argocd.argoproj.io/hook-delete-policy: BeforeHookCreation}`.
- **Chart-generated random secrets churn.** With no `*SecretName` set, the chart
  emits `*-fernet-key`, `*-api-secret-key`, `*-jwt-secret`, `*-metadata`,
  `*-broker-url` with fresh random values on every render → permanent `OutOfSync`
  and, worse, a rotating Fernet key that makes stored connections undecryptable.
  Create stable Secrets out of band and set `fernetKeySecretName`,
  `apiSecretKeySecretName`, `jwtSecretName`, `data.metadataSecretName`.
- **Out-of-band Secrets must not carry the app's tracking label.** If a
  hand-created Secret has `app.kubernetes.io/instance: <app>` (e.g. because you
  `kubectl apply`-ed over a chart-generated one), Argo CD treats it as an
  app resource that's "extra" and sits `OutOfSync`. Create them fresh with no
  Argo CD labels/annotations.
- **KubernetesExecutor** removes Redis, the Celery result backend, the broker,
  and the worker Deployment — four fewer stateful things to run. Good default for
  a first prod cut; set `executor: KubernetesExecutor` and `redis.enabled: false`.

## MySQL (any chart) — 8/9 client auth

### MySQL 8/9 auth — every client hits this

- MySQL **9.x removed the `mysql_native_password` plugin entirely** (deprecated
  in 8.0). `CREATE USER ... IDENTIFIED WITH mysql_native_password` fails with
  "Plugin 'mysql_native_password' is not loaded". Users are `caching_sha2_password`.
- `caching_sha2_password` needs an **encrypted channel** for the first auth (RSA
  key exchange), or `allowPublicKeyRetrieval=true` on an insecure one. What each
  client needs in its connection string:
  - **Airflow** (`mysqlclient` C driver): `mysql://user:pass@host/db` works as-is.
  - **Metabase** (MariaDB Connector/J **2.x**): `?useSSL=true&trustServerCertificate=true`
    (not `sslMode=trust` — that's the 3.x syntax).
  - **Trino** / anything on **MySQL Connector/J 8.x**: `?sslMode=REQUIRED`.
  - Grafana (`go-sql-driver`): `?tls=skip-verify` or `?allowNativePasswords=true&tls=...`.
- The MySQL server chart must actually enable TLS (groundhog2k/mysql and Bitnami
  both do by default, with a self-signed cert — hence `trustServerCertificate` /
  `skip-verify` / `sslMode=REQUIRED` rather than full verification).

### MySQL server config for Airflow

- Airflow requires `explicit_defaults_for_timestamp=1` on the MySQL server, plus
  `character-set-server=utf8mb4` / `collation-server=utf8mb4_unicode_ci`. Pass
  these via the MySQL chart's custom-config mechanism (Bitnami:
  `primary.configuration`; groundhog2k: `customConfig`).
- The `apache/airflow` image bundles `mysqlclient`, so a `mysql://airflow:PASS@host:3306/airflow`
  SQLAlchemy URL in the `connection` key of `data.metadataSecretName` works
  as-is. Verify with a throwaway pod: `python -c "import MySQLdb"`.
- Avoid the Bitnami MySQL chart unless you've confirmed the image tag is still
  pullable (post-2025 Bitnami moved free Debian images to `bitnamilegacy/`).
  `groundhog2k/mysql` uses the official `mysql` image and is a clean
  drop-in for a single-primary metadata DB.
- Deploy the DB **before** Airflow: put `argocd.argoproj.io/sync-wave: "-1"` on
  the MySQL `Application` so the root app syncs it first. (The plugin's
  `application.yaml.tmpl` has no sync-wave field yet — add the annotation by
  hand, or via `/argocd-deploy` follow-up edit.)
- Create the `airflow` database + user through the MySQL chart's user-database
  option, sourcing name/user/password from the **same Secret** the Airflow
  `data.metadataSecretName` points at (add a `connection` key to it).

### Sharing one MySQL across apps

A single MySQL StatefulSet backing several apps (Airflow metadata, Metabase app
DB, a Trino catalog target) is fine for a small platform — one DB to run,
back up, and monitor. Give each app its own database + least-privilege user
(`SELECT`/`SHOW VIEW` for a read-only catalog; full rights on its own schema for
an app that owns state). Passwords in per-app Secrets, referenced by both the DB
chart (to create the user) and the consuming app.
