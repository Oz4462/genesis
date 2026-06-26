#!/usr/bin/env python3
"""find_islands.py — reachability / island analysis for the GENESIS ``gen`` package.

Why this exists: the codebase grew ~45 "island" modules — real, tested code that no
production path ever calls. Green tests give them false liveness. This tool finds them
mechanically so STATUS.md (and a future CI gate) can never lose track again.

It classifies every module under ``src/gen`` as exactly one of:

  WIRED   reachable (via a real import chain) from a product entry point
          (``gen.cli`` / ``gen.web.app`` / ``gen.web.__main__``).
  SCRIPT  not WIRED, but has its own ``if __name__ == "__main__"`` — a runnable
          standalone tool/experiment (not part of the pipeline, but not dead).
  ISLAND  not WIRED, not a SCRIPT: real code with no production caller. Sub-tagged:
            facade-only  imported ONLY by package __init__ re-exports (false liveness)
            test-only    imported ONLY by tests/
            orphan       imported by nobody at all
            transitive   imported only by other islands

  (``__init__`` / ``__main__`` package files are INFRA and excluded from the verdict.)

Accuracy notes:
  * Uses ``ast`` (not regex). Resolves absolute + relative imports.
  * FOLLOWS ``__init__`` re-exports to the real source module, so a symbol genuinely
    used through a package facade counts as usage — but a symbol that is *only*
    re-exported and never consumed (e.g. ``map_to_designer_spec``) stays an island.
  * Tests NEVER count as "wired" (the whole point: tested-but-uncalled = island).
  * Limitation: static analysis. Misses ``importlib.import_module(...)`` / fully
    dynamic dispatch. If you add such a path, annotate the module in STATUS.md.

Usage:
  python scripts/find_islands.py            # human-readable report
  python scripts/find_islands.py --json     # machine-readable (for gen_status.py / CI)
  python scripts/find_islands.py --islands  # just island dotted-names, one per line
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
PKG = SRC / "gen"
TESTS = ROOT / "tests"
SCRIPTS = ROOT / "scripts"

PIPELINE_ENTRIES = ("gen.cli", "gen.web.app", "gen.web.__main__", "gen.__main__")


def _modname(path: Path) -> str:
    return ".".join(path.relative_to(SRC).with_suffix("").parts)


def _iter_py(base: Path):
    if not base.exists():
        return
    for p in sorted(base.rglob("*.py")):
        if "__pycache__" not in p.parts:
            yield p


def _parse(path: Path):
    """Return (list_of_import_records, has_main_block). Records: (level, module, names)."""
    records: list[tuple[int, str | None, list[str]]] = []
    has_main = False
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return records, has_main
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            t = node.test
            if isinstance(t, ast.Compare) and isinstance(t.left, ast.Name) and t.left.id == "__name__":
                has_main = True
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] == "gen":
                    records.append((0, a.name, []))
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative
                records.append((node.level, node.module, [a.name for a in node.names]))
            elif node.module and node.module.split(".")[0] == "gen":  # absolute gen.*
                records.append((0, node.module, [a.name for a in node.names]))
    return records, has_main


def analyze() -> dict:
    modules: dict[str, Path] = {_modname(p): p for p in _iter_py(PKG)}
    parsed = {m: _parse(p) for m, p in modules.items()}
    has_main = {m for m, (_, mb) in parsed.items() if mb}

    def is_pkg(dotted: str) -> bool:
        return f"{dotted}.__init__" in modules

    # Build each package's re-export map: exported_name -> source module (from __init__ relative imports)
    export_map: dict[str, dict[str, str]] = {}
    for m, (recs, _) in parsed.items():
        if not m.endswith(".__init__"):
            continue
        pkg = m[: -len(".__init__")]
        owner_parts = m.split(".")
        emap = export_map.setdefault(pkg, {})
        for level, module, names in recs:
            if level:  # from .sub import a, b  /  from . import a
                base = owner_parts[:-level]
                src = ".".join(base + (module.split(".") if module else []))
                for n in names:
                    cand = src if module else f"{base and '.'.join(base)}.{n}"
                    target = cand if cand in modules else (src if src in modules else None)
                    if target:
                        emap[n] = target

    def resolve_one(owner: str, level: int, module: str | None, name: str | None) -> str | None:
        """Resolve a single imported thing to a real (non-__init__) module, or None."""
        if level:  # relative
            base = owner.split(".")[:-level]
            if not base:
                return None
            stem = ".".join(base + (module.split(".") if module else []))
        else:
            stem = module or ""
        # candidates: stem.name (submodule) → stem (module) → facade re-export → stem itself a pkg
        cands = []
        if name:
            cands.append(f"{stem}.{name}")
        cands.append(stem)
        for c in cands:
            if c in modules and not c.endswith(".__init__"):
                return c
        # facade: importing NAME from a package that re-exports it
        if name and is_pkg(stem) and name in export_map.get(stem, {}):
            return export_map[stem][name]
        # importing NAME from a package where NAME is a submodule
        if name and f"{stem}.{name}.__init__" in modules:
            return f"{stem}.{name}"  # sub-package; treat as used
        return None

    def edges_from(owner: str, recs) -> set[str]:
        out: set[str] = set()
        for level, module, names in recs:
            targets: set[str] = set()
            if names:
                for n in names:
                    t = resolve_one(owner, level, module, n)
                    if t:
                        targets.add(t)
            else:
                t = resolve_one(owner, level, module, None)
                if t:
                    targets.add(t)
            out |= targets
        out.discard(owner)
        return out

    # Usage graph among real (non-__init__) modules
    edges: dict[str, set[str]] = {}
    importers: dict[str, set[str]] = {m: set() for m in modules}
    for m, (recs, _) in parsed.items():
        tgts = edges_from(m, recs)
        edges[m] = tgts
        for t in tgts:
            importers.setdefault(t, set()).add(m)

    # External importers (diagnostic only; tests never => wired)
    def external_importers(base: Path) -> dict[str, set[str]]:
        res: dict[str, set[str]] = {m: set() for m in modules}
        for p in _iter_py(base):
            recs, _ = _parse(p)
            for t in edges_from("", recs):  # owner "" => only absolute gen.* resolve
                res.setdefault(t, set()).add(f"{base.name}/{p.name}")
        return res

    test_importers = external_importers(TESTS)
    script_importers = external_importers(SCRIPTS)

    # Reachability from pipeline entries over the usage graph (NOT through __init__, NOT via tests)
    entries = {e for e in PIPELINE_ENTRIES if e in modules}
    reachable: set[str] = set()
    stack = list(entries)
    while stack:
        cur = stack.pop()
        if cur in reachable:
            continue
        reachable.add(cur)
        stack.extend(edges.get(cur, ()))

    def real_importers(m: str) -> set[str]:
        return {i for i in importers.get(m, set()) if not i.endswith(".__init__")}

    result_modules = []
    for m in sorted(modules):
        leaf = m.rsplit(".", 1)[-1]
        if leaf in ("__init__", "__main__"):
            kind, tag = "INFRA", ""
        elif m in reachable:
            kind, tag = "WIRED", ""
        elif m in has_main:
            kind, tag = "SCRIPT", ""
        else:
            kind = "ISLAND"
            ri = real_importers(m)
            init_imp = {i for i in importers.get(m, set()) if i.endswith(".__init__")}
            if ri:
                tag = "transitive"  # used by real modules that are themselves not wired
            elif init_imp:
                tag = "facade-only"
            elif test_importers.get(m):
                tag = "test-only"
            else:
                tag = "orphan"
        result_modules.append({
            "module": m,
            "kind": kind,
            "tag": tag,
            "has_main": m in has_main,
            "importers": sorted(real_importers(m)),
            "facade_importers": sorted(i for i in importers.get(m, set()) if i.endswith(".__init__")),
            "used_by_scripts": sorted(script_importers.get(m, set())),
            "used_by_tests": sorted(test_importers.get(m, set())),
        })

    counts: dict[str, int] = {}
    for r in result_modules:
        counts[r["kind"]] = counts.get(r["kind"], 0) + 1

    return {
        "totals": {"modules": len(modules), **counts},
        "entries": sorted(entries),
        "modules": result_modules,
        "islands": [r for r in result_modules if r["kind"] == "ISLAND"],
        "scripts": [r["module"] for r in result_modules if r["kind"] == "SCRIPT"],
    }


def _human(data: dict) -> str:
    t = data["totals"]
    lines = [
        "GENESIS island / reachability report",
        "=" * 44,
        f"modules={t['modules']}  WIRED={t.get('WIRED',0)}  SCRIPT={t.get('SCRIPT',0)}  "
        f"ISLAND={t.get('ISLAND',0)}  INFRA={t.get('INFRA',0)}",
        f"entries: {', '.join(data['entries'])}",
        "",
        f"SCRIPTS (runnable standalone, not pipeline-wired) — {len(data['scripts'])}:",
    ]
    for m in data["scripts"]:
        lines.append(f"  · {m}")
    lines.append("")
    lines.append(f"ISLANDS (real code, no production caller) — {len(data['islands'])}:")
    for r in sorted(data["islands"], key=lambda x: (x["tag"], x["module"])):
        who = (", ".join(r["importers"]) if r["importers"]
               else ", ".join(r["facade_importers"]) or "—")
        test = " [has test]" if r["used_by_tests"] else ""
        lines.append(f"  · {r['module']:<46} {r['tag']:<11} via: {who}{test}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Find island modules in src/gen.")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    ap.add_argument("--islands", action="store_true", help="just island dotted-names")
    args = ap.parse_args(argv)
    data = analyze()
    if args.json:
        print(json.dumps(data, indent=2))
    elif args.islands:
        for r in data["islands"]:
            print(r["module"])
    else:
        print(_human(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
