"""Requests by country for hosts behind Cloudflare, e.g. the install script host.

``curl -fsSL https://get.artifactkeeper.com | bash`` is the documented install path,
so requests to that host, by the visitor's country, are the closest thing to
"installs by region" that exists. Cloudflare keeps this per-request data for a
few days only, so it is snapshotted daily into data/<project>/cf_<host>.csv.

Needs CLOUDFLARE_API_TOKEN (Zone > Analytics > Read) and CLOUDFLARE_ZONE_ID.
Skipped silently when either is missing.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import urllib.request
from pathlib import Path

from .config import Project

CF_GRAPHQL = "https://api.cloudflare.com/client/v4/graphql"

QUERY = """
query($zone: String!, $start: Date!, $end: Date!, $host: String!) {
  viewer {
    zones(filter: {zoneTag: $zone}) {
      httpRequests1dGroups(limit: 10000, filter: {date_geq: $start, date_leq: $end}) {
        dimensions { date }
        sum { countryMap { clientCountryName requests } requests uniques { uniques } }
      }
      byHost: httpRequestsAdaptiveGroups(
        limit: 10000,
        filter: {date_geq: $start, date_leq: $end, clientRequestHTTPHost: $host, requestSource: "eyeball"}
      ) {
        count
        dimensions { date clientCountryName }
      }
    }
  }
}
"""


def _read(path: Path) -> dict[tuple[str, str], int]:
    out: dict[tuple[str, str], int] = {}
    if path.exists():
        with path.open(newline="") as fh:
            for r in csv.DictReader(fh):
                out[(r["date"], r["country"])] = int(r["requests"])
    return out


def _write(path: Path, data: dict[tuple[str, str], int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "country", "requests"])
        for (d, c), n in sorted(data.items()):
            w.writerow([d, c, n])


def collect_cloudflare(p: Project, hosts: list[str], days: int = 7) -> dict[str, int]:
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    zone = os.environ.get("CLOUDFLARE_ZONE_ID")
    if not token or not zone or not hosts:
        return {}
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    totals: dict[str, int] = {}
    for host in hosts:
        body = json.dumps({"query": QUERY, "variables": {"zone": zone, "start": start.isoformat(),
                                                         "end": end.isoformat(), "host": host}}).encode()
        req = urllib.request.Request(CF_GRAPHQL, data=body, method="POST",
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                                              "User-Agent": "ak-stats"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.load(resp)
        if data.get("errors"):
            raise RuntimeError(data["errors"])
        zones = data["data"]["viewer"]["zones"]
        if not zones:
            continue
        z = zones[0]
        path = p.data_dir / f"cf_{host.replace('.', '_')}.csv"
        existing = _read(path)
        # Drop the partial current day, then upsert the window.
        for (d, c) in list(existing):
            if start.isoformat() <= d < end.isoformat():
                existing.pop((d, c))
        for row in z["byHost"]:
            d, c = row["dimensions"]["date"], row["dimensions"]["clientCountryName"] or "??"
            if d >= end.isoformat():
                continue
            existing[(d, c)] = existing.get((d, c), 0) + int(row["count"])
        _write(path, existing)
        totals[host] = sum(existing.values())

        # Whole-zone daily totals (site traffic) as a plain snapshot too.
        zpath = p.data_dir / "cf_zone_daily.csv"
        zdata = _read(zpath)
        for g in z["httpRequests1dGroups"]:
            d = g["dimensions"]["date"]
            if d >= end.isoformat():
                continue
            for cm in g["sum"]["countryMap"]:
                zdata[(d, cm["clientCountryName"])] = int(cm["requests"])
        _write(zpath, zdata)
    return totals
