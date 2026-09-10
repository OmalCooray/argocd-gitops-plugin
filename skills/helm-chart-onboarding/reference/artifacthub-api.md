# ArtifactHub REST API (used via WebFetch)

<!-- owner: helm-chart-onboarding skill · last reviewed: 2026-09-10 -->

Base: `https://artifacthub.io/api/v1`. No auth for reads.

## Search for a chart

```
GET /packages/search?kind=0&ts_query_web=<term>&limit=20
```
`kind=0` = Helm charts. Response: `packages[]` with `name`, `repository.name`,
`repository.url`, `version` (latest), `official`, `cncf`.

## Get a specific chart's detail + version list

```
GET /packages/helm/<repo-name>/<chart-name>
```
Returns `version` (latest), `available_versions[]` (each with `version`,
`ts`, `contains_security_updates`, `prerelease`), `repository.url`,
`data.kubeVersion` (constraint string), `data.dependencies[]`.

## Get one exact version

```
GET /packages/helm/<repo-name>/<chart-name>/<version>
```

## Picking a version programmatically

1. Filter `available_versions` to `prerelease == false`.
2. Sort by semver descending.
3. Take the first whose `data.kubeVersion` (if present) is satisfied by the
   target cluster's server version (`kubectl version -o json`).

## Notes

- The `repository.url` from the API is the **Helm repo URL** — use it directly in
  `Chart.yaml` `dependencies[].repository` and `helm show values --repo`.
- Some charts are OCI (`repository.url` starts with `oci://`). For OCI,
  `Chart.yaml` `repository` is the `oci://...` path and `helm show values` takes
  the full `oci://.../<chart>` reference with `--version`.
