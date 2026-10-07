"""Generate README.md, latest.json and shields.io endpoint badges from the data."""
from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path

from .config import ROOT, Project

RAW = "https://raw.githubusercontent.com/artifact-keeper/stats/main"


def _latest_snapshot(p: Project) -> dict[str, int]:
    path = p.data_dir / "snapshots.csv"
    latest: dict[str, tuple[str, int]] = {}
    if not path.exists():
        return {}
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            d, m, v = row["date"], row["metric"], int(float(row["value"]))
            if m not in latest or d > latest[m][0]:
                latest[m] = (d, v)
    return {m: v for m, (_, v) in latest.items()}


def _delta(p: Project, metric: str, days: int) -> int | None:
    path = p.data_dir / "snapshots.csv"
    if not path.exists():
        return None
    cutoff = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    rows = sorted((r["date"], int(float(r["value"]))) for r in csv.DictReader(path.open(newline="")) if r["metric"] == metric)
    if len(rows) < 2:
        return None
    older = [v for d, v in rows if d <= cutoff]
    if not older:
        return None
    return rows[-1][1] - older[-1]


def _sum_window(p: Project, metric: str, days: int) -> int | None:
    path = p.data_dir / "snapshots.csv"
    if not path.exists():
        return None
    today = dt.date.today()
    cutoff = (today - dt.timedelta(days=days)).isoformat()
    vals = [int(float(r["value"])) for r in csv.DictReader(path.open(newline=""))
            if r["metric"] == metric and cutoff < r["date"] < today.isoformat()]
    return sum(vals) if vals else None


def _fmt(n: int | None) -> str:
    return "n/a" if n is None else f"{n:,}"


def _badge(label: str, value: str, color: str = "2a78d6") -> dict:
    return {"schemaVersion": 1, "label": label, "message": value, "color": color}


def _short(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1000:.1f}k".replace(".0k", "k")
    return str(n)


def write_badges(p: Project, snap: dict[str, int]) -> None:
    p.badges_dir.mkdir(parents=True, exist_ok=True)
    badges: dict[str, dict] = {}
    if "docker_pulls_total" in snap:
        badges["docker-pulls-total"] = _badge("docker pulls", _short(snap["docker_pulls_total"]))
    if "contributors" in snap:
        badges["contributors"] = _badge("contributors", str(snap["contributors"]))
    v28 = _sum_window(p, "views_unique", 28)
    if v28 is not None:
        badges["unique-visitors-28d"] = _badge("unique visitors (28d)", _short(v28))
    c28 = _sum_window(p, "clones_unique", 28)
    if c28 is not None:
        badges["unique-cloners-28d"] = _badge("unique cloners (28d)", _short(c28))
    if "release_downloads" in snap:
        badges["release-downloads"] = _badge("release downloads", _short(snap["release_downloads"]))
    for name, body in badges.items():
        (p.badges_dir / f"{name}.json").write_text(json.dumps(body) + "\n")


def project_section(p: Project, snap: dict[str, int]) -> str:
    c = f"{RAW}/charts/{p.name}"
    rows = [
        ("GitHub stars", snap.get("stars"), _delta(p, "stars", 30)),
        ("Forks", snap.get("forks"), _delta(p, "forks", 30)),
        ("Contributors", snap.get("contributors"), _delta(p, "contributors", 30)),
        ("Docker Hub pulls (all images)", snap.get("docker_pulls_total"), _delta(p, "docker_pulls_total", 30)),
    ]
    if p.primary_image:
        rows.append((f"Docker Hub pulls (`{p.primary_image.split('/')[-1]}`)", snap.get(f"docker_pulls:{p.primary_image}"),
                     _delta(p, f"docker_pulls:{p.primary_image}", 30)))
    rows += [
        ("Binary release downloads", snap.get("release_downloads"), _delta(p, "release_downloads", 30)),
        ("Stable releases shipped", snap.get("releases"), _delta(p, "releases", 30)),
        ("Merged pull requests", snap.get("merged_prs"), _delta(p, "merged_prs", 30)),
        ("Closed issues", snap.get("closed_issues"), _delta(p, "closed_issues", 30)),
        ("Discussions", snap.get("discussions"), _delta(p, "discussions", 30)),
        ("Unique visitors, last 28 days", _sum_window(p, "views_unique", 28), None),
        ("Unique git cloners, last 28 days", _sum_window(p, "clones_unique", 28), None),
    ]
    table = ["| Metric | Now | 30-day change |", "|---|---:|---:|"]
    for label, now, delta in rows:
        d = "" if delta is None else (f"+{delta:,}" if delta >= 0 else f"{delta:,}")
        table.append(f"| {label} | {_fmt(now)} | {d} |")

    badge_lines = []
    for name in sorted(x.stem for x in p.badges_dir.glob("*.json")) if p.badges_dir.exists() else []:
        url = f"https://img.shields.io/endpoint?url={RAW}/badges/{p.name}/{name}.json"
        badge_lines.append(f"![{name}]({url})")

    return f"""## {p.name}

Repository: [{p.github}](https://github.com/{p.github})

{chr(10).join(table)}

30-day change needs 30 days of snapshots; it fills in as history accumulates.

{' '.join(badge_lines)}

![Growth overview]({c}/overview.png)

![Where traffic comes from]({c}/countries.png)

**Where is the community?** A spinning globe of stargazers, forkers and contributors by self-reported
GitHub location: [artifact-keeper.github.io/stats/site](https://artifact-keeper.github.io/stats/site/?project={p.name}).
Country totals are in [`data/{p.name}/countries.csv`](data/{p.name}/countries.csv).

<details>
<summary>Individual charts</summary>

![GitHub stars]({c}/stars.png)
![Forks]({c}/forks.png)
![Contributors]({c}/contributors.png)
![Commits per week]({c}/commits_weekly.png)
![Docker Hub pulls]({c}/docker_pulls.png)
![GitHub traffic]({c}/traffic.png)
![Release downloads]({c}/release_downloads.png)

</details>
"""


def write_readme(projects: list[Project]) -> None:
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sections = []
    latest_all: dict[str, dict] = {}
    for p in projects:
        snap = _latest_snapshot(p)
        latest_all[p.name] = snap
        write_badges(p, snap)
        sections.append(project_section(p, snap))
    body = f"""# OSS growth stats

Adoption and community metrics for Artifact Keeper open-source projects, collected daily by
[a GitHub Actions workflow](.github/workflows/update.yml) and committed back to this repo.
Charts and numbers below regenerate on every run.

Last updated: **{now}**

Data lives in [`data/`](data/) as plain CSV so it can be dropped into a spreadsheet or deck.
Chart images are in [`charts/`](charts/) as PNG and SVG. Machine-readable latest numbers are in
[`latest.json`](latest.json), and [`badges/`](badges/) holds shields.io endpoint badges for metrics
shields cannot compute on its own.

{chr(10).join(sections)}
## Adding a project

Add a `[[projects]]` block to [`config.toml`](config.toml) with the GitHub repo and any Docker Hub
images, then run the workflow. Traffic (views, clones) needs the `STATS_TOKEN` secret to have push
access to that repo; everything else works with public API access.

## Running locally

```bash
uv sync
uv run ak-stats all            # collect + charts + readme
uv run ak-stats charts         # re-render charts from existing data
```
"""
    (ROOT / "README.md").write_text(body)
    (ROOT / "latest.json").write_text(json.dumps({"updated": now, "projects": latest_all}, indent=2) + "\n")
