"""Where are the people who star and fork the project?

GitHub profiles carry a free-text, self-reported ``location``. We collect it for
every stargazer and fork owner, geocode distinct strings through Nominatim (cached
in data/geocode_cache.csv so each string is looked up once), and aggregate to
data/<project>/geo.json for the globe page and a per-country table.
"""
from __future__ import annotations

import csv
import json
import re
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

from .config import DATA_DIR, Project
from .github import GitHub
from . import graph

CACHE = DATA_DIR / "geocode_cache.csv"
CACHE_COLS = ["query", "lat", "lon", "country", "country_code", "place"]
MAX_NEW_GEOCODES_PER_RUN = 400
NOMINATIM = "https://nominatim.openstreetmap.org/search"


JUNK = {
    "earth", "world", "worldwide", "global", "internet", "the internet", "online", "cloud", "the cloud",
    "remote", "everywhere", "nowhere", "somewhere", "home", "localhost", "null", "undefined", "unknown",
    "n/a", "none", "moon", "mars", "/dev/null", "127.0.0.1", "0.0.0.0", "::1", "planet earth", "milky way",
    "universe", "metaverse", "matrix", "the matrix", "cyberspace", "space", "wherever", "anywhere",
}
_IPISH = re.compile(r"^[\d.:/]+$")


def _norm(loc: str) -> str:
    """Normalise a profile location; return '' for strings that are not places."""
    loc = re.sub(r"\s+", " ", loc.strip())
    loc = loc.strip(" ,.;|/-")
    if len(loc) < 2 or _IPISH.match(loc) or loc.lower() in JUNK or not re.search(r"[^\W\d_]", loc):
        return ""
    return loc


def people(gh: GitHub, p: Project) -> tuple[dict[str, str], set[str], set[str], set[str]]:
    """Return (login -> normalised location) plus the stargazer, forker and contributor login sets."""
    locs: dict[str, str] = {}
    stars: set[str] = set()
    forks: set[str] = set()
    contribs: set[str] = set()
    for _, person in graph.stargazers(gh, p.github):
        stars.add(person.login)
        if person.location and _norm(person.location):
            locs[person.login] = _norm(person.location)
    for _, person in graph.forks(gh, p.github):
        forks.add(person.login)
        if person.location and _norm(person.location):
            locs[person.login] = _norm(person.location)
    for person in graph.contributors(gh, p.github):
        contribs.add(person.login)
        if person.location and _norm(person.location):
            locs[person.login] = _norm(person.location)
    return locs, stars, forks, contribs


def _load_cache() -> dict[str, dict]:
    if not CACHE.exists():
        return {}
    with CACHE.open(newline="") as fh:
        return {r["query"]: r for r in csv.DictReader(fh)}


def _save_cache(cache: dict[str, dict]) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    with CACHE.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CACHE_COLS)
        w.writeheader()
        for q in sorted(cache):
            w.writerow({k: cache[q].get(k, "") for k in CACHE_COLS})


PHOTON = "https://photon.komoot.io/api/"


def _empty(query: str) -> dict:
    return {"query": query, "lat": "", "lon": "", "country": "", "country_code": "", "place": ""}


def _get_json(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers={"User-Agent": "ak-stats/0.1 (github.com/artifact-keeper/stats)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except Exception:  # noqa: BLE001
        return None


def geocode_photon(query: str) -> dict | None:
    data = _get_json(PHOTON + "?" + urllib.parse.urlencode({"q": query, "limit": 1, "lang": "en"}), timeout=15)
    feats = (data or {}).get("features") or []
    if not feats:
        return None
    f = feats[0]
    lon, lat = f["geometry"]["coordinates"]
    pr = f.get("properties", {})
    place = pr.get("city") or pr.get("name") or pr.get("state") or pr.get("country") or query
    return {"query": query, "lat": f"{lat:.3f}", "lon": f"{lon:.3f}", "country": pr.get("country", ""),
            "country_code": (pr.get("countrycode") or "").upper(), "place": place}


def geocode_nominatim(query: str) -> dict | None:
    results = _get_json(NOMINATIM + "?" + urllib.parse.urlencode(
        {"q": query, "format": "jsonv2", "limit": 1, "addressdetails": 1, "accept-language": "en"}))
    if not results:
        return None
    r = results[0]
    addr = r.get("address", {})
    return {"query": query, "lat": f"{float(r['lat']):.3f}", "lon": f"{float(r['lon']):.3f}",
            "country": addr.get("country", ""), "country_code": addr.get("country_code", "").upper(),
            "place": r.get("name") or r.get("display_name", "").split(",")[0]}


def geocode(query: str) -> dict:
    """Nominatim first (rate-limited to 1 req/s by the caller), Photon as a fallback."""
    hit = geocode_nominatim(query)
    if hit is None:
        hit = geocode_photon(query)
    return hit or _empty(query)


def ensure_geocoded(queries: set[str]) -> dict[str, dict]:
    cache = _load_cache()
    missing = [q for q in sorted(queries) if q not in cache][:MAX_NEW_GEOCODES_PER_RUN]
    for q in missing:
        cache[q] = geocode(q)
        _save_cache(cache)
        time.sleep(1.1)  # Nominatim usage policy: max 1 request per second
    return cache


def build_geo(gh: GitHub, p: Project) -> dict:
    locs, star_set, fork_set, contrib_set = people(gh, p)
    cache = ensure_geocoded(set(locs.values()))

    # Aggregate to places (lat/lon rounded) and to countries. No logins are written out.
    places: dict[tuple[str, str], dict] = {}
    countries: Counter = Counter()
    country_names: dict[str, str] = {}
    located = 0
    for login, loc in locs.items():
        g = cache.get(loc)
        if not g or not g["lat"]:
            continue
        located += 1
        key = (g["lat"], g["lon"])
        entry = places.setdefault(key, {"lat": float(g["lat"]), "lon": float(g["lon"]), "place": g["place"] or loc,
                                        "country": g["country"], "country_code": g["country_code"],
                                        # True when the profile only named a country, so the point is a centroid, not a city
                                        "country_level": bool(g["country"]) and (g["place"] or "").strip().lower() == g["country"].strip().lower(),
                                        "stargazers": 0, "forkers": 0, "contributors": 0})
        if login in star_set:
            entry["stargazers"] += 1
        if login in fork_set:
            entry["forkers"] += 1
        if login in contrib_set:
            entry["contributors"] += 1
        if g["country_code"]:
            countries[g["country_code"]] += 1
            country_names[g["country_code"]] = g["country"]

    out = {
        "project": p.name,
        "repo": p.github,
        "people_total": len(star_set | fork_set | contrib_set),
        "contributors_total": len(contrib_set),
        "contributors_located": sum(1 for c in contrib_set if c in locs and cache.get(locs[c], {}).get("lat")),
        "people_with_location": len(locs),
        "people_located": located,
        "countries": [{"code": c, "name": country_names[c], "people": n} for c, n in countries.most_common()],
        "places": sorted(places.values(), key=lambda e: -(e["stargazers"] + e["forkers"] + e["contributors"])),
    }
    p.data_dir.mkdir(parents=True, exist_ok=True)
    (p.data_dir / "geo.json").write_text(json.dumps(out, indent=1) + "\n")
    with (p.data_dir / "countries.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["country_code", "country", "people"])
        for c in out["countries"]:
            w.writerow([c["code"], c["name"], c["people"]])
    return out
