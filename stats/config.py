from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CHARTS_DIR = ROOT / "charts"
BADGES_DIR = ROOT / "badges"


@dataclass
class Project:
    name: str
    github: str
    docker_images: list[str] = field(default_factory=list)
    primary_image: str | None = None
    cloudflare_hosts: list[str] = field(default_factory=list)

    @property
    def data_dir(self) -> Path:
        return DATA_DIR / self.name

    @property
    def charts_dir(self) -> Path:
        return CHARTS_DIR / self.name

    @property
    def badges_dir(self) -> Path:
        return BADGES_DIR / self.name


def load_projects(path: Path = ROOT / "config.toml") -> list[Project]:
    with path.open("rb") as fh:
        raw = tomllib.load(fh)
    return [Project(**p) for p in raw.get("projects", [])]
