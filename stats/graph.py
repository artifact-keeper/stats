"""GraphQL fetchers for public repo history.

Used instead of the REST endpoints because the Actions GITHUB_TOKEN cannot call
several REST endpoints on repos outside the workflow's own repo, and anonymous
REST is refused from GitHub-hosted runners. GraphQL reads of public data work
with any token.
"""
from __future__ import annotations

from dataclasses import dataclass

from .github import GitHub


@dataclass
class Person:
    login: str
    location: str | None


def _owner_name(repo: str) -> tuple[str, str]:
    owner, name = repo.split("/")
    return owner, name


def stargazers(gh: GitHub, repo: str) -> list[tuple[str, Person]]:
    owner, name = _owner_name(repo)
    q = """
    query($owner:String!, $name:String!, $after:String) {
      repository(owner:$owner, name:$name) {
        stargazers(first:100, after:$after, orderBy:{field:STARRED_AT, direction:ASC}) {
          pageInfo { hasNextPage endCursor }
          edges { starredAt node { login location } }
        }
      }
    }"""
    out: list[tuple[str, Person]] = []
    after = None
    while True:
        conn = gh.graphql(q, owner=owner, name=name, after=after)["repository"]["stargazers"]
        out += [(e["starredAt"], Person(e["node"]["login"], e["node"].get("location"))) for e in conn["edges"]]
        if not conn["pageInfo"]["hasNextPage"]:
            return out
        after = conn["pageInfo"]["endCursor"]


def forks(gh: GitHub, repo: str) -> list[tuple[str, Person]]:
    owner, name = _owner_name(repo)
    q = """
    query($owner:String!, $name:String!, $after:String) {
      repository(owner:$owner, name:$name) {
        forks(first:100, after:$after, orderBy:{field:CREATED_AT, direction:ASC}) {
          pageInfo { hasNextPage endCursor }
          nodes { createdAt owner { login ... on User { location } ... on Organization { location } } }
        }
      }
    }"""
    out: list[tuple[str, Person]] = []
    after = None
    while True:
        conn = gh.graphql(q, owner=owner, name=name, after=after)["repository"]["forks"]
        out += [(n["createdAt"], Person(n["owner"]["login"], n["owner"].get("location"))) for n in conn["nodes"]]
        if not conn["pageInfo"]["hasNextPage"]:
            return out
        after = conn["pageInfo"]["endCursor"]


def releases(gh: GitHub, repo: str) -> list[dict]:
    owner, name = _owner_name(repo)
    q = """
    query($owner:String!, $name:String!, $after:String) {
      repository(owner:$owner, name:$name) {
        releases(first:50, after:$after, orderBy:{field:CREATED_AT, direction:ASC}) {
          pageInfo { hasNextPage endCursor }
          nodes { tagName publishedAt isPrerelease isDraft releaseAssets(first:100) { nodes { downloadCount } } }
        }
      }
    }"""
    out: list[dict] = []
    after = None
    while True:
        conn = gh.graphql(q, owner=owner, name=name, after=after)["repository"]["releases"]
        for n in conn["nodes"]:
            if n["isDraft"] or not n["publishedAt"]:
                continue
            out.append({"tag": n["tagName"], "published_at": n["publishedAt"], "prerelease": n["isPrerelease"],
                        "downloads": sum(a["downloadCount"] for a in n["releaseAssets"]["nodes"])})
        if not conn["pageInfo"]["hasNextPage"]:
            out.sort(key=lambda r: r["published_at"])
            return out
        after = conn["pageInfo"]["endCursor"]


def contributors(gh: GitHub, repo: str) -> list[Person]:
    """Distinct commit authors on the default branch that map to a GitHub account."""
    owner, name = _owner_name(repo)
    q = """
    query($owner:String!, $name:String!, $after:String) {
      repository(owner:$owner, name:$name) {
        defaultBranchRef { target { ... on Commit {
          history(first:100, after:$after) {
            pageInfo { hasNextPage endCursor }
            nodes { author { user { login location } } }
          } } } }
      }
    }"""
    seen: dict[str, Person] = {}
    after = None
    while True:
        hist = gh.graphql(q, owner=owner, name=name, after=after)["repository"]["defaultBranchRef"]["target"]["history"]
        for n in hist["nodes"]:
            u = (n.get("author") or {}).get("user")
            if u and u["login"] not in seen:
                seen[u["login"]] = Person(u["login"], u.get("location"))
        if not hist["pageInfo"]["hasNextPage"]:
            return list(seen.values())
        after = hist["pageInfo"]["endCursor"]
