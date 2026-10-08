# OSS growth stats

Adoption and community metrics for Artifact Keeper open-source projects, collected daily by
[a GitHub Actions workflow](.github/workflows/update.yml) and committed back to this repo.
Charts and numbers below regenerate on every run.

Last updated: **2026-10-08 13:38 UTC**

Data lives in [`data/`](data/) as plain CSV so it can be dropped into a spreadsheet or deck.
Chart images are in [`charts/`](charts/) as PNG and SVG. Machine-readable latest numbers are in
[`latest.json`](latest.json), and [`badges/`](badges/) holds shields.io endpoint badges for metrics
shields cannot compute on its own.

## artifact-keeper

Repository: [artifact-keeper/artifact-keeper](https://github.com/artifact-keeper/artifact-keeper)

| Metric | Now | 30-day change |
|---|---:|---:|
| GitHub stars | 1,115 |  |
| Forks | 153 |  |
| Contributors | 73 |  |
| Docker Hub pulls (all images) | 318,368 |  |
| Docker Hub pulls (`backend`) | 116,700 |  |
| Binary release downloads | 2,867 |  |
| Stable releases shipped | 45 |  |
| Merged pull requests | 2,137 |  |
| Closed issues | 1,957 |  |
| Discussions | 62 |  |
| Unique visitors, last 28 days | 2,733 |  |
| Unique git cloners, last 28 days | 1,866 |  |

30-day change needs 30 days of snapshots; it fills in as history accumulates.

![contributors](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/artifact-keeper/stats/main/badges/artifact-keeper/contributors.json) ![docker-pulls-total](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/artifact-keeper/stats/main/badges/artifact-keeper/docker-pulls-total.json) ![release-downloads](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/artifact-keeper/stats/main/badges/artifact-keeper/release-downloads.json) ![unique-cloners-28d](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/artifact-keeper/stats/main/badges/artifact-keeper/unique-cloners-28d.json) ![unique-visitors-28d](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/artifact-keeper/stats/main/badges/artifact-keeper/unique-visitors-28d.json)

![Growth overview](https://raw.githubusercontent.com/artifact-keeper/stats/main/charts/artifact-keeper/overview.png)

![Where traffic comes from](https://raw.githubusercontent.com/artifact-keeper/stats/main/charts/artifact-keeper/countries.png)

**Where is the community?** Heat map of stargazers, forkers and contributors by self-reported GitHub
location, with countries shaded by website traffic. Click for the interactive globe.

[![Where is Artifact Keeper today? Spinning globe heat map](https://raw.githubusercontent.com/artifact-keeper/stats/main/charts/artifact-keeper/globe.gif)](https://artifact-keeper.github.io/stats/site/?project=artifact-keeper)

Country totals are in [`data/artifact-keeper/countries.csv`](data/artifact-keeper/countries.csv).

<details>
<summary>Individual charts</summary>
<p>
<img src="https://raw.githubusercontent.com/artifact-keeper/stats/main/charts/artifact-keeper/stars.png" alt="GitHub stars" width="100%"><br>
<img src="https://raw.githubusercontent.com/artifact-keeper/stats/main/charts/artifact-keeper/forks.png" alt="Forks" width="100%"><br>
<img src="https://raw.githubusercontent.com/artifact-keeper/stats/main/charts/artifact-keeper/contributors.png" alt="Contributors" width="100%"><br>
<img src="https://raw.githubusercontent.com/artifact-keeper/stats/main/charts/artifact-keeper/commits_weekly.png" alt="Commits per week" width="100%"><br>
<img src="https://raw.githubusercontent.com/artifact-keeper/stats/main/charts/artifact-keeper/docker_pulls.png" alt="Docker Hub pulls" width="100%"><br>
<img src="https://raw.githubusercontent.com/artifact-keeper/stats/main/charts/artifact-keeper/traffic.png" alt="GitHub traffic" width="100%"><br>
<img src="https://raw.githubusercontent.com/artifact-keeper/stats/main/charts/artifact-keeper/release_downloads.png" alt="Release downloads" width="100%">
</p>
</details>

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
