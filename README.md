# OSS growth stats

Adoption and community metrics for Artifact Keeper open-source projects, collected daily by
[a GitHub Actions workflow](.github/workflows/update.yml) and committed back to this repo.
Charts and numbers below regenerate on every run.

Last updated: **2026-10-07 17:09 UTC**

Data lives in [`data/`](data/) as plain CSV so it can be dropped into a spreadsheet or deck.
Chart images are in [`charts/`](charts/) as PNG and SVG. Machine-readable latest numbers are in
[`latest.json`](latest.json), and [`badges/`](badges/) holds shields.io endpoint badges for metrics
shields cannot compute on its own.

## artifact-keeper

Repository: [artifact-keeper/artifact-keeper](https://github.com/artifact-keeper/artifact-keeper)

| Metric | Now | 30-day change |
|---|---:|---:|
| GitHub stars | 1,113 |  |
| Forks | 152 |  |
| Contributors | 73 |  |
| Docker Hub pulls (all images) | 315,982 |  |
| Docker Hub pulls (`backend`) | 115,900 |  |
| Binary release downloads | 2,867 |  |
| Stable releases shipped | 45 |  |
| Merged pull requests | 2,128 |  |
| Closed issues | 1,946 |  |
| Discussions | 61 |  |
| Unique visitors, last 28 days | 2,526 |  |
| Unique git cloners, last 28 days | 1,675 |  |

30-day change needs 30 days of snapshots; it fills in as history accumulates.

![contributors](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/artifact-keeper/stats/main/badges/artifact-keeper/contributors.json) ![docker-pulls-total](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/artifact-keeper/stats/main/badges/artifact-keeper/docker-pulls-total.json) ![release-downloads](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/artifact-keeper/stats/main/badges/artifact-keeper/release-downloads.json) ![unique-cloners-28d](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/artifact-keeper/stats/main/badges/artifact-keeper/unique-cloners-28d.json) ![unique-visitors-28d](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/artifact-keeper/stats/main/badges/artifact-keeper/unique-visitors-28d.json)

![Growth overview](https://raw.githubusercontent.com/artifact-keeper/stats/main/charts/artifact-keeper/overview.png)

**Where is the community?** A spinning globe of stargazers, forkers and contributors by self-reported
GitHub location: [artifact-keeper.github.io/stats/site](https://artifact-keeper.github.io/stats/site/?project=artifact-keeper).
Country totals are in [`data/artifact-keeper/countries.csv`](data/artifact-keeper/countries.csv).

<details>
<summary>Individual charts</summary>

![GitHub stars](https://raw.githubusercontent.com/artifact-keeper/stats/main/charts/artifact-keeper/stars.png)
![Forks](https://raw.githubusercontent.com/artifact-keeper/stats/main/charts/artifact-keeper/forks.png)
![Contributors](https://raw.githubusercontent.com/artifact-keeper/stats/main/charts/artifact-keeper/contributors.png)
![Commits per week](https://raw.githubusercontent.com/artifact-keeper/stats/main/charts/artifact-keeper/commits_weekly.png)
![Docker Hub pulls](https://raw.githubusercontent.com/artifact-keeper/stats/main/charts/artifact-keeper/docker_pulls.png)
![GitHub traffic](https://raw.githubusercontent.com/artifact-keeper/stats/main/charts/artifact-keeper/traffic.png)
![Release downloads](https://raw.githubusercontent.com/artifact-keeper/stats/main/charts/artifact-keeper/release_downloads.png)

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
