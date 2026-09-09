"""Validate the plugin manifest and .mcp.json shape."""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_manifest_exists_and_is_json():
    data = load(".claude-plugin/plugin.json")
    assert isinstance(data, dict)


def test_manifest_name_is_kebab_case():
    data = load(".claude-plugin/plugin.json")
    assert data["name"] == "argocd-gitops-plugin"
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", data["name"])


def test_manifest_has_semver_version():
    data = load(".claude-plugin/plugin.json")
    assert re.fullmatch(r"\d+\.\d+\.\d+", data["version"])


def test_manifest_has_description_and_author():
    data = load(".claude-plugin/plugin.json")
    assert data["description"].strip()
    assert data["author"]["name"] == "Omal Cooray"


def test_manifest_declares_no_custom_component_paths():
    # Phase 1 uses only default auto-discovery dirs.
    data = load(".claude-plugin/plugin.json")
    for key in ("commands", "agents", "skills", "hooks"):
        assert key not in data, f"unexpected custom path for {key}"


def test_mcp_json_is_valid_and_argocd_disabled_by_default():
    data = load(".mcp.json")
    assert "argocd" in data["mcpServers"]
    srv = data["mcpServers"]["argocd"]
    # Disabled by default: our convention is the _disabled marker key set true.
    assert srv.get("_disabled") is True
    # No secrets inlined — only ${ENV} references.
    for v in srv.get("env", {}).values():
        assert v.startswith("${") and v.endswith("}")
