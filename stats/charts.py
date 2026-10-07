"""Render growth charts (PNG + SVG) from the collected data."""
from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

from .config import Project  # noqa: E402

# Palette (validated light-mode defaults): surface, ink, series 1 (blue), series 2 (orange)
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e8e7e3"
S1 = "#2a78d6"
S2 = "#eb6834"
S3 = "#1baf7a"
S4 = "#eda100"
SERIES = [S1, S2, S3, S4]

plt.rcParams.update({
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "text.color": INK,
    "axes.labelcolor": INK_2,
    "axes.edgecolor": GRID,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.spines.left": False,
    "axes.grid": True,
    "axes.grid.axis": "y",
    "grid.color": GRID,
    "grid.linewidth": 1,
    "xtick.color": INK_2,
    "ytick.color": INK_2,
    "xtick.major.size": 0,
    "ytick.major.size": 0,
    "legend.frameon": False,
    "svg.hashsalt": "ak-stats",   # deterministic SVG ids so unchanged charts do not churn in git
})


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def _fmt(n: float) -> str:
    n = float(n)
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n/1000:.0f}k"
    if n >= 1_000:
        return f"{n/1000:.1f}k"
    return f"{int(n)}"


def _cumulative(stamps: list[str]) -> tuple[list[dt.date], list[int]]:
    days = sorted(dt.datetime.fromisoformat(s.replace("Z", "+00:00")).date() for s in stamps)
    if not days:
        return [], []
    xs, ys = [], []
    count = 0
    cur = days[0]
    i = 0
    last = max(days[-1], dt.date.today())
    while cur <= last:
        while i < len(days) and days[i] <= cur:
            i += 1
            count += 1
        xs.append(cur)
        ys.append(count)
        cur += dt.timedelta(days=1)
    return xs, ys


def _finish(fig, ax, title: str, subtitle: str, out: Path) -> None:
    ax.set_title(title, loc="left", fontsize=14, fontweight="bold", pad=22, color=INK)
    ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=10.5, color=INK_2, va="bottom")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    for label in ax.get_xticklabels():
        label.set_fontsize(9.5)
    ax.tick_params(axis="x", which="major", length=0)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out.with_suffix(".png"), dpi=160)
    fig.savefig(out.with_suffix(".svg"), metadata={"Date": None})
    plt.close(fig)


def _line(ax, xs, ys, color, label=None, direct_label=True):
    ax.plot(xs, ys, color=color, linewidth=2, label=label, solid_capstyle="round")
    ax.fill_between(xs, ys, color=color, alpha=0.08, linewidth=0)
    if direct_label and xs:
        ax.plot(xs[-1], ys[-1], "o", color=color, markersize=6, markeredgecolor=SURFACE, markeredgewidth=2)
        ax.annotate(_fmt(ys[-1]), (xs[-1], ys[-1]), xytext=(8, 0), textcoords="offset points",
                    va="center", fontsize=11, fontweight="bold", color=INK)


