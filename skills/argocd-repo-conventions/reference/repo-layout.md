# Annotated repo layout

```
<gitops-repo>/
├── charts/                          # CATALOG
│   └── <app>/
│       ├── Chart.yaml               # apiVersion v2; upstream chart pinned in dependencies
│       └── values.yaml              # base overrides, nested under the dependency name
│
├── environments/
│   └── <env>/                       # one folder per cluster/environment
│       ├── root.yaml                # root app-of-apps → path: environments/<env>/apps
│       ├── apps/
│       │   └── <app>.yaml           # Argo CD Application (multi-source)
│       └── values/
│           └── <app>.yaml           # optional per-env Helm values overlay
│
├── bootstrap/
│   └── install.sh                   # helm upgrade --install argo-cd + kubectl apply root.yaml
│
├── .claude/
│   └── CLAUDE.md                    # repo facts + catalog inventory + deployment matrix
├── CODEOWNERS
└── README.md
```

## Why this shape

- **Catalog reuse across environments**: three environments deploying `metabase`
  share one `charts/metabase/`. No chart duplication, no drift.
- **Selective deployment**: `charts/` may hold 50 apps; an environment's
  `apps/` folder contains only the handful that run there.
- **Additive multi-env**: a new cluster is a new `environments/<name>/` folder
  plus one `kubectl apply` of its `root.yaml`. Nothing else moves.
- **Greppable env delta**: `diff environments/dev environments/prod` shows the
  entire intentional difference between environments.

## Adding an environment later

```
environments/
├── data-platform/      # existing, untouched
└── prod/               # new: root.yaml + apps/ (subset) + values/ (overrides)
```
