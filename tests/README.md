# Tests

| File | Needs | Checks |
|------|-------|--------|
| `test_manifest.py` | python | `plugin.json` + `.mcp.json` shape |
| `test_templates.py` | python | templates render to golden files; no stray placeholders |
| `test_plugin_components.py` | python | commands/skills/agents exist with valid frontmatter; no hardcoded home paths |
| `smoke/helm_smoke.sh` | helm, network | render wrapper chart from templates -> `helm dependency build` + `helm lint` |
| `smoke/argocd_e2e.sh` | kubectl, helm, a throwaway cluster | install Argo CD, apply a root app, confirm it reconciles |

Run the fast suite with `python -m pytest`. Smoke scripts are opt-in.
