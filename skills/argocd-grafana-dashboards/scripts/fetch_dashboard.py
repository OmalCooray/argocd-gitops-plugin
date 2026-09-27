#!/usr/bin/env python3
"""Fetch a Grafana dashboard and normalize its datasource references.

Usage: fetch_dashboard.py <source> [--out PATH] [--relabel OLD=NEW]... [--labels]

  <source> is one of:
    - a grafana.com dashboard id: "12345", or "12345:8" to pin revision 8
    - an https:// URL to a dashboard JSON
    - a local path to a dashboard .json

Prints the normalized dashboard JSON (LF line endings) to stdout, or with
--out writes it to PATH atomically (temp file in the same directory +
os.replace: on any failure PATH is not created or modified and no temp file
is left behind; the directory must already exist). Exits 1 with a stderr
message on fetch failure, invalid JSON, or a dashboard with no Prometheus
datasource; exits 2 with this usage on bad arguments.

  --relabel OLD=NEW  rename label OLD to NEW (whole identifiers only);
                     repeatable
  --labels           print, as a JSON list, the label names the dashboard uses
                     instead of the dashboard; --out is ignored

--labels and --relabel share one scanner, so they cover exactly the same
positions in every expr / query / definition string (string literals are
masked first, so string values are never touched): matchers inside {...};
by / without / on / ignoring / group_left / group_right (...) lists; the last
argument of label_values(<metric>, <label>). In legendFormat strings only
{{ label }} templates are covered. Limits: label_replace / label_join labels
(string literals) and the one-argument label_values(<label>) form are not
covered.

Normalization:
  - remove __inputs, __requires, top-level id, top-level uid
  - ensure a templating variable {name: datasource, type: datasource,
    query: prometheus}
  - rewrite every "datasource" field: "${DS_*}" / a prometheus input name /
    "prometheus" -> "${datasource}"; {"type":"prometheus","uid":...} ->
    {"type":"prometheus","uid":"${datasource}"}; null and non-prometheus
    datasources are left untouched
  - rewrite a bare-string datasource (a uid or name this Grafana will not
    have) on type=query template variables to "${datasource}" (built-in
    "-- Mixed --" / "-- Grafana --" etc. and non-prometheus inputs excepted)
  - add "__source": "<origin>, fetched <YYYY-MM-DD>" (a local file is recorded
    by basename only; a URL or grafana.com origin is kept verbatim)
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import date

GCOM = "https://grafana.com/api/dashboards"
DS_VAR = "datasource"
_DS_INPUT_RE = re.compile(r"^\$\{DS_[A-Z0-9_]+\}$")
_BUILTIN_DS = {"-- mixed --", "-- grafana --", "-- dashboard --", "mixed", "grafana", "dashboard"}
_IDENT = r"[A-Za-z_][A-Za-z0-9_]*"
_NOT_IDENT_BEFORE = r"(?<![A-Za-z0-9_$])"
_BRACES_RE = re.compile(r"\{([^{}]*)\}")
_MATCHER_RE = re.compile(_NOT_IDENT_BEFORE + "(" + _IDENT + r")\s*(?:=~|!~|!=|=)\s*[\"'`]")
_CLAUSE_RE = re.compile(
    _NOT_IDENT_BEFORE + r"(?:by|without|on|ignoring|group_left|group_right)\s*\(([^()]*)\)"
)
_IDENT_RE = re.compile(_NOT_IDENT_BEFORE + "(" + _IDENT + ")")
_LABEL_VALUES_RE = re.compile(_NOT_IDENT_BEFORE + r"label_values\s*\(")
_LEGEND_RE = re.compile(r"\{\{\s*(" + _IDENT + r")\s*\}\}")
_QUERY_KEYS = ("expr", "query", "definition")
_LEGEND_KEY = "legendFormat"


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


def _non_prom_input_names(dash: dict) -> set[str]:
    return {
        i["name"]
        for i in dash.get("__inputs", [])
        if i.get("type") == "datasource"
        and i.get("pluginId") != "prometheus"
        and i.get("name")
    }


def _iter_queries(node):
    """Yield (container, key, text) for every expr/query/definition/legendFormat string."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in _QUERY_KEYS + (_LEGEND_KEY,) and isinstance(value, str):
                yield node, key, value
            else:
                yield from _iter_queries(value)
    elif isinstance(node, list):
        for value in node:
            yield from _iter_queries(value)


def _mask(text: str) -> str:
    """Blank the inside of "...", '...' and `...` literals (same length), honouring
    backslash escapes, so braces/identifiers in strings are invisible to the scanner."""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c not in "\"'`":
            out.append(c)
            i += 1
            continue
        j = i + 1
        while j < n and text[j] != c:
            j += 2 if (text[j] == "\\" and c != "`") else 1
        j = min(j, n)
        out.append(c + " " * (j - i - 1) + (c if j < n else ""))
        i = j + 1
    return "".join(out)


