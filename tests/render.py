"""Minimal mustache-style renderer: replaces {{ KEY }} with vars[KEY].

Rules:
- {{ KEY }} and {{KEY}} both work (surrounding spaces ignored).
- Every placeholder in the template MUST have a key in vars, else KeyError.
- Values are inserted literally (no escaping — these are YAML/text templates).
"""
from __future__ import annotations
import json
import re
import sys

_PLACEHOLDER = re.compile(r"\{\{\s*([A-Z0-9_]+)\s*\}\}")


def render(template: str, variables: dict) -> str:
    def sub(match: re.Match) -> str:
        key = match.group(1)
        if key not in variables:
            raise KeyError(f"missing template variable: {key}")
        return str(variables[key])

    return _PLACEHOLDER.sub(sub, template)


def placeholders(template: str) -> set[str]:
    return set(_PLACEHOLDER.findall(template))


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: render.py <template-file> <vars.json>", file=sys.stderr)
        return 2
    template = open(argv[1], encoding="utf-8").read()
    variables = json.loads(open(argv[2], encoding="utf-8").read())
    # Force UTF-8 on stdout — templates contain non-ASCII (e.g. "≥") and the
    # default console encoding on Windows (cp1252) cannot encode them.
    sys.stdout.buffer.write(render(template, variables).encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
