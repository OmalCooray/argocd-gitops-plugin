"""Render each template with fixture vars and compare against golden files."""
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from render import render, placeholders  # noqa: E402

VARS = json.loads((ROOT / "tests/fixtures/podinfo.vars.json").read_text())

CASES = [
    ("templates/Chart.yaml.tmpl", "tests/fixtures/golden/Chart.yaml"),
    ("templates/application.yaml.tmpl", "tests/fixtures/golden/application.yaml"),
    ("templates/root.yaml.tmpl", "tests/fixtures/golden/root.yaml"),
]


@pytest.mark.parametrize("tmpl,golden", CASES)
def test_template_renders_to_golden(tmpl, golden):
    template_text = (ROOT / tmpl).read_text(encoding="utf-8")
    expected = (ROOT / golden).read_text(encoding="utf-8")
    assert render(template_text, VARS) == expected


@pytest.mark.parametrize("tmpl,_golden", CASES)
def test_every_placeholder_has_a_fixture_var(tmpl, _golden):
    template_text = (ROOT / tmpl).read_text(encoding="utf-8")
    missing = placeholders(template_text) - set(VARS)
    assert not missing, f"{tmpl} uses vars with no fixture value: {sorted(missing)}"


TEXT_ONLY = [
    "templates/values.yaml.tmpl",
    "templates/install.sh.tmpl",
    "templates/gitops-README.md.tmpl",
    "templates/gitops-CLAUDE.md.tmpl",
    "templates/CODEOWNERS.tmpl",
]


@pytest.mark.parametrize("tmpl", TEXT_ONLY)
def test_text_template_fully_renders(tmpl):
    template_text = (ROOT / tmpl).read_text(encoding="utf-8")
    out = render(template_text, VARS)
    assert "{{" not in out and "}}" not in out
    missing = placeholders(template_text) - set(VARS)
    assert not missing, f"{tmpl} uses vars with no fixture value: {sorted(missing)}"
