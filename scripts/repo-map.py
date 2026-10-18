#!/usr/bin/env python3
"""Bounded source-navigation lookup, without dependencies or private-file reads."""
import argparse
import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def declarations(path):
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        tree = ast.parse(text)
        symbols = [(n.lineno, n.name) for n in tree.body
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
        routes = []
        for n in tree.body:
            for d in getattr(n, "decorator_list", []):
                if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.args:
                    if d.func.attr in {"get", "post", "put", "patch", "delete"} and isinstance(d.args[0], ast.Constant):
                        routes.append((n.lineno, f"{d.func.attr.upper()} {d.args[0].value}"))
        imports = [ast.unparse(n) for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        return symbols + routes, imports
    symbols = [(i, line.strip()[:160]) for i, line in enumerate(text.splitlines(), 1)
               if re.search(r"export (?:class|interface|type|function|const)|path:\s*['\"]", line)]
    return symbols, [line.strip() for line in text.splitlines() if line.startswith("import ")]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--query", required=True, help="Case-insensitive path, symbol or route fragment")
    p.add_argument("--details", action="store_true", help="Include symbols, line numbers and local imports")
    p.add_argument("--limit", type=int, default=12)
    args = p.parse_args()
    query = args.query.lower()
    paths = sorted((ROOT / "backend/app").rglob("*.py")) + sorted((ROOT / "frontend/src/app").rglob("*.ts"))
    found = 0
    for path in paths:
        symbols, imports = declarations(path)
        rel = str(path.relative_to(ROOT))
        matches = [(line, name) for line, name in symbols if query in name.lower()]
        if query not in rel.lower() and not matches:
            continue
        found += 1
        if found > max(1, min(args.limit, 50)):
            continue
        print(rel)
        for line, name in (symbols if args.details else matches)[:18]:
            print(f"  {line}: {name}")
        if args.details:
            for item in imports:
                if "app." in item or "./" in item:
                    print(f"  {item}")
    print(f"{found} matching files. Use --query with a narrower term or --limit to expand.")


if __name__ == "__main__":
    main()
