"""Minimal GitHub REST/GraphQL client on top of urllib (no extra deps)."""
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Iterator

API = "https://api.github.com"


def _token() -> str | None:
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        return tok
    try:
        out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True)
        return out.stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


class GitHub:
    def __init__(self, token: str | None = None):
        self.token = token or _token()

    def _request(self, url: str, accept: str = "application/vnd.github+json", method: str = "GET", body: dict | None = None):
        headers = {"Accept": accept, "User-Agent": "ak-stats", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, headers=headers, method=method, data=data)
        for attempt in range(5):
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return json.loads(resp.read() or b"null"), resp.headers
            except urllib.error.HTTPError as e:
                body = e.read().decode(errors="ignore")
                # 202 = stats being computed; 403/429 = rate limit. Back off and retry.
                if e.code in (202, 429) or (e.code == 403 and "rate limit" in body.lower()):
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"GitHub API {e.code} for {url}: {body[:300]}") from None
        raise RuntimeError(f"GitHub API gave up on {url}")

    def get(self, path: str, **params: Any) -> Any:
        url = f"{API}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data, _ = self._request(url)
        return data

    def paginate(self, path: str, accept: str = "application/vnd.github+json", **params: Any) -> Iterator[Any]:
        params.setdefault("per_page", 100)
        url = f"{API}{path}?{urllib.parse.urlencode(params)}"
        while url:
            data, headers = self._request(url, accept=accept)
            yield from data
            url = None
            for part in (headers.get("Link") or "").split(","):
                if 'rel="next"' in part:
                    url = part[part.find("<") + 1 : part.find(">")]

    def graphql(self, query: str, **variables: Any) -> dict:
        data, _ = self._request(f"{API}/graphql", method="POST", body={"query": query, "variables": variables})
        errors = data.get("errors") or []
        # NOT_FOUND on an aliased field (e.g. a deleted or bot account) still
        # returns data for the other aliases; only fail on real errors.
        fatal = [e for e in errors if e.get("type") != "NOT_FOUND"]
        if fatal or data.get("data") is None:
            raise RuntimeError(errors)
        return data["data"]

    def try_get(self, path: str, **params: Any) -> Any | None:
        """GET that returns None on 403/404 (e.g. traffic without push access)."""
        try:
            return self.get(path, **params)
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                return None
            raise