def chart_cumulative(p: Project, file: str, column: str, title: str, out_name: str, color: str = S1) -> int | None:
    stamps = [r[column] for r in _read(p.data_dir / file)]
    xs, ys = _cumulative(stamps)
    if not xs:
        return None
    fig, ax = plt.subplots(figsize=(9, 4.2))
    _line(ax, xs, ys, color)
    ax.set_ylim(0, max(ys) * 1.12)
    ax.set_xlim(xs[0], xs[-1] + dt.timedelta(days=max(7, len(xs) // 12)))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: _fmt(v)))
    last30 = ys[-1] - (ys[-31] if len(ys) > 31 else 0)
    _finish(fig, ax, title, f"{ys[-1]:,} total   ·   +{last30:,} in the last 30 days", p.charts_dir / out_name)
    return ys[-1]


def chart_contributors(p: Project) -> int | None:
    rows = _read(p.data_dir / "commits_weekly.csv")
    if not rows:
        return None
    xs = [dt.date.fromisoformat(r["week"]) for r in rows]
    ys = [int(r["total_contributors"]) for r in rows]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.step(xs, ys, where="post", color=S3, linewidth=2)
    ax.fill_between(xs, ys, step="post", color=S3, alpha=0.08, linewidth=0)
    ax.plot(xs[-1], ys[-1], "o", color=S3, markersize=6, markeredgecolor=SURFACE, markeredgewidth=2)
    ax.annotate(str(ys[-1]), (xs[-1], ys[-1]), xytext=(8, 0), textcoords="offset points", va="center",
                fontsize=11, fontweight="bold", color=INK)
    ax.set_ylim(0, max(ys) * 1.15)
    ax.set_xlim(xs[0], xs[-1] + dt.timedelta(days=14))
    new_quarter = sum(int(r["new_contributors"]) for r in rows[-13:])
    _finish(fig, ax, "Contributors", f"{ys[-1]} distinct commit authors   ·   {new_quarter} new in the last 13 weeks",
            p.charts_dir / "contributors")
    return ys[-1]


def chart_commits(p: Project) -> None:
    rows = _read(p.data_dir / "commits_weekly.csv")
    if not rows:
        return
    xs = [dt.date.fromisoformat(r["week"]) for r in rows]
    ys = [int(r["commits"]) for r in rows]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    # drop the current, partial week from the headline so it doesn't look like a dip
    ax.bar(xs, ys, width=5.5, color=S1, align="edge", linewidth=0)
    ax.set_ylim(0, max(ys) * 1.12)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: _fmt(v)))
    last4 = sum(ys[-5:-1]) if len(ys) > 5 else sum(ys)
    _finish(fig, ax, "Commits per week", f"{sum(ys):,} commits total   ·   {last4:,} in the last 4 full weeks",
            p.charts_dir / "commits_weekly")


def _snapshot_series(p: Project, metric: str) -> tuple[list[dt.date], list[int]]:
    rows = [r for r in _read(p.data_dir / "snapshots.csv") if r["metric"] == metric]
    rows.sort(key=lambda r: r["date"])
    return [dt.date.fromisoformat(r["date"]) for r in rows], [int(float(r["value"])) for r in rows]


def chart_docker_pulls(p: Project) -> int | None:
    series = []
    for i, image in enumerate(p.docker_images[:4]):
        xs, ys = _snapshot_series(p, f"docker_pulls:{image}")
        if xs:
            series.append((image.split("/")[-1], xs, ys, SERIES[i]))
    if not series:
        return None
    _, tys = _snapshot_series(p, "docker_pulls_total")
    total = tys[-1] if tys else sum(ys[-1] for _, _, ys, _ in series)
    first_day = min(xs[0] for _, xs, _, _ in series)
    days_of_history = (dt.date.today() - first_day).days
    out = p.charts_dir / "docker_pulls"

    if days_of_history < 2:
        # Not enough history for a trend yet: show today's totals per image.
        fig, ax = plt.subplots(figsize=(9, 0.5 * len(series) + 1.8))
        names = [n for n, _, _, _ in series][::-1]
        vals = [ys[-1] for _, _, ys, _ in series][::-1]
        ax.barh(names, vals, color=S1, height=0.62, linewidth=0)
        ax.grid(False, axis="y")
        ax.grid(True, axis="x")
        ax.set_axisbelow(True)
        for i, v in enumerate(vals):
            ax.annotate(_fmt(v), (v, i), xytext=(6, 0), textcoords="offset points", va="center", fontsize=10, color=INK)
        ax.set_xlim(0, max(vals) * 1.15)
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: _fmt(v)))
        ax.set_title("Docker Hub pulls", loc="left", fontsize=14, fontweight="bold", pad=22, color=INK)
        ax.text(0, 1.02, f"{total:,} pulls across all images   ·   trend line appears once daily snapshots accumulate",
                transform=ax.transAxes, fontsize=10.5, color=INK_2, va="bottom")
        fig.tight_layout()
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out.with_suffix(".png"), dpi=160)
        fig.savefig(out.with_suffix(".svg"), metadata={"Date": None})
        plt.close(fig)
        return total

    fig, ax = plt.subplots(figsize=(9, 4.2))
    for name, xs, ys, color in series:
        ax.plot(xs, ys, color=color, linewidth=2, label=f"{name}  ·  {_fmt(ys[-1])}", solid_capstyle="round")
    ax.set_ylim(0, ax.get_ylim()[1] * 1.1)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: _fmt(v)))
    ax.legend(loc="upper left", ncol=2, fontsize=9.5)
    ax.set_title("Docker Hub pulls (cumulative)", loc="left", fontsize=14, fontweight="bold", pad=22, color=INK)
    ax.text(0, 1.02, f"{total:,} pulls across all images", transform=ax.transAxes, fontsize=10.5, color=INK_2, va="bottom")
    _date_axis(ax, days_of_history)
    fig.tight_layout()
    fig.savefig(out.with_suffix(".png"), dpi=160)
    fig.savefig(out.with_suffix(".svg"), metadata={"Date": None})
    plt.close(fig)
    return total


