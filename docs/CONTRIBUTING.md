# Contributing

## The development flow

Every feature follows the same cycle (this repo's `docs/superpowers/`):

1. **Brainstorm** the design — `superpowers:brainstorming` → a spec in
   `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`.
2. **Plan** — `superpowers:writing-plans` → a task-by-task plan in
   `docs/superpowers/plans/`.
3. **Execute** — `superpowers:subagent-driven-development`, with spec + quality
   review between tasks.
4. **Dogfood** — run the change end-to-end against a real Argo CD + cluster.
5. **Finish** — `superpowers:finishing-a-development-branch` → PR → merge.

Infra / docs chores can skip steps 1–2 but still land behind a reviewed PR.

## Rules enforced by tests / CI

- Every file in `commands/` references `${CLAUDE_PLUGIN_ROOT}/references/interaction-style.md`
  (`test_no_hardcoded_home_paths_in_components` + a grep).
- No absolute or home paths in `commands/`, `agents/`, `skills/` — use
  `${CLAUDE_PLUGIN_ROOT}/...`.
- No active `.mcp.json` committed — only `.mcp.json.example`
  (`test_mcp_example_present_and_no_active_mcp_json`).
- A `templates/` or `grafana-dashboards/` change in a wrapper chart bumps that
  chart's `Chart.yaml` `version`.
- New command → add to `EXPECTED_COMMANDS`; new skill → `EXPECTED_SKILLS`
  (`tests/test_plugin_components.py`).
- Starters (`skills/*/reference/starters/*.yaml`) are gated on a nil-safe
  `{{- if (.Values.<x>).enabled }}` and never `include` a subchart `_helpers`.

## Running the checks locally

```bash
python -m pip install -r tests/requirements.txt
python -m pytest -q
bash tests/smoke/helm_smoke.sh
bash tests/smoke/extra_manifest_smoke.sh
bash tests/smoke/dashboard_smoke.sh
# needs a cluster:
bash tests/smoke/argocd_e2e.sh
```

## Releasing

1. Land all milestone PRs.
2. Update `CHANGELOG.md`: move `[Unreleased]` items into a dated `[X.Y.Z]` section.
3. Bump `.claude-plugin/plugin.json` `version`.
4. `git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z`.

## Branch protection

`master` requires the CI status checks. Applied with:

```bash
gh api -X PUT repos/OmalCooray/argocd-gitops-plugin/branches/master/protection \
  -f 'required_status_checks[strict]=true' \
  -f 'required_status_checks[checks][][context]=pytest (ubuntu-latest, py3.12)' \
  # ... one line per required check ...
  -F 'enforce_admins=false' -F 'required_pull_request_reviews=null' -F 'restrictions=null'
```
