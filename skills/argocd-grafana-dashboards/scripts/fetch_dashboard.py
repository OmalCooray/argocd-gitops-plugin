#!/usr/bin/env python3
"""Fetch a Grafana dashboard and normalize its datasource references.

Usage: fetch_dashboard.py <source>

  <source> is one of:
    - a grafana.com dashboard id: "12345", or "12345:8" to pin revision 8
    - an https:// URL to a dashboard JSON
    - a local path to a dashboard .json

Prints the normalized dashboard JSON to stdout. Exits non-zero with a stderr
message on fetch failure, invalid JSON, or a dashboard with no Prometheus
datasource.

Normalization:
  - remove __inputs, __requires, top-level id, top-level uid
  - ensure a templating variable {name: datasource, type: datasource,
    query: prometheus}
  - rewrite every "datasource" field: "${DS_*}" / a prometheus input name /
    "prometheus" -> "${datasource}"; {"type":"prometheus","uid":...} ->
    {"type":"prometheus","uid":"${datasource}"}; null and non-prometheus
    datasources are left untouched
  - add "__source": "<origin>, fetched <YYYY-MM-DD>"
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from datetime import date

GCOM = "https://grafana.com/api/dashboards"
DS_VAR = "datasource"
_DS_INPUT_RE = re.compile(r"^\$\{DS_[A-Z0-9_]+\}$")


class DashboardError(Exception):
    pass


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "argocd-gitops-plugin"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (trusted host)
        return resp.read()


def _unwrap(obj):
    """Grafana HTTP-API exports wrap the dashboard: {"dashboard": {...}, "meta": {...}}."""
    if isinstance(obj, dict) and isinstance(obj.get("dashboard"), dict):
        return obj["dashboard"]
    return obj


def load(source: str) -> tuple[dict, str]:
    """Return (dashboard, origin_label)."""
    if re.fullmatch(r"\d+(:\d+)?", source):
        gid, _, rev = source.partition(":")
        if not rev:
            meta = json.loads(_http_get(f"{GCOM}/{gid}"))
            revision = meta.get("revision")
            if revision is None:
                raise DashboardError(
                    f"grafana.com returned no revision for dashboard {gid}"
                )
            rev = str(revision)
        raw = _http_get(f"{GCOM}/{gid}/revisions/{rev}/download")
        return _unwrap(json.loads(raw)), f"grafana.com/dashboards/{gid} revision {rev}"
    if source.startswith(("http://", "https://")):
        return _unwrap(json.loads(_http_get(source))), source
    with open(source, encoding="utf-8") as fh:
        return _unwrap(json.load(fh)), source


def _prom_input_names(dash: dict) -> set[str]:
    return {
        i["name"]
        for i in dash.get("__inputs", [])
        if i.get("type") == "datasource"
        and i.get("pluginId") == "prometheus"
        and i.get("name")
    }


def _fix_ds(ds, prom_inputs: set[str]):
    if ds is None:
        return ds
    if isinstance(ds, str):
        m = re.fullmatch(r"\$\{(\w+)\}", ds)
        if (
            _DS_INPUT_RE.match(ds)
            or (m and m.group(1) in prom_inputs)
            or ds.lower() == "prometheus"
        ):
            return "${%s}" % DS_VAR
        return ds  # already a var ref, or a non-prometheus named datasource
    if isinstance(ds, dict):
        if ds.get("type") in ("prometheus", None):
            return {"type": "prometheus", "uid": "${%s}" % DS_VAR}
        return ds  # loki / mixed / other — leave it
    return ds


def normalize(dash: dict, origin: str) -> dict:
    prom_inputs = _prom_input_names(dash)
    for key in ("__inputs", "__requires", "id", "uid"):
        dash.pop(key, None)

    tmpl = dash.setdefault("templating", {})
    tlist = tmpl.setdefault("list", [])
    had_ds_var = any(
        isinstance(v, dict) and v.get("name") == DS_VAR for v in tlist
    )
    if not had_ds_var:
        tlist.insert(0, {
            "name": DS_VAR,
            "type": "datasource",
            "query": "prometheus",
            "label": "Datasource",
            "current": {},
            "hide": 0,
            "refresh": 1,
        })

    rewrites = 0

    def walk(node):
        nonlocal rewrites
        if isinstance(node, dict):
            if "datasource" in node:
                fixed = _fix_ds(node["datasource"], prom_inputs)
                if fixed != node["datasource"]:
                    rewrites += 1
                node["datasource"] = fixed
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(dash)
    if rewrites == 0 and not had_ds_var:
        raise DashboardError(
            "no Prometheus datasource references found — not a fit for this plugin"
        )
    dash["__source"] = f"{origin}, fetched {date.today().isoformat()}"
    return dash


def main(argv: list[str]) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    if len(argv) != 2:
        sys.stderr.write(__doc__)
        return 2
    try:
        dash, origin = load(argv[1])
        dash = normalize(dash, origin)
    except (urllib.error.URLError, OSError, json.JSONDecodeError, KeyError) as exc:
        sys.stderr.write(f"error: could not load dashboard: {exc}\n")
        return 1
    except DashboardError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1
    json.dump(dash, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