def _date_axis(ax, span_days: int) -> None:
    """Readable date ticks for short (daily) or long (monthly) spans."""
    if span_days <= 120:
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=8))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    else:
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.tick_params(axis="x", length=0, labelsize=9.5)


def chart_traffic(p: Project) -> dict[str, int] | None:
    vx, vy = _snapshot_series(p, "views_unique")
    cx, cy = _snapshot_series(p, "clones_unique")
    if not vx and not cx:
        return None
    # The newest day is partial; drop it from the picture.
    today = dt.date.today()
    vx, vy = zip(*[(x, y) for x, y in zip(vx, vy) if x < today]) if vx else ([], [])
    cx, cy = zip(*[(x, y) for x, y in zip(cx, cy) if x < today]) if cx else ([], [])
    fig, ax = plt.subplots(figsize=(9, 4.2))
    if vx:
        ax.plot(list(vx), list(vy), color=S1, linewidth=2, label="Unique visitors", solid_capstyle="round")
    if cx:
        ax.plot(list(cx), list(cy), color=S2, linewidth=2, label="Unique cloners", solid_capstyle="round")
    ax.legend(loc="upper left", ncol=2, fontsize=9.5)
    ax.set_ylim(0, ax.get_ylim()[1] * 1.1)
    days = max(len(vx), len(cx))
    totals = {"views_unique_28d": sum(list(vy)[-28:]), "clones_unique_28d": sum(list(cy)[-28:])}
    sub = f"Last {min(days, 28)} days: {totals['views_unique_28d']:,} unique visitors · {totals['clones_unique_28d']:,} unique cloners"
    ax.set_title("GitHub traffic (daily uniques)", loc="left", fontsize=14, fontweight="bold", pad=22, color=INK)
    ax.text(0, 1.02, sub, transform=ax.transAxes, fontsize=10.5, color=INK_2, va="bottom")
    span = ((max(vx[-1] if vx else cx[-1], cx[-1] if cx else vx[-1])) - min(vx[0] if vx else cx[0], cx[0] if cx else vx[0])).days
    _date_axis(ax, span)
    fig.tight_layout()
    out = p.charts_dir / "traffic"
    fig.savefig(out.with_suffix(".png"), dpi=160)
    fig.savefig(out.with_suffix(".svg"), metadata={"Date": None})
    plt.close(fig)
    return totals


