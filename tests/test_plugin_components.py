"""Structural checks for commands, agents, and skills."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]

EXPECTED_COMMANDS = {
    "argocd-bootstrap", "argocd-init-repo", "argocd-add-chart",
    "argocd-deploy", "argocd-audit",
}
EXPECTED_SKILLS = {"argocd-repo-conventions", "helm-chart-onboarding"}
EXPECTED_AGENTS = {"argocd-onboarder"}

FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _frontmatter(path: pathlib.Path) -> str:
    m = FRONTMATTER.match(path.read_text(encoding="utf-8"))
    assert m, f"{path} has no YAML frontmatter"
    return m.group(1)


def test_expected_commands_present_and_named():
    files = {p.stem for p in (ROOT / "commands").glob("*.md")}
    assert EXPECTED_COMMANDS <= files, EXPECTED_COMMANDS - files
    for name in EXPECTED_COMMANDS:
        fm = _frontmatter(ROOT / "commands" / f"{name}.md")
        assert "description:" in fm


def test_expected_skills_have_skill_md_with_name_and_description():
    for name in EXPECTED_SKILLS:
        skill = ROOT / "skills" / name / "SKILL.md"
        assert skill.exists(), skill
        fm = _frontmatter(skill)
        assert re.search(r"^name:\s*\S", fm, re.MULTILINE)
        assert re.search(r"^description:\s*\S", fm, re.MULTILINE)


def test_expected_agents_present_with_description():
    for name in EXPECTED_AGENTS:
        agent = ROOT / "agents" / f"{name}.md"
        assert agent.exists(), agent
        assert "description:" in _frontmatter(agent)


def test_no_hardcoded_home_paths_in_components():
    offenders = []
    for sub in ("commands", "agents", "skills"):
        for p in (ROOT / sub).rglob("*.md"):
            text = p.read_text(encoding="utf-8")
            if re.search(r"/(Users|home)/[a-z]", text) or "C:\\Users" in text:
                offenders.append(str(p))
    assert not offenders, offenders
