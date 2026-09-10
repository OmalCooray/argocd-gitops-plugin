"""Structural checks on the extra-manifest starter templates."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
STARTERS = ROOT / "skills/argocd-extra-manifests/reference/starters"

EXPECTED = {
    "servicemonitor.yaml": "ServiceMonitor",
    "podmonitor.yaml": "PodMonitor",
}


def test_expected_starters_present():
    files = {p.name for p in STARTERS.glob("*.yaml")}
    assert files == set(EXPECTED), files


def _text(name):
    return (STARTERS / name).read_text(encoding="utf-8")


def test_each_starter_is_gated_on_an_enabled_flag():
    for name in EXPECTED:
        t = _text(name)
        assert re.search(r"\{\{-?\s*if\s+\.Values\.\w+\.enabled\s*\}\}", t), name
        assert t.rstrip().endswith("{{- end }}"), name


def test_each_starter_declares_its_kind_matching_the_filename():
    for name, kind in EXPECTED.items():
        assert re.search(rf"^kind:\s*{kind}\s*$", _text(name), re.MULTILINE), name


def test_no_starter_includes_a_subchart_helper():
    # a parent chart cannot call a subchart's named templates
    for name in EXPECTED:
        assert 'include "' not in _text(name), name


def test_each_starter_uses_a_named_port_not_a_number():
    # the port value is passed straight through from .Values.<x>.port (a name)
    for name in EXPECTED:
        t = _text(name)
        assert re.search(r"port:\s*\{\{\s*required[^}]*\.Values\.\w+\.port", t), name


def test_each_starter_has_a_leading_comment_block():
    for name in EXPECTED:
        assert _text(name).startswith("{{- /*"), name