def chart_release_downloads(p: Project) -> None:
    rows = [r for r in _read(p.data_dir / "releases.csv") if r["prerelease"] == "False"]
    if not rows:
        return
    rows = rows[-15:]
    fig, ax = plt.subplots(figsize=(9, 0.32 * len(rows) + 1.8))
    tags = [r["tag"] for r in rows]
    vals = [int(r["downloads"]) for r in rows]
    ax.barh(tags, vals, color=S1, height=0.62, linewidth=0)
    ax.grid(False, axis="y")
    ax.grid(True, axis="x")
    ax.set_axisbelow(True)
    for i, v in enumerate(vals):
        ax.annotate(_fmt(v), (v, i), xytext=(6, 0), textcoords="offset points", va="center", fontsize=10, color=INK)
    ax.set_xlim(0, max(vals) * 1.15)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: _fmt(v)))
    total = sum(int(r["downloads"]) for r in _read(p.data_dir / "releases.csv"))
    ax.set_title("Binary release downloads", loc="left", fontsize=14, fontweight="bold", pad=22, color=INK)
    ax.text(0, 1.02, f"{total:,} downloads across all releases   ·   last {len(rows)} stable releases shown",
            transform=ax.transAxes, fontsize=10.5, color=INK_2, va="bottom")
    fig.tight_layout()
    out = p.charts_dir / "release_downloads"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out.with_suffix(".png"), dpi=160)
    fig.savefig(out.with_suffix(".svg"), metadata={"Date": None})
    plt.close(fig)


def chart_overview(p: Project) -> None:
    """2x2 small multiples for slide decks: stars, forks, contributors, weekly commits."""
    sx, sy = _cumulative([r["starred_at"] for r in _read(p.data_dir / "stars.csv")])
    fx, fy = _cumulative([r["created_at"] for r in _read(p.data_dir / "forks.csv")])
    rows = _read(p.data_dir / "commits_weekly.csv")
    wx = [dt.date.fromisoformat(r["week"]) for r in rows]
    cy = [int(r["total_contributors"]) for r in rows]
    ky = [int(r["commits"]) for r in rows]
    if not sx:
        return
    fig, axes = plt.subplots(2, 2, figsize=(12, 7))
    panels = [
        (axes[0][0], "GitHub stars", sx, sy, S1, "line"),
        (axes[0][1], "Forks", fx, fy, S2, "line"),
        (axes[1][0], "Contributors", wx, cy, S3, "step"),
        (axes[1][1], "Commits per week", wx, ky, S1, "bar"),
    ]
    for ax, title, xs, ys, color, kind in panels:
        if not xs:
            ax.set_visible(False)
            continue
        if kind == "line":
            ax.plot(xs, ys, color=color, linewidth=2)
            ax.fill_between(xs, ys, color=color, alpha=0.08, linewidth=0)
        elif kind == "step":
            ax.step(xs, ys, where="post", color=color, linewidth=2)
            ax.fill_between(xs, ys, step="post", color=color, alpha=0.08, linewidth=0)
        else:
            ax.bar(xs, ys, width=5.5, color=color, align="edge", linewidth=0)
        headline = f"{ys[-1]:,}" if kind != "bar" else f"{sum(ys):,} total"
        ax.set_title(f"{title}  ·  {headline}", loc="left", fontsize=12, fontweight="bold", color=INK)
        ax.set_ylim(0, max(ys) * 1.12)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: _fmt(v)))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
        ax.tick_params(axis="both", labelsize=9)
    fig.suptitle(f"{p.name} growth overview  ·  {dt.date.today():%B %d, %Y}", x=0.02, ha="left",
                 fontsize=14, fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = p.charts_dir / "overview"
    fig.savefig(out.with_suffix(".png"), dpi=160)
    fig.savefig(out.with_suffix(".svg"), metadata={"Date": None})
    plt.close(fig)


def render_project(p: Project) -> dict:
    p.charts_dir.mkdir(parents=True, exist_ok=True)
    summary: dict = {}
    summary["stars"] = chart_cumulative(p, "stars.csv", "starred_at", "GitHub stars", "stars", S1)
    summary["forks"] = chart_cumulative(p, "forks.csv", "created_at", "Forks", "forks", S2)
    summary["contributors"] = chart_contributors(p)
    chart_commits(p)
    summary["docker_pulls_total"] = chart_docker_pulls(p)
    summary["traffic"] = chart_traffic(p)
    chart_release_downloads(p)
    chart_overview(p)
    return summary
