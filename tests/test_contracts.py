"""Regression tests: each fixed live-test defect stays fixed."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Commands/agents that contact a cluster or Argo CD and so must resolve the target first.
CLUSTER_COMPONENTS = [
    "commands/argocd-bootstrap.md",
    "commands/argocd-audit.md",
    "commands/argocd-doctor.md",
    "commands/argocd-sync.md",
    "commands/argocd-deploy.md",
    "commands/argocd-add-chart.md",
    "commands/argocd-add-manifest.md",
    "commands/argocd-add-dashboard.md",
    "commands/argocd-review-values.md",
    "agents/argocd-onboarder.md",
]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def fenced_lines(text):
    """Yield lines that are inside ``` fences."""
    inside = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            inside = not inside
            continue
        if inside:
            yield line


def test_target_resolution_reference_exists_and_is_complete():
    t = read("references/target-resolution.md")
    for needle in ("Target: context=", "--context", "cluster-info", "Proceed?", ".claude/CLAUDE.md"):
        assert needle in t, needle


def test_every_cluster_component_resolves_the_target_first():
    for rel in CLUSTER_COMPONENTS:
        assert "target-resolution.md" in read(rel), f"{rel} must reference target-resolution.md"


def test_no_bare_kubectl_in_fenced_examples():
    allowed = re.compile(r"kubectl\s+(config\s|version\s+--client)")
    for rel in CLUSTER_COMPONENTS + [
        "skills/argocd-rollout/SKILL.md",
        "skills/argocd-troubleshooting/SKILL.md",
    ]:
        for line in fenced_lines(read(rel)):
            if re.search(r"\bkubectl\s", line) and "--context" not in line and not allowed.search(line):
                raise AssertionError(f"{rel}: kubectl without --context: {line.strip()}")
