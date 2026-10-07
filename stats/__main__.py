from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .charts import render_project
from .collect import collect_project
from .config import load_projects
from .github import GitHub
from .readme import write_readme


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ak-stats", description="Collect growth metrics and render charts")
    ap.add_argument("command", choices=["collect", "charts", "readme", "all"])
    ap.add_argument("--project", help="only this project (name from config.toml)")
    ap.add_argument("--git-dir", type=Path, help="existing .git dir to read commit history from instead of cloning")
    ap.add_argument("--date", help="snapshot date override (YYYY-MM-DD)")
    args = ap.parse_args(argv)

    projects = load_projects()
    if args.project:
        projects = [p for p in projects if p.name == args.project]
        if not projects:
            print(f"unknown project {args.project}", file=sys.stderr)
            return 2

    if args.command in ("collect", "all"):
        gh = GitHub()
        for p in projects:
            snap = collect_project(gh, p, git_dir=args.git_dir, today=args.date)
            print(f"[{p.name}] snapshot: " + ", ".join(f"{k}={v}" for k, v in sorted(snap.items())))
    if args.command in ("charts", "all"):
        for p in projects:
            summary = render_project(p)
            print(f"[{p.name}] charts: {summary}")
    if args.command in ("readme", "all"):
        write_readme(load_projects())
        print("README.md, latest.json and badges written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
