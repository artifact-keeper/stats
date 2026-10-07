"""Collect a daily snapshot of growth metrics for each configured project.

Two kinds of data are written under data/<project>/:

* Event histories that can always be rebuilt from the API (stars.csv, forks.csv,
  releases.csv, commits_weekly.csv). These are regenerated in full on every run.
* snapshots.csv, a long-format (date, metric, value) table for numbers that
  cannot be backfilled (Docker Hub pulls, traffic, release download totals,
  contributor counts). One row per metric per day, upserted so re-runs are safe.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import subprocess
import tempfile
import urllib.request
from collections import Counter, OrderedDict
from pathlib import Path

from .cloudflare import collect_cloudflare
from .config import Project
from .github import GitHub

SNAPSHOT_COLUMNS = ["date", "metric", "value"]


def _write_csv(path: Path, header: list[str], rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def _read_snapshots(path: Path) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    if path.exists():
        with path.open(newline="") as fh:
            for row in csv.DictReader(fh):
                out[(row["date"], row["metric"])] = row["value"]
    return out


def _write_snapshots(path: Path, data: dict[tuple[str, str], str]) -> None:
    rows = sorted(data.items())
    _write_csv(path, SNAPSHOT_COLUMNS, [(d, m, v) for (d, m), v in rows])


# ----------------------------------------------------------------------------
# Event histories
# ----------------------------------------------------------------------------

def collect_stars(gh: GitHub, p: Project) -> list[str]:
    stamps = [s["starred_at"] for s in gh.paginate(f"/repos/{p.github}/stargazers", accept="application/vnd.github.star+json")]
    stamps.sort()
    _write_csv(p.data_dir / "stars.csv", ["starred_at"], [(s,) for s in stamps])
    return stamps


def collect_forks(gh: GitHub, p: Project) -> list[str]:
    stamps = [f["created_at"] for f in gh.paginate(f"/repos/{p.github}/forks", sort="oldest")]
    stamps.sort()
    _write_csv(p.data_dir / "forks.csv", ["created_at"], [(s,) for s in stamps])
    return stamps


def collect_releases(gh: GitHub, p: Project) -> list[dict]:
    rels = []
    for r in gh.paginate(f"/repos/{p.github}/releases"):
        if r.get("draft"):
            continue
        rels.append({
            "tag": r["tag_name"],
            "published_at": r["published_at"],
            "prerelease": r["prerelease"],
            "downloads": sum(a["download_count"] for a in r.get("assets", [])),
        })
    rels.sort(key=lambda r: r["published_at"])
    _write_csv(p.data_dir / "releases.csv", ["tag", "published_at", "prerelease", "downloads"],
               [(r["tag"], r["published_at"], r["prerelease"], r["downloads"]) for r in rels])
    return rels


def _git_log(p: Project, git_dir: Path | None) -> list[tuple[str, str]]:
    """Return (author_date_iso, author_key) for every non-merge commit on the default branch."""
    if git_dir is None:
        tmp = Path(tempfile.mkdtemp(prefix="ak-stats-"))
        subprocess.run(["git", "clone", "--quiet", "--bare", "--filter=blob:none",
                        f"https://github.com/{p.github}.git", str(tmp / "repo.git")], check=True)
        git_dir = tmp / "repo.git"
        ref = "HEAD"
    else:
        ref = "origin/HEAD"
        head = subprocess.run(["git", "--git-dir", str(git_dir), "symbolic-ref", "-q", ref], capture_output=True, text=True)
        if head.returncode != 0:
            ref = "origin/main"
    out = subprocess.run(["git", "--git-dir", str(git_dir), "log", ref, "--no-merges", "--format=%aI%x09%aE"],
                         capture_output=True, text=True, check=True).stdout
    rows = []
    for line in out.splitlines():
        date, _, email = line.partition("\t")
        key = hashlib.sha1(email.strip().lower().encode()).hexdigest()[:12]
        rows.append((date, key))
    return rows


def collect_commits(p: Project, git_dir: Path | None) -> list[dict]:
    """Weekly commit counts and cumulative distinct contributors, from git history."""
    commits = _git_log(p, git_dir)
    commits.sort()
    per_week: "OrderedDict[str, dict]" = OrderedDict()
    seen: set[str] = set()
    for date, author in commits:
        d = dt.datetime.fromisoformat(date).date()
        week = (d - dt.timedelta(days=d.weekday())).isoformat()  # Monday
        row = per_week.setdefault(week, {"week": week, "commits": 0, "new_contributors": 0})
        row["commits"] += 1
        if author not in seen:
            seen.add(author)
            row["new_contributors"] += 1
    total = 0
    rows = []
    for row in per_week.values():
        total += row["new_contributors"]
        row["total_contributors"] = total
        rows.append(row)
    _write_csv(p.data_dir / "commits_weekly.csv", ["week", "commits", "new_contributors", "total_contributors"],
               [(r["week"], r["commits"], r["new_contributors"], r["total_contributors"]) for r in rows])
    return rows


# ----------------------------------------------------------------------------
# Daily snapshot
# ----------------------------------------------------------------------------

def docker_pulls(image: str) -> int | None:
    url = f"https://hub.docker.com/v2/repositories/{image}/"
    req = urllib.request.Request(url, headers={"User-Agent": "ak-stats"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return int(json.load(resp)["pull_count"])
    except Exception:  # noqa: BLE001 - a missing image just yields no data point
        return None


def collect_snapshot(gh: GitHub, p: Project, releases: list[dict], today: str) -> dict[str, int]:
    owner, name = p.github.split("/")
    q = """
    query($owner:String!, $name:String!) {
      repository(owner:$owner, name:$name) {
        stargazerCount forkCount
        watchers { totalCount }
        openIssues: issues(states:OPEN) { totalCount }
        closedIssues: issues(states:CLOSED) { totalCount }
        openPRs: pullRequests(states:OPEN) { totalCount }
        mergedPRs: pullRequests(states:MERGED) { totalCount }
        discussions { totalCount }
      }
    }"""
    r = gh.graphql(q, owner=owner, name=name)["repository"]
    snap: dict[str, int] = {
        "stars": r["stargazerCount"],
        "forks": r["forkCount"],
        "watchers": r["watchers"]["totalCount"],
        "open_issues": r["openIssues"]["totalCount"],
        "closed_issues": r["closedIssues"]["totalCount"],
        "open_prs": r["openPRs"]["totalCount"],
        "merged_prs": r["mergedPRs"]["totalCount"],
        "discussions": r["discussions"]["totalCount"],
        "release_downloads": sum(x["downloads"] for x in releases),
        "releases": sum(1 for x in releases if not x["prerelease"]),
    }
    contributors = sum(1 for _ in gh.paginate(f"/repos/{p.github}/contributors", anon="true"))
    snap["contributors"] = contributors

    for image in p.docker_images:
        pulls = docker_pulls(image)
        if pulls is not None:
            snap[f"docker_pulls:{image}"] = pulls
    docker_total = [v for k, v in snap.items() if k.startswith("docker_pulls:")]
    if docker_total:
        snap["docker_pulls_total"] = sum(docker_total)

    existing = _read_snapshots(p.data_dir / "snapshots.csv")
    for metric, value in snap.items():
        existing[(today, metric)] = str(value)

    # Traffic: 14 daily points, only with push access. Upsert every day in the window
    # so partial "today" numbers get corrected tomorrow.
    traffic_ok = False
    for kind in ("views", "clones"):
        data = gh.try_get(f"/repos/{p.github}/traffic/{kind}")
        if not data:
            continue
        traffic_ok = True
        for point in data[kind]:
            day = point["timestamp"][:10]
            existing[(day, kind)] = str(point["count"])
            existing[(day, f"{kind}_unique")] = str(point["uniques"])
    if traffic_ok:
        for kind, key in (("referrers", "referrer"), ("paths", "path")):
            data = gh.try_get(f"/repos/{p.github}/traffic/popular/{kind}") or []
            _write_csv(p.data_dir / f"traffic_{kind}.csv", [key, "count", "uniques"],
                       [(d[key], d["count"], d["uniques"]) for d in data])

    _write_snapshots(p.data_dir / "snapshots.csv", existing)
    return snap


def collect_project(gh: GitHub, p: Project, git_dir: Path | None = None, today: str | None = None) -> dict[str, int]:
    today = today or dt.date.today().isoformat()
    p.data_dir.mkdir(parents=True, exist_ok=True)
    collect_stars(gh, p)
    collect_forks(gh, p)
    releases = collect_releases(gh, p)
    collect_commits(p, git_dir)
    snap = collect_snapshot(gh, p, releases, today)
    for host, total in collect_cloudflare(p, p.cloudflare_hosts).items():
        snap[f"cf_requests:{host}"] = total
    return snap
