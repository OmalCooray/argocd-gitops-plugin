#!/usr/bin/env python3
"""Render a {{ KEY }} template.

Usage: render_template.py <template> <output> KEY=VALUE [KEY=VALUE ...]

Every {{ KEY }} must be given a value and every KEY=VALUE must be used, else exit 1
and write nothing. Output is UTF-8, LF newlines, no BOM (safe on Windows).
"""
import os
import re
import sys
import tempfile

PLACEHOLDER = re.compile(r"\{\{\s*([A-Z0-9_]+)\s*\}\}")


def render(argv):
    tpl, out, pairs = argv[1], argv[2], argv[3:]
    values = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep:
            sys.stderr.write(f"error: expected KEY=VALUE, got {pair!r}\n")
            return 2
        if key in values:
            sys.stderr.write(f"error: duplicate key: {key}\n")
            return 2
        values[key] = value
    with open(tpl, encoding="utf-8", newline="") as fh:
        text = fh.read().replace("\r\n", "\n")
    needed = set(PLACEHOLDER.findall(text))
    missing, unused = needed - values.keys(), values.keys() - needed
    if missing or unused:
        if missing:
            sys.stderr.write(f"error: no value for: {', '.join(sorted(missing))}\n")
        if unused:
            sys.stderr.write(f"error: unused values: {', '.join(sorted(unused))}\n")
        return 1
    rendered = PLACEHOLDER.sub(lambda m: values[m.group(1)], text)
    directory = os.path.dirname(os.path.abspath(out))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(rendered)
        try:
            os.chmod(tmp, 0o644)
        except OSError:
            pass
        os.replace(tmp, out)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return 0


def main(argv):
    if len(argv) < 3:
        sys.stderr.write(__doc__)
        return 2
    try:
        return render(argv)
    except (OSError, UnicodeDecodeError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