def _label_positions(key: str, text: str) -> list[tuple[int, int, str]]:
    """Return sorted (start, end, name) spans of label names in one query string.

    Shared by used_labels() and relabel() so --labels and --relabel agree.
    Covered: legendFormat "{{ label }}" templates; and in PromQL (expr/query/
    definition, scanned on a string-masked copy): matchers inside {...},
    by/without/on/ignoring/group_left/group_right (...) lists, and the last
    argument of label_values(<metric>, <label>). NOT covered: label_replace /
    label_join destination and source labels (they are string literals), and the
    single-argument label_values(<label>) form (indistinguishable from a metric).
    """
    if key == _LEGEND_KEY:
        return [(m.start(1), m.end(1), m.group(1)) for m in _LEGEND_RE.finditer(text)]
    masked = _mask(text)
    spans: dict[int, tuple[int, int, str]] = {}
    for brace in _BRACES_RE.finditer(masked):
        for m in _MATCHER_RE.finditer(brace.group(1)):
            start = brace.start(1) + m.start(1)
            spans[start] = (start, brace.start(1) + m.end(1), m.group(1))
    for clause in _CLAUSE_RE.finditer(masked):
        for m in _IDENT_RE.finditer(clause.group(1)):
            start = clause.start(1) + m.start(1)
            spans[start] = (start, clause.start(1) + m.end(1), m.group(1))
    for lv in _LABEL_VALUES_RE.finditer(masked):
        depth, last_comma, i = 1, None, lv.end()
        while i < len(masked) and depth:
            ch = masked[i]
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            elif ch == "," and depth == 1:
                last_comma = i
            i += 1
        if last_comma is not None and depth == 0:
            m = re.fullmatch(r"(\s*)(" + _IDENT + r")\s*", masked[last_comma + 1 : i - 1])
            if m:
                start = last_comma + 1 + m.start(2)
                spans[start] = (start, last_comma + 1 + m.end(2), m.group(2))
    return sorted(spans.values())


def used_labels(dash: dict) -> set[str]:
    return {name for _, key, text in _iter_queries(dash) for _, _, name in _label_positions(key, text)}


def relabel(dash: dict, mapping: dict[str, str]) -> int:
    """Rename labels, only at the positions _label_positions() reports (whole
    identifiers). Returns the number of strings changed."""
    count = 0
    for node, key, text in list(_iter_queries(dash)):
        new = text
        for start, end, name in reversed(_label_positions(key, text)):
            if name in mapping:
                new = new[:start] + mapping[name] + new[end:]
        if new != text:
            node[key] = new
            count += 1
    return count


def _source_label(origin: str) -> str:
    if origin.startswith(("http://", "https://", "grafana.com/")):
        return origin
    return re.split(r"[\\/]", origin)[-1] or origin  # local file: basename only


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
    other_inputs = _non_prom_input_names(dash)
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
            # resolve to the org's default datasource on load — without this the
            # variable is unset and every panel renders "No data"
            "current": {"text": "default", "value": "default"},
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

    # A bare-string uid/name on a query variable (which _fix_ds does not know
    # about) points at a datasource this Grafana will not have.
    for var in tlist:
        if not isinstance(var, dict) or var.get("type") != "query":
            continue
        ds = var.get("datasource")
        if (
            isinstance(ds, str)
            and not ds.startswith("${")
            and ds.lower() not in _BUILTIN_DS
            and ds not in other_inputs
        ):
            var["datasource"] = "${%s}" % DS_VAR
            rewrites += 1

    if rewrites == 0 and not had_ds_var:
        raise DashboardError(
            "no Prometheus datasource references found - not a fit for this plugin"
        )
    dash["__source"] = f"{_source_label(origin)}, fetched {date.today().isoformat()}"
    return dash


class _UsageError(Exception):
    pass


def _parse(argv: list[str]):
    """Return (source, out, labels_only, mapping); flags may precede or follow the source."""
    src, out, labels_only, mapping = None, None, False, {}
    args = iter(argv[1:])
    for a in args:
        if a == "--out":
            out = next(args, None)
            if not out:
                raise _UsageError("--out needs a path")
        elif a == "--labels":
            labels_only = True
        elif a == "--relabel":
            old, eq, new = next(args, "").partition("=")
            if not (eq and old and new):
                raise _UsageError("--relabel needs OLD=NEW")
            mapping[old] = new
        elif a.startswith("--") or src is not None:
            raise _UsageError(f"unexpected argument: {a}")
        else:
            src = a
    if src is None:
        raise _UsageError("missing <source>")
    return src, out, labels_only, mapping


def _write_atomic(path: str, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def main(argv: list[str]) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    except (AttributeError, ValueError):
        pass
    try:
        src, out, labels_only, mapping = _parse(argv)
    except _UsageError as exc:
        sys.stderr.write(f"error: {exc}\n\n{__doc__}")
        return 2
    if out and not labels_only:
        directory = os.path.dirname(os.path.abspath(out))
        if not os.path.isdir(directory):
            sys.stderr.write(f"error: output directory does not exist: {directory}\n")
            return 1
    try:
        dash, origin = load(src)
        dash = normalize(dash, origin)
        relabel(dash, mapping)
    except (urllib.error.URLError, OSError, json.JSONDecodeError, KeyError) as exc:
        sys.stderr.write(f"error: could not load dashboard: {exc}\n")
        return 1
    except DashboardError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1
    if labels_only:
        sys.stdout.write(json.dumps(sorted(used_labels(dash))) + "\n")
        return 0
    text = json.dumps(dash, indent=2, ensure_ascii=False) + "\n"
    if out is None:
        sys.stdout.write(text)
        return 0
    try:
        _write_atomic(out, text)
    except OSError as exc:
        sys.stderr.write(f"error: could not write {out}: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
